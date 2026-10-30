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

    # 訪客 Demo 模式：禁止使用個人 Webhook 寫入，保護個人試算表
    try:
        import auth_manager
        if not auth_manager.is_authenticated():
            return ""
    except Exception:
        pass

    try:
        with open("keys.json", "r", encoding="utf-8") as f:
            keys = json.load(f)
            val = keys.get("GOOGLE_SHEET_WEBHOOK_URL", "").strip()
            if val:
                return val
    except Exception:
        pass
    try:
        import streamlit as st
        if "GOOGLE_SHEET_WEBHOOK_URL" in st.secrets:
            return str(st.secrets["GOOGLE_SHEET_WEBHOOK_URL"]).strip()
    except Exception:
        pass
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

def auto_backfill_workout_to_gsheet(
    dist_km=0.0,
    pace_str="—",
    avg_hr="—",
    cadence="—",
    duration_str="",
    score="98 分 (A+ 頂規)",
    target_row=None,
    note="",
    webhook_url=None
):
    """
    智慧自動回填實跑成效至 Google Sheet F 欄
    若未指定 target_row，自動定位當前週次之今日或最近課表
    """
    from datetime import date
    today = date.today()
    date_str = today.strftime("%m/%d")

    if not target_row:
        try:
            import training_schedule_view
            schedule = training_schedule_view.load_schedule_data()
            _, curr_week = training_schedule_view.get_current_week_idx_and_info(schedule)
            if curr_week:
                workouts = curr_week.get("workouts", [])
                cur_weekday = today.weekday()
                # 優先尋找今日課表
                for wo in workouts:
                    d_int = training_schedule_view.DAY_NAME_TO_INT.get(wo.get("day", "")[:2])
                    if d_int == cur_weekday:
                        target_row = wo.get("sheet_row")
                        break
                # 若今日非課表日，尋找最近前期尚未回填之課表
                if not target_row:
                    for wo in workouts:
                        d_int = training_schedule_view.DAY_NAME_TO_INT.get(wo.get("day", "")[:2])
                        if d_int is not None and d_int <= cur_weekday and not wo.get("actual_summary"):
                            target_row = wo.get("sheet_row")
                            break
        except Exception:
            pass

    if not target_row:
        return {"status": "error", "message": "無法自動定位對應之課表列數"}

    dur_part = f" ({duration_str})" if duration_str else ""
    summary_text = f"【{date_str} 實跑驗證】{dist_km:.2f}K{dur_part} @ {pace_str}/km | 均心率 {avg_hr} bpm | 步頻 {cadence} spm"
    if note:
        summary_text += f" ({note})"
    if score:
        summary_text += f" | 評定 {score}"

    res = update_gsheet_cell(sheet_name="2026 賽季", cell=f"F{target_row}", value=summary_text, webhook_url=webhook_url)
    if res.get("status") == "success":
        try:
            import os, json
            if os.path.exists("data/schedule_local.json"):
                with open("data/schedule_local.json", "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                for w in s_data:
                    for wo in w.get("workouts", []):
                        if wo.get("sheet_row") == target_row:
                            wo["actual_summary"] = summary_text
                with open("data/schedule_local.json", "w", encoding="utf-8") as f:
                    json.dump(s_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    return res

if __name__ == "__main__":
    print("Testing sync_to_gsheet module...")
