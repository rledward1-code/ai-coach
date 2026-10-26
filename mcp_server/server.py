# d:\ai-coach\mcp_server\server.py
"""
AI Coach MCP 伺服器 (ai-coach-mcp)
提供專業運動科學計算、Garmin FIT/CSV 活動解析、Edward 專屬生理校準與課表微調模擬。
支援透過標準 Model Context Protocol (MCP) 與任何 LLM 客戶端連接。
"""

import sys
import os
import json

# 強制 Windows 環境下輸出使用 UTF-8
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# 將專案目錄與當前目錄加入 path
SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SERVER_DIR)
for p in [SERVER_DIR, PROJECT_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

from mcp.server.mcpserver import MCPServer
import tools
import garmin_local

# 建立 MCP 伺服器實例
app = MCPServer("ai-coach-mcp")

@app.tool()
def parse_activity(file_path: str) -> str:
    """
    解析 Garmin FIT 或 CSV 跑步活動檔案。
    提取總距離、平均配速、心率區間分佈 (Zone 1~5)、各圈 Lap 明細、平均步頻 (SPM)、觸地時間 (GCT) 與垂直振幅。
    
    :param file_path: 本地 .fit 或 .csv 檔案的絕對或相對路徑。
    :return: 包含完整結構化運動科學指標的 JSON 字串。
    """
    result = tools.parse_activity_data(file_path)
    return json.dumps(result, ensure_ascii=False, indent=2)

@app.tool()
def simulate_training_plan(
    target_pace: str,
    intervals_count: int,
    interval_distance_m: int,
    rest_seconds: int,
    current_rpe: int = 5,
    weekly_mileage_km: float = 40.0
) -> str:
    """
    微調與預估間歇訓練課表：
    根據 Edward 專屬生理基線 (Max HR 210, Rest HR 53, LTHR 193)，模擬計算預估心率攀升、
    TRIMP 訓練負荷指數、心率漂移趨勢，並給出路格 (Luger) 量化紅綠燈評定與佩絲 (Pace) 身心恢復建議。
    同時提供可用於繪製互動圖表的數值資料。
    
    :param target_pace: 目標配速字串，例如 "4:30" 或 "5:15"。
    :param intervals_count: 間歇趟數，例如 6。
    :param interval_distance_m: 每趟距離 (公尺)，例如 800 或 1000。
    :param rest_seconds: 每趟間隔休息秒數，例如 90。
    :param current_rpe: 跑者當前自覺疲勞強度 (1-10 分，5 為適中，8 以上為疲勞)。
    :param weekly_mileage_km: 最近週跑量 (km)，預設 40.0。
    :return: 包含負荷預測、路格/佩絲雙重診斷與圖表數值的 JSON 字串。
    """
    result = tools.simulate_interval_plan(
        target_pace_str=target_pace,
        intervals_count=intervals_count,
        interval_distance_m=interval_distance_m,
        rest_seconds=rest_seconds,
        current_rpe=current_rpe,
        weekly_mileage_km=weekly_mileage_km
    )
    return json.dumps(result, ensure_ascii=False, indent=2)

@app.tool()
def get_edward_runner_profile() -> str:
    """
    獲取 Edward 專屬跑者個人生理特質、心率分區定義與核心規則：
    包含 Max HR 210、Rest HR 53、LTHR 193、路格神聖 Zone 2 (148-163 bpm) 標準、
    步頻半頻 x 2 校正規則以及裝備歷史清單。
    
    :return: 包含 Edward 生理基線與教練準則的 JSON 字串。
    """
    profile = tools.get_edward_full_profile()
    return json.dumps(profile, ensure_ascii=False, indent=2)

@app.tool()
def search_race_vault(query: str = "") -> str:
    """
    檢索 Edward 歷年重大賽事實績資料庫 (2022~2025 台北馬、渣打馬、長榮半馬、金門馬、台南古都半馬) 與 MIZUNO 訓練營課表。
    
    :param query: 檢索關鍵字，例如 "台北馬", "fit", "mizuno" 或留空檢索全部。
    :return: 相關檔案列表與元數據的 JSON 字串。
    """
    results = tools.search_race_vault(query=query)
    return json.dumps(results, ensure_ascii=False, indent=2)

@app.tool()
def sync_latest_garmin_activity(folder_override: str = "") -> str:
    """
    自動掃描並取得最新 Garmin 活動檔案：
    優先自動掃描電腦 USB 磁碟上的 Garmin 手錶目錄 (GARMIN/Activity)，
    其次檢索指定的本機同步資料夾。
    
    :param folder_override: 自訂的本機監視資料夾路徑 (例如 Garmin Express 同步目錄)，留空則使用自動偵測。
    :return: 同步結果、檔案路徑與狀態訊息的 JSON 字串。
    """
    fit_path, msg = garmin_local.get_latest_fit(watch_folder=folder_override)
    if not fit_path:
        return json.dumps({"status": "not_found", "message": msg}, ensure_ascii=False)
    
    # 自動調用解析工具輸出摘要
    parsed = tools.parse_activity_data(fit_path)
    return json.dumps({
        "status": "success",
        "message": msg,
        "fit_path": fit_path,
        "activity_summary": parsed
    }, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    # 以標準 stdio 傳輸協議運行 MCP 伺服器
    app.run(transport="stdio")
