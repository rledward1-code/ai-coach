# 🔌 AI Coach MCP 伺服器使用手冊 (Model Context Protocol Guide)

本目錄提供了一套標準的 **Model Context Protocol (MCP)** 伺服器，讓任何支援 MCP 協議的 AI 外腦（例如 **Google Antigravity**、**Claude Desktop**、**Cursor** 等）能夠直接調用運動科學工具，實現對跑步數據的深度解讀與課表推演。

---

## 🛠️ MCP 伺服器提供的 5 大專屬工具

| 工具名稱 | 參數 | 功能說明 |
| :--- | :--- | :--- |
| **`parse_activity`** | `file_path`: 本地 `.fit` 或 `.csv` 路徑 | 自動提取總距離、平均配速、心率區間分佈 (Zone 1~5)、Lap 明細、觸地時間 (GCT)、垂直振幅與步態剛性。 |
| **`simulate_training_plan`** | `target_pace`, `intervals_count`, `interval_distance_m`, `rest_seconds`, `current_rpe`, `weekly_mileage_km` | 模擬間歇課表負荷，推演 TRIMP 負荷指數、心率漂移曲線，並輸出路格 (Luger) 紅綠燈評定與佩絲 (Pace) 恢復處方。 |
| **`get_edward_runner_profile`** | 無 | 讀取跑者個人生理特質、乳酸閾值 (LTHR)、Zone 2 守護線與裝備清單。 |
| **`search_race_vault`** | `query`: 賽事關鍵字 (如 "台北馬", "長榮") | 檢索歷年重大賽事實績資料庫與訓練營課表。 |
| **`sync_latest_garmin_activity`** | `folder_override`: 自訂目錄 (選填) | 自動掃描 USB 連接的 Garmin 手錶目錄或本地同步資料夾，提取最新一次實跑檔案並輸出摘要。 |

---

## 🚀 3 步驟接入您的 AI 客戶端

### 1. 安裝環境與依賴
確保已安裝專案根目錄的 `requirements.txt`：
```powershell
pip install -r requirements.txt
```

### 2. 配置 MCP 客戶端設定檔

#### 情況 A：Claude Desktop 客戶端
打開您的 Claude Desktop 設定檔：
* **Windows**：`%APPDATA%\Claude\claude_desktop_config.json`
* **macOS**：`~/Library/Application Support/Claude/claude_desktop_config.json`

在 `mcpServers` 區塊中加入以下設定（請將路徑換成您電腦上的絕對路徑）：
```json
{
  "mcpServers": {
    "ai-coach": {
      "command": "python",
      "args": [
        "D:\\ai-coach\\mcp_server\\server.py"
      ],
      "env": {
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

#### 情況 B：Google Antigravity
在 Antigravity 專案設定檔中註冊 `ai-coach` MCP 伺服器，或在對話中直接透過雙教練 Skill 調用。

### 3. 重啟客戶端即可開始對話！
重啟 Claude Desktop 或 Antigravity 後，在聊天室中直接輸入：
* *「幫我分析 2026 長榮馬拉松的觸地時間與後半程疲勞心率」*
* *「我明天想跑 1000m x 6 趟 @ 4:45，請路格與佩絲教練評估負荷」*

AI 將會自動呼叫 MCP 工具完成量化計算，並以雙教練視角給出臨床診斷！
