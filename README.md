# Ansys Fluent MCP Server

讓 Claude 等 AI 助手透過 [PyFluent](https://fluent.docs.pyansys.com/) 直接操作 Ansys Fluent：
開啟／連線 Fluent、讀 case、下 TUI 指令、初始化與迭代，並且**診斷收斂問題**（例如 continuity 不收斂）。

> 非 Ansys 官方工具。

## 功能

| 工具 | 說明 |
|---|---|
| `check_environment` | Python / PyFluent 版本、已安裝的 Ansys 版本（`AWP_ROOTxxx`）、連線狀態 |
| `launch_fluent` | 開新的 Fluent（可指定版本 `2025R2`、核心數、是否顯示 GUI），session 會一直保留 |
| `connect_to_fluent` | 連到你**自己已經開好**的 Fluent（斷線時不會關掉 Fluent） |
| `close_fluent` | 關閉 session |
| `read_case` | 讀 `.cas.h5` / `.msh`；`with_data=True` 同時讀 `.dat`，會帶回之前的殘差紀錄 |
| `check_mesh` | `/mesh/check` + `/mesh/quality`：最小正交品質、最大長寬比、最小體積 |
| `get_setup_summary` | 模型、邊界條件、求解器設定（p-v coupling、離散格式、鬆弛因子） |
| `report_mass_balance` | 各邊界質量流率與淨不平衡百分比 |
| `initialize` | hybrid（建議）或 standard 初始化 |
| `iterate` | 跑 N 次迭代，回傳最新殘差、各方程式趨勢、新出現的警告 |
| `get_residual_history` | 殘差歷史與趨勢分析（下降／停滯／振盪／上升） |
| `diagnose_convergence` | **收斂診斷**：整合網格、質量守恆、設定、殘差趨勢、迭代警告，列出可能原因與建議（唯讀，不改設定） |
| `run_tui_commands` | 執行任意 Fluent TUI 指令並回傳輸出 |
| `run_journal` | 執行 `.jou` journal 檔 |
| `write_case_data` | 存 case + data |

每個指令都包在 Fluent transcript 裡執行，所以 AI 看得到 Fluent console 的完整輸出，包括 `reversed flow`、`turbulent viscosity limited` 這類警告。

## 安裝（在有 Ansys 的電腦上）

需求：Ansys Fluent 2025 R1/R2（或其他 PyFluent 支援的版本）、Python 3.10–3.13（建議 3.12）。

```powershell
git clone https://github.com/017-YiChing/ansys-mcp-server.git C:\ansys-mcp-server
cd C:\ansys-mcp-server
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

確認 Ansys 有被找到（應該看到 `AWP_ROOT251` 或 `AWP_ROOT252`）：

```powershell
Get-ChildItem env:AWP_ROOT*
```

## 接到 Claude

**Claude Code：**

```powershell
claude mcp add ansys -e ANSYS_MCP_WORKDIR=C:/cfd/work -- C:/ansys-mcp-server/.venv/Scripts/python.exe C:/ansys-mcp-server/ansys_mcp_server.py
```

**Claude 桌面版**（`%APPDATA%\Claude\claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "ansys": {
      "command": "C:/ansys-mcp-server/.venv/Scripts/python.exe",
      "args": ["C:/ansys-mcp-server/ansys_mcp_server.py"],
      "env": { "ANSYS_MCP_WORKDIR": "C:/cfd/work" }
    }
  }
}
```

`ANSYS_MCP_WORKDIR` 是 Fluent 的工作資料夾（暫存的 transcript 也放這裡），沒設定時用啟動目錄下的 `ansys_work/`。

## 使用方式

### 方式 A：讓 AI 開 Fluent

> 用 Fluent 2025R2、8 核心開啟 `C:/cfd/room.cas.h5`，檢查網格後用 hybrid 初始化，先跑 200 次。

### 方式 B：連到你已經開好的 Fluent（適合排查既有案例）

1. 在 Fluent 中 **File → Applications → Server → Start**，存出 server info 檔（例如 `C:/cfd/server_info.txt`）。
   也可以用指令啟動：`fluent 3ddp -sifile=C:/cfd/server_info.txt`
2. 對 AI 說：

> 連到 `C:/cfd/server_info.txt` 的 Fluent，幫我檢查為什麼 continuity 一直不收斂。

### 診斷 continuity 不收斂

`diagnose_convergence` 會一次收集：

- **網格**：最小正交品質（< 0.01 幾乎一定出問題，建議 > 0.1）、負體積
- **質量守恆**：淨質量流率不平衡 %（< 0.5% 通常可接受）
- **殘差趨勢**：continuity 是在下降、停滯、振盪還是上升
- **迭代警告**：出口回流（reversed flow）、湍流黏度被限制、發散
- **求解器設定**：p-v coupling、離散格式、鬆弛因子

然後依嚴重程度列出可能原因與建議。注意：

- 殘差紀錄來自 `iterate` 的輸出，或 `read_case(with_data=True)` 讀入的歷史。
  **建議先跑 100–200 次迭代再診斷**，因為 reversed flow 等警告只在迭代時出現。
- Fluent 的 continuity 殘差是「相對前 5 次迭代」的比例，常停在 1e-3～1e-2。
  若質量守恆 < 0.5% 且關心的監測值已平穩，通常可視為收斂，工具會提示這種情況。
- 診斷是啟發式判斷，最後仍需要你依物理意義判讀。

## 注意事項

- **路徑請用純英文**：Fluent 讀寫含中文的路徑（例如 OneDrive 的「國立成功大學」資料夾）常會失敗。
- **大量迭代請分段**：每次 `iterate` 建議 ≤ 300 次。若單次計算很久，可提高 Claude Code 的 MCP 逾時，例如設定環境變數 `MCP_TOOL_TIMEOUT=3600000`（毫秒）。
- `connect_to_fluent` 時，Fluent 必須跟 MCP server 在**同一台電腦**（transcript 檔需要能讀到）。
- 修改物理模型、邊界條件或求解器設定前，AI 會先告訴你要改什麼。

## 測試

不需要 Ansys，用模擬的 Fluent 輸出測試解析、診斷與 MCP 通訊：

```powershell
.venv\Scripts\python -m pytest -o asyncio_mode=auto
```

## License

MIT
