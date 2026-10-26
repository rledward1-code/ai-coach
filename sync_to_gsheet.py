# sync_to_gsheet.py
"""
將跑步賽事實績與課表自動同步寫入 Google 試算表 (支援多列批次寫入、單一儲存格更新、刪除列)
"""

import sys
import json
import requests

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def get_webhook_url(override_url=None):
    if override_url:
        return override_url
    try:
        with open("keys.json", "r", encoding="utf-8") as f:
            keys = json.load(f)
            return keys.get("GOOGLE_SHEET_WEBHOOK_URL", "")
    except Exception:
        return ""

def _send_payload(payload, webhook_url=None):
    url = get_webhook_url(webhook_url)
    if not url:
        return {"status": "error", "message": "keys.json 中找不到 GOOGLE_SHEET_WEBHOOK_URL"}
    try:
        r = requests.post(url, json=payload, timeout=25)
        if r.status_code == 200:
            try:
                return r.json()
            except Exception:
                return {"status": "success", "data": r.text}
        elif r.status_code == 401:
            return {
                "status": "error",
                "code": 401,
                "message": "Google 權限不足 (401)：請在 Apps Script 部署設定中將「誰可以存取」改為「所有人 (Anyone)」。"
            }
        else:
            return {
                "status": "error",
                "code": r.status_code,
                "message": f"HTTP {r.status_code}: {r.text[:200]}"
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def sync_activity_to_gsheet(
    activity_name="2026.10 長榮馬",
    finish_time="2:01:08",
    avg_pace="5:41",
    avg_hr=186,
    max_hr=198,
    cadence=185,
    gct=237,
    vertical_osc=7.1,
    ascent=35,
    shoes="Pro4",
    rank_pct="",
    temperature="24°C 至 28°C",
    section="half",
    webhook_url=None
):
    """向下相容：同步單次賽事完賽紀錄至【成績】工作表"""
    payload = {
        "sheet_name": "成績",
        "section": section,
        "row": [
            activity_name,
            finish_time,
            avg_pace,
            avg_hr,
            max_hr,
            cadence,
            gct,
            vertical_osc,
            ascent,
            shoes,
            rank_pct,
            temperature
        ]
    }
    return _send_payload(payload, webhook_url)

def update_gsheet_cell(sheet_name="2026 賽季", cell=None, row=None, col=None, value="", webhook_url=None):
    """修改特定儲存格 (例如 cell='C20' 或 row=20, col=3)"""
    payload = {
        "action": "update_cell",
        "sheet_name": sheet_name,
        "value": value
    }
    if cell:
        payload["cell"] = cell
    else:
        payload["row"] = row
        payload["col"] = col
    return _send_payload(payload, webhook_url)

def update_gsheet_range(sheet_name="2026 賽季", start_row=16, start_col=1, values=None, webhook_url=None):
    """多列多欄批次寫入 (例如寫入 8 週課表 values 2D 陣列)"""
    if not values:
        return {"status": "error", "message": "values 不能為空"}
    payload = {
        "action": "set_range",
        "sheet_name": sheet_name,
        "start_row": start_row,
        "start_col": start_col,
        "values": values
    }
    return _send_payload(payload, webhook_url)

def delete_gsheet_row(sheet_name="2026 賽季", row_index=40, webhook_url=None):
    """刪除指定資料列 (例如刪除多餘的測試列)"""
    payload = {
        "action": "delete_row",
        "sheet_name": sheet_name,
        "row_index": row_index
    }
    return _send_payload(payload, webhook_url)

def clear_gsheet_range(sheet_name="2026 賽季", range_str="A16:E50", webhook_url=None):
    """清除特定範圍內容"""
    payload = {
        "action": "clear_range",
        "sheet_name": sheet_name,
        "range": range_str
    }
    return _send_payload(payload, webhook_url)

if __name__ == "__main__":
    print("Testing sync_to_gsheet module...")
