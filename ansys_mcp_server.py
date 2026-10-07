#!/usr/bin/env python3
"""
Ansys Fluent MCP Server

Lets an AI assistant drive Ansys Fluent through PyFluent: launch or attach to a
session, read cases, run TUI commands, initialize and iterate, and diagnose
convergence problems (mesh quality, residual trends, mass balance, solver
warnings).

Every Fluent command is wrapped in a Fluent transcript so its console output can
be returned to the assistant, which keeps the server independent of the
PyFluent settings-API differences between Fluent versions.
"""

import asyncio
import io
import logging
import math
import os
import re
import sys
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, Optional, Union

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError

    _MCP_V2 = True
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer
    from mcp.server.fastmcp.exceptions import ToolError

    _MCP_V2 = False

__version__ = "0.2.0"

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ansys-mcp")

MAX_TEXT = 12000
_FLOAT = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_NUM_RE = re.compile(rf"^{_FLOAT}$")


# ---------------------------------------------------------------------------
# Parsers for Fluent console output (pure functions, unit-tested)
# ---------------------------------------------------------------------------


def truncate(text: str, limit: int = MAX_TEXT) -> str:
    """Keep the head and tail of long console output."""
    if len(text) <= limit:
        return text
    head = limit // 3
    omitted = len(text) - limit
    return f"{text[:head]}\n... ({omitted} chars omitted) ...\n{text[-(limit - head):]}"


def parse_residual_lines(text: str) -> list[dict[str, float]]:
    """Parse the residual table Fluent prints while iterating.

    Header:  iter  continuity  x-velocity ...  time/iter
    Row:      120  1.2345e-03  4.5678e-05 ...  0:00:12  380
    """
    rows: list[dict[str, float]] = []
    header: Optional[list[str]] = None
    for line in text.splitlines():
        tokens = line.split()
        if not tokens:
            continue
        if tokens[0] == "iter" and len(tokens) > 1:
            header = [t for t in tokens[1:] if t != "time/iter"]
            continue
        if header and tokens[0].isdigit() and len(tokens) > len(header):
            values = tokens[1 : 1 + len(header)]
            if all(_NUM_RE.match(v) for v in values):
                row: dict[str, float] = {"iter": int(tokens[0])}
                row.update({name: float(v) for name, v in zip(header, values)})
                rows.append(row)
    return rows


_WARNING_PATTERNS = {
    "reversed_flow": re.compile(r"reversed flow", re.I),
    "turbulent_viscosity_limited": re.compile(r"turbulent viscosity limited", re.I),
    "divergence": re.compile(r"divergence detected|floating point exception", re.I),
    "temperature_limited": re.compile(r"temperature limited", re.I),
    "pressure_limited": re.compile(r"pressure limited", re.I),
}


def extract_warnings(text: str) -> dict[str, dict[str, Any]]:
    """Count solver warnings that usually explain poor convergence."""
    found: dict[str, dict[str, Any]] = {}
    for line in text.splitlines():
        stripped = line.strip()
        for key, pattern in _WARNING_PATTERNS.items():
            if pattern.search(stripped):
                entry = found.setdefault(key, {"count": 0, "examples": []})
                entry["count"] += 1
                if stripped not in entry["examples"] and len(entry["examples"]) < 5:
                    entry["examples"].append(stripped)
    return found


def merge_warnings(total: dict, new: dict) -> None:
    for key, entry in new.items():
        target = total.setdefault(key, {"count": 0, "examples": []})
        target["count"] += entry["count"]
        for example in entry["examples"]:
            if example not in target["examples"]:
                target["examples"].append(example)
        target["examples"] = target["examples"][-5:]


def parse_mesh_quality(text: str) -> dict[str, float]:
    """Extract key numbers from /mesh/check and /mesh/quality output."""
    patterns = {
        "min_orthogonal_quality": rf"Minimum Orthogonal Quality\s*=\s*({_FLOAT})",
        "max_aspect_ratio": rf"Maximum Aspect Ratio\s*=\s*({_FLOAT})",
        "max_skewness": rf"Maximum (?:Ortho )?Skew(?:ness)?\s*=\s*({_FLOAT})",
        "min_volume": rf"minimum volume\s*\(m3\)\s*:\s*({_FLOAT})",
        "max_volume": rf"maximum volume\s*\(m3\)\s*:\s*({_FLOAT})",
    }
    result = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        if match:
            result[key] = float(match.group(1))
    return result


def parse_mass_flow(text: str) -> Optional[dict[str, Any]]:
    """Parse the /report/fluxes/mass-flow table into a mass balance."""
    zones: dict[str, float] = {}
    net = None
    for line in text.splitlines():
        match = re.match(rf"^\s*(\S+)\s+({_FLOAT})\s*$", line)
        if not match:
            continue
        name, value = match.group(1), float(match.group(2))
        if name.lower() == "net":
            net = value
        else:
            zones[name] = value
    if not zones:
        return None
    if net is None:
        net = sum(zones.values())
    inflow = sum(v for v in zones.values() if v > 0)
    return {
        "zones_kg_s": zones,
        "net_kg_s": net,
        "total_inflow_kg_s": inflow,
        "imbalance_percent": abs(net) / inflow * 100 if inflow > 0 else None,
    }


def split_summary_sections(text: str) -> dict[str, str]:
    """Split /report/summary output on its top-level underlined headers."""
    lines = text.splitlines()
    sections: dict[str, list[str]] = {"_preamble": []}
    current = "_preamble"
    i = 0
    while i < len(lines):
        line = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if (
            line.strip()
            and not line.startswith((" ", "\t"))
            and nxt.strip()
            and set(nxt.strip()) == {"-"}
        ):
            current = line.strip()
            sections[current] = []
            i += 2
            continue
        sections[current].append(line)
        i += 1
    return {k: "\n".join(v).strip() for k, v in sections.items() if "".join(v).strip()}


def analyze_residuals(rows: list[dict], window: int = 200) -> dict[str, dict]:
    """Classify each residual's recent behaviour: dropping, stalled, oscillating, rising."""
    if not rows:
        return {}
    names = [k for k in rows[-1] if k != "iter"]
    recent = rows[-window:]
    result = {}
    for name in names:
        values = [r[name] for r in recent if r.get(name, 0) > 0]
        if len(values) < 2:
            continue
        logs = [math.log10(v) for v in values]
        # Compare the mean of the first and last fifth so oscillation phase doesn't skew it.
        segment = max(1, len(logs) // 5)
        dropped = sum(logs[:segment]) / segment - sum(logs[-segment:]) / segment
        amplitude = max(logs) - min(logs)
        if dropped > 0.5:
            trend = "dropping"
        elif dropped < -0.5:
            trend = "rising"
        elif amplitude >= 0.5:
            trend = "stalled_oscillating"
        else:
            trend = "stalled"
        result[name] = {
            "latest": values[-1],
            "min_overall": min(r[name] for r in rows if r.get(name, 0) > 0),
            "window_iterations": len(values),
            "decades_dropped_in_window": round(dropped, 2),
            "log10_amplitude_in_window": round(amplitude, 2),
            "trend": trend,
        }
    return result


def build_flags(
    mesh: dict, residuals: dict, warnings: dict, mass: Optional[dict]
) -> list[dict[str, str]]:
    """Turn the collected evidence into prioritized findings (heuristics, not verdicts)."""
    flags = []

    def add(severity, item, detail, suggestion):
        flags.append(
            {"severity": severity, "item": item, "detail": detail, "suggestion": suggestion}
        )

    if mesh.get("min_volume") is not None and mesh["min_volume"] <= 0:
        add(
            "high",
            "負體積網格",
            f"minimum volume = {mesh['min_volume']:.3e} m3",
            "網格有翻轉/負體積元素，必須回到前處理修正網格，求解器設定無法補救。",
        )
    oq = mesh.get("min_orthogonal_quality")
    if oq is not None:
        if oq < 0.01:
            add(
                "high",
                "網格正交品質極差",
                f"min orthogonal quality = {oq:.3e}（建議 > 0.1，至少 > 0.01）",
                "continuity 不收斂最常見的原因。找出低品質網格位置（transcript 會列 cell 座標），"
                "重新劃分該處網格；暫時可試 /mesh/repair-improve/improve-quality。",
            )
        elif oq < 0.1:
            add(
                "medium",
                "網格正交品質偏低",
                f"min orthogonal quality = {oq:.3e}（建議 > 0.1）",
                "若低品質網格位於流動劇烈處（開口、角落），可能造成殘差停滯；考慮局部加密或改善。",
            )
    ar = mesh.get("max_aspect_ratio")
    if ar is not None and ar > 1000:
        add(
            "low",
            "長寬比很大",
            f"max aspect ratio = {ar:.3g}",
            "邊界層網格長寬比大是正常的；若出現在主流區則應改善網格。",
        )

    for key in ("divergence",):
        if key in warnings:
            add(
                "high",
                "計算發散",
                warnings[key]["examples"][0],
                "降低 under-relaxation 或 Courant number、改用 first-order 起步、檢查邊界條件與單位。",
            )
    if "reversed_flow" in warnings:
        add(
            "high",
            "出口回流 (reversed flow)",
            f"出現 {warnings['reversed_flow']['count']} 次，例：{warnings['reversed_flow']['examples'][0]}",
            "出口太靠近建築/障礙物會讓渦流穿過出口，是 continuity 停滯的典型原因。"
            "把計算域往下游延長（室外風場建議建築後方 ≥15H），或確認出口 backflow 設定合理。",
        )
    if "turbulent_viscosity_limited" in warnings:
        add(
            "medium",
            "湍流黏度被限制",
            f"出現 {warnings['turbulent_viscosity_limited']['count']} 次",
            "通常是初始條件、入口湍流參數不合理或局部網格太差；檢查入口 turbulence intensity / "
            "length scale，並先用 hybrid initialization。",
        )
    for key, label in (("temperature_limited", "溫度"), ("pressure_limited", "壓力")):
        if key in warnings:
            add(
                "medium",
                f"{label}被限制",
                warnings[key]["examples"][0],
                "解在某些網格出現非物理值，檢查該區網格與邊界條件。",
            )

    continuity = residuals.get("continuity")
    if continuity:
        trend = continuity["trend"]
        latest = continuity["latest"]
        if trend == "rising":
            add(
                "high",
                "continuity 殘差上升",
                f"最近 {continuity['window_iterations']} 次迭代上升 "
                f"{-continuity['decades_dropped_in_window']} 個數量級",
                "可能正在發散：降低 pressure / momentum under-relaxation，或改用 pseudo-transient。",
            )
        elif trend.startswith("stalled") and latest > 1e-3:
            osc = trend == "stalled_oscillating"
            add(
                "medium",
                "continuity 殘差停滯" + ("且振盪" if osc else ""),
                f"目前 {latest:.2e}，最近 {continuity['window_iterations']} 次迭代幾乎沒下降",
                ("振盪常代表流場本身不穩定（建築尾流渦旋脫落），穩態可能根本不存在，"
                 "可考慮改跑暫態或用監測值平均。" if osc else
                 "檢查網格品質與出口回流；可試 Coupled + pseudo-transient、second-order 前先用 "
                 "first-order 跑穩。"),
            )

    if mass and mass.get("imbalance_percent") is not None:
        pct = mass["imbalance_percent"]
        if pct > 1:
            add(
                "medium",
                "質量不守恆",
                f"淨質量流率不平衡 {pct:.2f}%（建議 < 0.5%）",
                "解尚未收斂，繼續迭代或依其他項目修正。",
            )
        elif continuity and continuity["latest"] > 1e-3 and pct < 0.5:
            add(
                "info",
                "質量守恆其實已達標",
                f"不平衡僅 {pct:.3f}%，但 continuity 殘差 = {continuity['latest']:.2e}",
                "Fluent 的 continuity 殘差是相對第 5 次迭代的比例，常停在 1e-3~1e-2。"
                "若質量守恆 < 0.5% 且關心的監測值（如出口風速、平均溫度）已平穩，通常可視為收斂。",
            )
    return flags


CONVERGENCE_CHECKLIST = [
    "1. 網格：min orthogonal quality > 0.1、無負體積、關鍵區域（開口/角落）網格夠細。",
    "2. 出口位置：出口離建築或障礙物夠遠，迭代中不應持續出現 reversed flow。",
    "3. 邊界條件：入口速度/湍流參數合理、單位正確；封閉空間需有明確的壓力參考。",
    "4. 初始化：先用 hybrid initialization，避免從零速度場開始。",
    "5. 求解器：Coupled + pseudo-transient 通常比 SIMPLE 穩；先 first-order 跑穩再切 second-order。",
    "6. 物理：浮力/自然通風或建築尾流本質不穩定時，穩態殘差會振盪，應改暫態或看平均監測值。",
    "7. 判定收斂：不要只看殘差，要同時看質量守恆（< 0.5%）與關心的監測值是否平穩。",
]


# ---------------------------------------------------------------------------
# Fluent session controller
# ---------------------------------------------------------------------------


def _scheme_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _quote_path(path: Union[str, Path]) -> str:
    return '"' + str(path).replace("\\", "/") + '"'


def normalize_version(version: str) -> str:
    """Accept '2025R2', '25R2', '252' or '25.2.0' and return '25.2.0'."""
    v = version.strip().upper().replace(" ", "")
    match = re.fullmatch(r"(?:20)?(\d{2})R(\d)", v)
    if match:
        return f"{match.group(1)}.{match.group(2)}.0"
    match = re.fullmatch(r"(\d{2})(\d)", v)
    if match:
        return f"{match.group(1)}.{match.group(2)}.0"
    return version.strip()


def _path_warnings(path: Path) -> list[str]:
    if any(ord(ch) > 127 for ch in str(path)):
        return ["路徑含中文或非 ASCII 字元，Fluent 可能讀寫失敗；建議改放在純英文路徑（例如 C:/cfd/）。"]
    return []


Action = Union[str, Callable[[], Any]]


class FluentController:
    def __init__(self):
        self.solver = None
        self.session_info: dict[str, Any] = {}
        self.lock = threading.Lock()
        self.workdir = Path(
            os.environ.get("ANSYS_MCP_WORKDIR") or Path.cwd() / "ansys_work"
        ).resolve()
        self.residual_rows: list[dict] = []
        self.warnings: dict[str, dict] = {}

    # -- low level ---------------------------------------------------------

    def require(self):
        if self.solver is None:
            raise RuntimeError("尚未連線 Fluent，請先呼叫 launch_fluent 或 connect_to_fluent。")
        return self.solver

    def _scheme(self, code: str):
        solver = self.require()
        for attr in ("scheme_eval", "scheme"):
            obj = getattr(solver, attr, None)
            if obj is None:
                continue
            # SchemeEval.eval() takes a Python-ized scheme object, so only the
            # string-based entry points are safe here.
            for method in ("scheme_eval", "string_eval"):
                fn = getattr(obj, method, None)
                if callable(fn):
                    return fn(code)
            if callable(obj):
                return obj(code)
        raise RuntimeError("這個 PyFluent 版本找不到 scheme 介面。")

    def _tui_raw(self, command: str):
        return self._scheme(f"(ti-menu-load-string {_scheme_string(command)})")

    def capture(self, actions: list[Action]) -> tuple[str, list[Any]]:
        """Run TUI commands / callables inside a Fluent transcript and return its text."""
        self.require()
        self.workdir.mkdir(parents=True, exist_ok=True)
        transcript = self.workdir / f"_mcp_{uuid.uuid4().hex[:8]}.trn"
        results = []
        started = False
        try:
            self._tui_raw(f"/file/start-transcript {_quote_path(transcript)}")
            started = True
            for action in actions:
                results.append(action() if callable(action) else self._tui_raw(action))
        finally:
            if started:
                try:
                    self._tui_raw("/file/stop-transcript")
                except Exception:
                    logger.exception("stop-transcript failed")
        text = ""
        if transcript.exists():
            text = transcript.read_text(encoding="utf-8", errors="replace")
            try:
                transcript.unlink()
            except OSError:
                pass
        self.residual_rows.extend(parse_residual_lines(text))
        merge_warnings(self.warnings, extract_warnings(text))
        return text, results

    def _monitor_residual_history(self) -> list[dict]:
        """Residual history stored in the case/data (e.g. iterations run before connecting)."""
        solver = self.require()
        for attr in ("monitors", "monitors_manager"):
            manager = getattr(solver, attr, None)
            getter = getattr(manager, "get_monitor_set_data", None)
            if not callable(getter):
                continue
            try:
                indices, data = getter(monitor_set_name="residual")
                indices = list(indices)
                if not indices or not isinstance(data, dict):
                    continue
                rows = []
                for i, it in enumerate(indices):
                    row = {"iter": int(it)}
                    for name, series in data.items():
                        row[name] = float(list(series)[i])
                    rows.append(row)
                return rows
            except Exception:
                logger.debug("get_monitor_set_data failed", exc_info=True)
        return []

    def residual_history(self) -> list[dict]:
        if not self.residual_rows:
            self.residual_rows = self._monitor_residual_history()
        return self.residual_rows

    def _reset_history(self):
        self.residual_rows = []
        self.warnings = {}

    # -- session -----------------------------------------------------------

    def environment(self) -> dict:
        try:
            from importlib.metadata import version

            pyfluent_version = version("ansys-fluent-core")
        except Exception:
            pyfluent_version = None
        awp = {k: v for k, v in os.environ.items() if k.upper().startswith("AWP_ROOT")}
        return {
            "python": sys.version.split()[0],
            "pyfluent": pyfluent_version or "未安裝（pip install ansys-fluent-core）",
            "ansys_installations": awp or "找不到 AWP_ROOTxxx 環境變數，Ansys 可能未安裝",
            "connected": self.solver is not None,
            "session": self.session_info,
            "working_directory": str(self.workdir),
            "recorded_iterations": len(self.residual_rows),
        }

    def launch(self, version, processors, dimension, precision, show_gui, working_dir):
        import ansys.fluent.core as pyfluent

        if self.solver is not None:
            raise RuntimeError("已經有 Fluent session，請先 close_fluent。")
        cwd = Path(working_dir).resolve() if working_dir else self.workdir
        cwd.mkdir(parents=True, exist_ok=True)

        def enum(cls_name, member, raw):
            cls = getattr(pyfluent, cls_name, None)
            return getattr(cls, member, raw) if cls is not None else raw

        kwargs = {
            "mode": enum("FluentMode", "SOLVER", "solver"),
            "precision": enum("Precision", precision.upper(), precision),
            "dimension": enum("Dimension", "THREE" if dimension == 3 else "TWO", dimension),
            "processor_count": processors,
            "ui_mode": enum("UIMode", "GUI" if show_gui else "NO_GUI",
                            "gui" if show_gui else "no_gui"),
            "cwd": str(cwd),
        }
        if version:
            kwargs["product_version"] = normalize_version(version)
        try:
            self.solver = pyfluent.launch_fluent(**kwargs)
        except TypeError:
            # Older PyFluent uses show_gui instead of ui_mode.
            kwargs.pop("ui_mode")
            kwargs["show_gui"] = show_gui
            self.solver = pyfluent.launch_fluent(**kwargs)
        self.workdir = cwd
        self._after_connect("launched", cleanup=True)
        return self.session_info

    def connect(self, server_info_file, ip, port, password):
        import ansys.fluent.core as pyfluent

        if self.solver is not None:
            raise RuntimeError("已經有 Fluent session，請先 close_fluent。")
        kwargs: dict[str, Any] = {"cleanup_on_exit": False}
        if server_info_file:
            kwargs["server_info_file_name"] = str(Path(server_info_file).resolve())
        else:
            kwargs.update(ip=ip or "127.0.0.1", port=port, password=password)
        self.solver = pyfluent.connect_to_fluent(**kwargs)
        self._after_connect("connected", cleanup=False)
        return self.session_info

    def _after_connect(self, how: str, cleanup: bool):
        self._reset_history()
        info: dict[str, Any] = {"how": how, "closes_fluent_on_exit": cleanup}
        try:
            info["fluent_version"] = str(self.solver.get_fluent_version())
        except Exception:
            pass
        self.session_info = info
        try:
            # Let write commands overwrite files instead of waiting on a prompt.
            self._tui_raw("/file/confirm-overwrite? no")
        except Exception:
            logger.debug("confirm-overwrite not available", exc_info=True)

    def close(self):
        if self.solver is None:
            return {"status": "no session"}
        try:
            self.solver.exit()
        finally:
            self.solver = None
            info, self.session_info = self.session_info, {}
        return {"status": "closed", "session": info}

    # -- operations ----------------------------------------------------------

    def read_case(self, path: str, with_data: bool):
        p = Path(path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"找不到檔案：{p}")
        command = "/file/read-case-data" if with_data else "/file/read-case"
        self._reset_history()
        text, _ = self.capture([f"{command} {_quote_path(p)}"])
        self.residual_rows = self._monitor_residual_history() if with_data else []
        return {
            "file": str(p),
            "warnings": _path_warnings(p),
            "existing_iterations_in_data": len(self.residual_rows),
            "output": truncate(text, 4000),
        }

    def check_mesh(self):
        text, _ = self.capture(["/mesh/check", "/mesh/quality"])
        metrics = parse_mesh_quality(text)
        return {
            "metrics": metrics,
            "flags": build_flags(metrics, {}, {}, None),
            "output": truncate(text, 6000),
        }

    def setup_summary(self, include_materials: bool):
        text, _ = self.capture(["/report/summary no"])
        sections = split_summary_sections(text)
        if not include_materials:
            sections = {k: v for k, v in sections.items() if "material" not in k.lower()}
        body = "\n\n".join(f"== {k} ==\n{v}" for k, v in sections.items() if k != "_preamble")
        return {"sections": list(sections), "summary": truncate(body or text)}

    def mass_balance(self):
        text, _ = self.capture(["/report/fluxes/mass-flow yes no"])
        mass = parse_mass_flow(text)
        if mass is None:
            solver = self.require()
            settings = getattr(solver, "settings", solver)

            def api_call():
                settings.results.report.fluxes.mass_flow(all_bndry_zones=True)

            try:
                text, _ = self.capture([api_call])
                mass = parse_mass_flow(text)
            except Exception:
                logger.debug("settings API mass_flow failed", exc_info=True)
        return {"mass_balance": mass, "output": truncate(text, 3000)}

    def initialize(self, method: str):
        commands = {
            "hybrid": "/solve/initialize/hyb-initialization",
            "standard": "/solve/initialize/initialize-flow",
        }
        if method not in commands:
            raise ValueError("method 必須是 'hybrid' 或 'standard'")
        self._reset_history()
        text, _ = self.capture([commands[method]])
        return {"method": method, "output": truncate(text, 3000)}

    def iterate(self, iterations: int):
        before = len(self.residual_history())
        warnings_before = {k: v["count"] for k, v in self.warnings.items()}
        text, _ = self.capture([f"/solve/iterate {iterations}"])
        new_rows = self.residual_rows[before:]
        new_warnings = {
            k: v["count"] - warnings_before.get(k, 0)
            for k, v in self.warnings.items()
            if v["count"] > warnings_before.get(k, 0)
        }
        return {
            "iterations_completed": len(new_rows),
            "total_recorded_iterations": len(self.residual_rows),
            "latest_residuals": new_rows[-1] if new_rows else None,
            "converged_by_criteria": "solution is converged" in text.lower(),
            "diverged": "divergence" in new_warnings,
            "new_warning_counts": new_warnings,
            "residual_trends": analyze_residuals(self.residual_rows),
            "output_tail": text[-2500:],
        }

    def residual_report(self, last_n: int, window: int):
        rows = self.residual_history()
        tail = rows[-last_n:] if last_n > 0 else []
        step = max(1, len(tail) // 60)
        return {
            "total_recorded_iterations": len(rows),
            "trends": analyze_residuals(rows, window),
            "history_sampled": tail[::step] + ([tail[-1]] if tail and step > 1 else []),
            "warnings": self.warnings,
        }

    def diagnose(self, window: int):
        report: dict[str, Any] = {"errors": {}}
        mesh: dict = {}
        mass = None
        steps = {
            "mesh": self.check_mesh,
            "mass_balance": self.mass_balance,
            "setup_summary": lambda: self.setup_summary(include_materials=False),
        }
        for name, fn in steps.items():
            try:
                report[name] = fn()
            except Exception as e:
                report["errors"][name] = f"{type(e).__name__}: {e}"
        if "mesh" in report:
            mesh = report["mesh"]["metrics"]
            report["mesh"] = {"metrics": mesh}
        if "mass_balance" in report:
            mass = report["mass_balance"]["mass_balance"]
            report["mass_balance"] = mass
        rows = self.residual_history()
        residuals = analyze_residuals(rows, window)
        report["residual_trends"] = residuals
        report["recorded_iterations"] = len(rows)
        report["solver_warnings"] = self.warnings
        report["flags"] = build_flags(mesh, residuals, self.warnings, mass)
        report["checklist"] = CONVERGENCE_CHECKLIST
        if not rows:
            report["note"] = (
                "沒有殘差紀錄：請先用 iterate 跑一段（例如 100 次），"
                "迭代輸出中的 reversed flow 等警告是重要診斷依據。"
            )
        if not report["errors"]:
            del report["errors"]
        return report

    def write_case_data(self, path: str):
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        text, _ = self.capture([f"/file/write-case-data {_quote_path(p)}"])
        return {"file": str(p), "warnings": _path_warnings(p), "output": truncate(text, 2000)}

    def run_journal(self, path: str):
        p = Path(path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"找不到檔案：{p}")
        text, _ = self.capture([f"/file/read-journal {_quote_path(p)}"])
        return {"journal": str(p), "output": truncate(text)}

    def run_tui(self, commands: list[str]):
        text, results = self.capture(list(commands))
        return {
            "results": [str(r) for r in results],
            "output": truncate(text),
        }


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

fluent = FluentController()

mcp = MCPServer(
    "ansys-fluent",
    instructions=(
        "Tools for driving Ansys Fluent through PyFluent. Typical flow: check_environment -> "
        "launch_fluent (or connect_to_fluent to a Fluent the user already opened) -> read_case -> "
        "check_mesh / get_setup_summary -> initialize -> iterate (in chunks of <=300 iterations so "
        "progress can be reviewed) -> diagnose_convergence when residuals stall. "
        "Before changing physics, boundary conditions or solver settings with run_tui_commands, "
        "tell the user what will change and why. Report residual numbers, mass imbalance and "
        "mesh metrics exactly as returned; never invent them."
    ),
)


async def _call(fn: Callable, *args):
    def locked():
        with fluent.lock:
            return fn(*args)

    try:
        return await asyncio.to_thread(locked)
    except Exception as e:
        # ToolError passes the message through to the assistant instead of a generic error.
        logger.exception("tool failed")
        raise ToolError(f"{type(e).__name__}: {e}") from e


@mcp.tool()
async def check_environment() -> dict:
    """Report Python/PyFluent versions, installed Ansys versions (AWP_ROOTxxx) and session state."""
    return await _call(fluent.environment)


@mcp.tool()
async def launch_fluent(
    version: str = "",
    processors: int = 4,
    dimension: int = 3,
    precision: str = "double",
    show_gui: bool = True,
    working_dir: str = "",
) -> dict:
    """Launch a new Fluent solver session and keep it open for later tools.

    version: e.g. "2025R2", "252" or "25.2.0"; empty = newest installed.
    show_gui: show the Fluent window so the user can watch.
    working_dir: Fluent working directory (ASCII-only path recommended).
    """
    return await _call(
        fluent.launch, version, processors, dimension, precision, show_gui, working_dir
    )


@mcp.tool()
async def connect_to_fluent(
    server_info_file: str = "", ip: str = "", port: int = 0, password: str = ""
) -> dict:
    """Attach to a Fluent the user already opened (File > Applications > Server > Start,
    or started with -sifile=<file>). Closing this connection later leaves Fluent running."""
    return await _call(fluent.connect, server_info_file, ip, port, password)


@mcp.tool()
async def close_fluent() -> dict:
    """Close the session (exits Fluent if it was launched by launch_fluent)."""
    return await _call(fluent.close)


@mcp.tool()
async def read_case(file_path: str, with_data: bool = False) -> dict:
    """Read a case (.cas.h5/.cas) or mesh (.msh/.msh.h5); with_data also reads the .dat
    file, which brings back the stored residual history."""
    return await _call(fluent.read_case, file_path, with_data)


@mcp.tool()
async def check_mesh() -> dict:
    """Run /mesh/check and /mesh/quality: min orthogonal quality, max aspect ratio,
    min volume, plus flagged problems."""
    return await _call(fluent.check_mesh)


@mcp.tool()
async def get_setup_summary(include_materials: bool = False) -> dict:
    """Fluent /report/summary: models, boundary conditions, solver settings
    (p-v coupling, discretization, relaxation factors)."""
    return await _call(fluent.setup_summary, include_materials)


@mcp.tool()
async def report_mass_balance() -> dict:
    """Mass flow through every boundary zone and the net imbalance in percent."""
    return await _call(fluent.mass_balance)


@mcp.tool()
async def initialize(method: str = "hybrid") -> dict:
    """Initialize the flow field: 'hybrid' (recommended) or 'standard'."""
    return await _call(fluent.initialize, method)


@mcp.tool()
async def iterate(iterations: int = 100) -> dict:
    """Run steady iterations. Returns latest residuals, per-equation trends and new solver
    warnings (reversed flow, turbulent viscosity limited, divergence)."""
    return await _call(fluent.iterate, iterations)


@mcp.tool()
async def get_residual_history(last_n: int = 300, window: int = 200) -> dict:
    """Residual history (sampled to ~60 rows) and trend analysis over the last `window`
    iterations."""
    return await _call(fluent.residual_report, last_n, window)


@mcp.tool()
async def diagnose_convergence(window: int = 200) -> dict:
    """Collect evidence for convergence problems (e.g. continuity not converging): mesh
    quality, mass balance, solver setup, residual trends and solver warnings, with
    prioritized findings and a checklist. Read-only: changes nothing in the case."""
    return await _call(fluent.diagnose, window)


@mcp.tool()
async def run_tui_commands(commands: list[str]) -> dict:
    """Run Fluent TUI commands in order (e.g. "/solve/set/p-v-coupling 24") and return the
    console output. Use for any setting the dedicated tools don't cover."""
    return await _call(fluent.run_tui, commands)


@mcp.tool()
async def run_journal(file_path: str) -> dict:
    """Execute a Fluent journal file (.jou)."""
    return await _call(fluent.run_journal, file_path)


@mcp.tool()
async def write_case_data(file_path: str) -> dict:
    """Save case and data (e.g. C:/cfd/run1.cas.h5)."""
    return await _call(fluent.write_case_data, file_path)


def main():
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    if _MCP_V2:
        # mcp 2.x points fd 1 at stderr while serving, so Fluent's console output
        # cannot reach the JSON-RPC stream.
        mcp.run("stdio")
    else:
        _run_stdio_mcp_v1()


def _run_stdio_mcp_v1():
    import anyio
    from mcp.server.stdio import stdio_server

    # Fluent's child process and some libraries write to stdout, which would corrupt
    # the JSON-RPC stream. Keep the real stdout for MCP and send everything else to stderr.
    mcp_fd = os.dup(1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    mcp_out = anyio.wrap_file(io.TextIOWrapper(os.fdopen(mcp_fd, "wb"), encoding="utf-8"))

    async def run():
        server = mcp._mcp_server
        async with stdio_server(stdout=mcp_out) as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    anyio.run(run)


if __name__ == "__main__":
    main()
