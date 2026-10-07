import json
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ansys_mcp_server as srv  # noqa: E402

ITERATE_OUTPUT = """
  iter  continuity  x-velocity  y-velocity  z-velocity           k       omega     time/iter
     1  1.0000e+00  4.1234e-03  3.2100e-03  2.9000e-03  1.2000e-01  2.3000e+00  0:00:09  299
     2  6.5400e-01  2.1000e-03  1.6000e-03  1.5000e-03  8.0000e-02  1.1000e-01  0:00:08  298
 Warning: reversed flow in 132 faces (1.2% area) on pressure-outlet 7.
     3  4.2000e-01  1.5000e-03  1.1000e-03  1.0000e-03  5.0000e-02  6.0000e-02  0:00:08  297
 turbulent viscosity limited to viscosity ratio of 1.000000e+05 in 12 cells
"""

MESH_OUTPUT = """
 Volume statistics:
  minimum volume (m3): 2.345678e-09
  maximum volume (m3): 1.234000e+00
    total volume (m3): 5.000000e+04
Mesh Quality:

Minimum Orthogonal Quality = 4.56000e-03 cell 1234 on zone 2 (ID: 5678 on partition: 0) at location (1.0, 2.0, 3.0)
Maximum Aspect Ratio = 2.43000e+02 cell 99 on zone 2
"""

MASS_OUTPUT = """
                             Mass Flow Rate                [kg/s]
-------------------------------- --------------------
                           inlet            12.25
                          outlet           -12.20
                            wall                0
                ---------------- --------------------
                             Net            0.05
"""

SUMMARY_OUTPUT = """
Models
------

   Model                        Settings
   -------------------------------------------------------------
   Space                        3D
   Viscous                      SST k-omega turbulence model

Material Properties
-------------------

   Material: air (fluid)
      Density   kg/m3   1.225

Solver Settings
---------------

   Equations
      Flow   yes
"""


def test_parse_residuals_and_warnings():
    rows = srv.parse_residual_lines(ITERATE_OUTPUT)
    assert [r["iter"] for r in rows] == [1, 2, 3]
    assert rows[2]["continuity"] == pytest.approx(0.42)
    assert rows[0]["omega"] == pytest.approx(2.3)
    assert "time/iter" not in rows[0]

    warnings = srv.extract_warnings(ITERATE_OUTPUT)
    assert warnings["reversed_flow"]["count"] == 1
    assert "pressure-outlet 7" in warnings["reversed_flow"]["examples"][0]
    assert warnings["turbulent_viscosity_limited"]["count"] == 1


def test_parse_mesh_quality():
    metrics = srv.parse_mesh_quality(MESH_OUTPUT)
    assert metrics["min_orthogonal_quality"] == pytest.approx(4.56e-3)
    assert metrics["max_aspect_ratio"] == pytest.approx(243)
    assert metrics["min_volume"] == pytest.approx(2.345678e-9)


def test_parse_mass_flow():
    mass = srv.parse_mass_flow(MASS_OUTPUT)
    assert mass["net_kg_s"] == pytest.approx(0.05)
    assert mass["zones_kg_s"]["outlet"] == pytest.approx(-12.2)
    assert mass["imbalance_percent"] == pytest.approx(0.05 / 12.25 * 100)


def test_split_summary_sections():
    sections = srv.split_summary_sections(SUMMARY_OUTPUT)
    assert set(sections) == {"Models", "Material Properties", "Solver Settings"}
    assert "SST" in sections["Models"]


def _rows(values):
    return [{"iter": i + 1, "continuity": v} for i, v in enumerate(values)]


def test_analyze_residual_trends():
    dropping = srv.analyze_residuals(_rows([10 ** (-i / 50) for i in range(200)]))
    assert dropping["continuity"]["trend"] == "dropping"

    stalled = srv.analyze_residuals(_rows([5e-3 * (1.6 if i % 2 else 1) for i in range(200)]))
    assert stalled["continuity"]["trend"] == "stalled"

    oscillating = srv.analyze_residuals(_rows([5e-3 * (10 if i % 20 < 10 else 1) for i in range(200)]))
    assert oscillating["continuity"]["trend"] == "stalled_oscillating"

    rising = srv.analyze_residuals(_rows([1e-4 * 10 ** (i / 50) for i in range(200)]))
    assert rising["continuity"]["trend"] == "rising"


def test_flags_for_typical_continuity_problem():
    mesh = srv.parse_mesh_quality(MESH_OUTPUT)
    residuals = srv.analyze_residuals(_rows([5e-3] * 200))
    warnings = srv.extract_warnings(ITERATE_OUTPUT)
    flags = srv.build_flags(mesh, residuals, warnings, srv.parse_mass_flow(MASS_OUTPUT))
    items = [f["item"] for f in flags]
    assert "網格正交品質極差" in items
    assert "出口回流 (reversed flow)" in items
    assert "continuity 殘差停滯" in items
    assert "質量守恆其實已達標" in items


@pytest.mark.parametrize(
    "raw, expected",
    [("2025R2", "25.2.0"), ("25 R1", "25.1.0"), ("252", "25.2.0"), ("25.2.0", "25.2.0")],
)
def test_normalize_version(raw, expected):
    assert srv.normalize_version(raw) == expected


class FakeScheme:
    """Mimics Fluent: writes canned console output into the active transcript."""

    CANNED = {
        "/mesh/check": MESH_OUTPUT,
        "/mesh/quality": "",
        "/report/fluxes/mass-flow yes no": MASS_OUTPUT,
        "/report/summary no": SUMMARY_OUTPUT,
        "/solve/iterate 3": ITERATE_OUTPUT,
    }

    def __init__(self):
        self.commands = []
        self.transcript = None
        self.buffer = []

    def scheme_eval(self, code):
        match = re.fullmatch(r'\(ti-menu-load-string "(.*)"\)', code, re.S)
        command = match.group(1).replace('\\"', '"').replace("\\\\", "\\")
        self.commands.append(command)
        if command.startswith("/file/start-transcript"):
            self.transcript = command.split(" ", 1)[1].strip('"')
            self.buffer = []
        elif command == "/file/stop-transcript":
            Path(self.transcript).write_text("".join(self.buffer), encoding="utf-8")
            self.transcript = None
        elif self.transcript:
            self.buffer.append(f"> {command}\n{self.CANNED.get(command, '')}")
        return True


class FakeSolver:
    def __init__(self):
        self.scheme_eval = FakeScheme()
        self.exited = False

    def exit(self):
        self.exited = True


@pytest.fixture
def controller(tmp_path, monkeypatch):
    monkeypatch.setenv("ANSYS_MCP_WORKDIR", str(tmp_path))
    ctl = srv.FluentController()
    ctl.solver = FakeSolver()
    return ctl


def test_requires_session():
    ctl = srv.FluentController()
    with pytest.raises(RuntimeError, match="launch_fluent"):
        ctl.run_tui(["/report/summary no"])


def test_capture_quotes_paths_and_cleans_up(controller, tmp_path):
    result = controller.run_tui(['/file/read-case "C:/my cases/a.cas.h5"'])
    commands = controller.solver.scheme_eval.commands
    assert commands[0].startswith('/file/start-transcript "')
    assert commands[1] == '/file/read-case "C:/my cases/a.cas.h5"'
    assert commands[-1] == "/file/stop-transcript"
    assert "C:/my cases/a.cas.h5" in result["output"]
    assert not list(tmp_path.glob("_mcp_*.trn"))


def test_iterate_then_diagnose(controller):
    result = controller.iterate(3)
    assert result["iterations_completed"] == 3
    assert result["latest_residuals"]["continuity"] == pytest.approx(0.42)
    assert result["new_warning_counts"] == {"reversed_flow": 1, "turbulent_viscosity_limited": 1}

    report = controller.diagnose(window=200)
    assert "errors" not in report
    assert report["mesh"]["metrics"]["min_orthogonal_quality"] == pytest.approx(4.56e-3)
    assert report["mass_balance"]["net_kg_s"] == pytest.approx(0.05)
    assert "Material Properties" not in report["setup_summary"]["sections"]
    assert report["recorded_iterations"] == 3
    assert {f["severity"] for f in report["flags"]} >= {"high"}
    json.dumps(report, ensure_ascii=False)


def test_read_case_rejects_missing_file(controller, tmp_path):
    with pytest.raises(FileNotFoundError):
        controller.read_case(str(tmp_path / "nope.cas.h5"), with_data=False)


async def test_mcp_stdio_roundtrip(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(srv.__file__))],
        env={**os.environ, "ANSYS_MCP_WORKDIR": str(tmp_path)},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = {t.name for t in (await session.list_tools()).tools}
            assert {"launch_fluent", "iterate", "diagnose_convergence"} <= tools
            env = await session.call_tool("check_environment", {})
            assert json.loads(env.content[0].text)["connected"] is False
            err = await session.call_tool("iterate", {"iterations": 10})
            is_error = getattr(err, "is_error", None) or getattr(err, "isError", None)
            assert is_error and "launch_fluent" in err.content[0].text
