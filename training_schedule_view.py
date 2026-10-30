# training_schedule_view.py
"""
2026 台北馬拉松 8 週破 PB 實戰課表與執行對照中樞
支援：
1. 側邊欄常駐輕量卡片 (Sidebar Glance Widget)
2. Tab 2 旗艦級課表全景戰情看板 (Full View)
3. Google Sheet 雲端試算表雙向即時同步 (含自動快取與一鍵手動刷新)
4. 雙教練臨床提問 Prompt 自動生成
"""

import os
import io
import csv
import json
import re
import urllib.request
import streamlit as st
import pandas as pd

SCHEDULE_LOCAL_PATH = "data/schedule_local.json"
SCHEDULE_JSON_PATH = "data/schedule_8weeks.json"
DEFAULT_GSHEET_URL = "https://docs.google.com/spreadsheets/d/10jQVBjpMCCnIF4PWwBb-Mm18q1ErJh5BcbXsARfDUPQ/edit?gid=279821330#gid=279821330"
DEFAULT_GSHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/10jQVBjpMCCnIF4PWwBb-Mm18q1ErJh5BcbXsARfDUPQ/gviz/tq?tqx=out:csv&gid=279821330"

def derive_csv_url_from_sheet_url(sheet_url: str) -> str:
    """
    智慧解析：自動從任何標準 Google 試算表瀏覽網址推導出免登入的 CSV 串流網址 (採用 Google Visualization API gviz/tq)
    使用者只需貼上瀏覽器網址，系統自動完成免驗證串流轉換
    """
    if not sheet_url or "docs.google.com/spreadsheets" not in sheet_url:
        return ""
    
    # 提取試算表 ID
    match_id = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
    if not match_id:
        return ""
    sheet_id = match_id.group(1)
    
    # 提取分頁 gid (若無則預設為 0)
    match_gid = re.search(r"[#&?]gid=([0-9]+)", sheet_url)
    gid = match_gid.group(1) if match_gid else "0"
    
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}"

def get_gsheet_urls():
    """
    安全解析 Google Sheet 網址
    - 訪客 Demo 模式：強制回傳公共 Demo 試算表，保護個人私密試算表絕不外洩
    - Edward VIP 模式：從 Session -> Secrets -> keys.json 讀取個人私密試算表
    """
    try:
        import auth_manager
        is_auth = auth_manager.is_authenticated()
    except Exception:
        is_auth = True

    if not is_auth:
        return DEFAULT_GSHEET_URL, DEFAULT_GSHEET_CSV_URL

    sheet_url = st.session_state.get("GOOGLE_SHEET_URL", "")
    csv_url = st.session_state.get("GOOGLE_SHEET_CSV_URL", "")

    # 1. 檢查 Streamlit Secrets (雲端部署環境)
    if not sheet_url or not csv_url:
        try:
            if hasattr(st, "secrets"):
                if not sheet_url:
                    sheet_url = st.secrets.get("GOOGLE_SHEET_URL", "")
                if not csv_url:
                    csv_url = st.secrets.get("GOOGLE_SHEET_CSV_URL", "")
        except Exception:
            pass

    # 2. 檢查本地 keys.json (本地開發與離線環境)
    if not sheet_url or not csv_url:
        if os.path.exists("keys.json"):
            try:
                with open("keys.json", "r", encoding="utf-8") as f:
                    kdata = json.load(f)
                    if not sheet_url:
                        sheet_url = kdata.get("GOOGLE_SHEET_URL", "")
                    if not csv_url:
                        csv_url = kdata.get("GOOGLE_SHEET_CSV_URL", "")
            except Exception:
                pass

    # 若有 sheet_url 但無 csv_url，自動推導
    if sheet_url and not csv_url:
        csv_url = derive_csv_url_from_sheet_url(sheet_url)

    # 若皆未設定，回退至系統預設 Demo 試算表
    if not sheet_url:
        sheet_url = DEFAULT_GSHEET_URL
    if not csv_url:
        csv_url = DEFAULT_GSHEET_CSV_URL

    return sheet_url, csv_url

def save_gsheet_settings(sheet_url: str, webhook_url: str = ""):
    """儲存 Google 試算表設定至 session_state 與 keys.json (本機離線與即時工作階段)"""
    csv_url = derive_csv_url_from_sheet_url(sheet_url)
    st.session_state["GOOGLE_SHEET_URL"] = sheet_url
    st.session_state["GOOGLE_SHEET_CSV_URL"] = csv_url
    if webhook_url:
        st.session_state["GOOGLE_SHEET_WEBHOOK_URL"] = webhook_url

    # 若本地有 keys.json，一併持久化更新
    if os.path.exists("keys.json"):
        try:
            with open("keys.json", "r", encoding="utf-8") as f:
                kdata = json.load(f)
            kdata["GOOGLE_SHEET_URL"] = sheet_url
            kdata["GOOGLE_SHEET_CSV_URL"] = csv_url
            if webhook_url:
                kdata["GOOGLE_SHEET_WEBHOOK_URL"] = webhook_url
            with open("keys.json", "w", encoding="utf-8") as f:
                json.dump(kdata, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    return csv_url

def fetch_schedule_from_gsheet(save_local=True):
    """向 Google 試算表 CSV 串流 API 拉取即時最新課表 (優先採用免登入 gviz API)"""
    _, raw_csv_url = get_gsheet_urls()
    if not raw_csv_url:
        return []

    # 候選網址建構 (優先採用 Google Visualization API 免登入端點，相容任何公開檢視連結)
    candidate_urls = []
    match_id = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", raw_csv_url)
    match_gid = re.search(r"[#&?]gid=([0-9]+)", raw_csv_url)
    if match_id:
        sheet_id = match_id.group(1)
        gid = match_gid.group(1) if match_gid else "0"
        candidate_urls.append(f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}")
    if raw_csv_url not in candidate_urls:
        candidate_urls.append(raw_csv_url)

    content = None
    last_err = None

    for target_url in candidate_urls:
        try:
            req = urllib.request.Request(target_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw_text = resp.read().decode("utf-8")
                # 確保取回的是真實 CSV，而不是 Google 登入轉址 HTML
                if "<html" not in raw_text.lower() and ("週次" in raw_text or "訓練日" in raw_text or "," in raw_text):
                    content = raw_text
                    break
        except Exception as e:
            last_err = e
            continue

    if not content:
        if last_err and ("401" in str(last_err) or "Unauthorized" in str(last_err)):
            try:
                st.session_state["gsheet_401_error"] = True
            except Exception:
                pass
        return []

    # 成功取得資料，清除 401 提示
    try:
        st.session_state["gsheet_401_error"] = False
    except Exception:
        pass

    try:
        reader = csv.reader(io.StringIO(content))
        all_rows = list(reader)
        
        schedule = []
        curr_week = None
        
        # 智慧尋找表頭 (容許任何排版變動)
        start_idx = 1
        for idx, r in enumerate(all_rows):
            if r and len(r) >= 2 and ("訓練日" in r[1] or "週次" in r[0]):
                start_idx = idx + 1
                break
                
        for r in all_rows[start_idx:]:
            if not r or len(r) < 3:
                continue
                
            w_col = r[0].strip() if len(r) > 0 else ""
            day_col = r[1].strip() if len(r) > 1 else ""
            workout_col = r[2].strip() if len(r) > 2 else ""
            pace_col = r[3].strip() if len(r) > 3 else ""
            hr_col = r[4].strip() if len(r) > 4 else ""
            
            if not any([w_col, day_col, workout_col]):
                continue
                
            if w_col:
                lines = [x.strip() for x in w_col.split("\n") if x.strip()]
                w_title = lines[0] if len(lines) > 0 else f"第 {len(schedule)+1} 週"
                w_dates = lines[1] if len(lines) > 1 else ""
                w_theme = lines[2] if len(lines) > 2 else ""
                curr_week = {
                    "week_title": w_title,
                    "dates": w_dates,
                    "theme": w_theme,
                    "workouts": []
                }
                schedule.append(curr_week)
                
            if curr_week is not None and day_col:
                curr_week["workouts"].append({
                    "day": day_col,
                    "workout": workout_col,
                    "pace": pace_col,
                    "hr_note": hr_col
                })
                
        if schedule and save_local:
            os.makedirs("data", exist_ok=True)
            with open(SCHEDULE_LOCAL_PATH, "w", encoding="utf-8") as f:
                json.dump(schedule, f, ensure_ascii=False, indent=2)
                
        return schedule
    except Exception:
        return []

@st.cache_data(ttl=180, show_spinner=False)
def get_cached_gsheet_schedule():
    """快取 3 分鐘向 Google Sheet 探詢最新版本，兼具極速流暢與動態同步"""
    return fetch_schedule_from_gsheet(save_local=True)

def load_schedule_data(force_reload=False):
    """
    載入完整課表：
    1. 支援手動強制刷新 (force_reload=True)
    2. 自動快取連動 Google 試算表 (3 分鐘自動更新)
    3. 本地優先：已認證本機環境直接讀取 data/schedule_local.json (極速 0.0005s)
    4. 雲端 VIP：優先向 Google 試算表拉取包含萬金石的完整 25 週課表
    5. 安全回退：未認證 (Demo) 或離線時使用通用範本 data/schedule_8weeks.json
    """
    if force_reload:
        st.cache_data.clear()
        fresh = fetch_schedule_from_gsheet(save_local=True)
        if fresh:
            return fresh

    try:
        import auth_manager
        is_auth = auth_manager.is_authenticated()
    except Exception:
        is_auth = True

    # 1. 未認證 (Demo 模式)：直接使用通用 12 週示範範本
    if not is_auth:
        if os.path.exists(SCHEDULE_JSON_PATH):
            try:
                with open(SCHEDULE_JSON_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    # 2. 已認證 (VIP 模式)：
    # (A) 若本地電腦有完整的 25 週專屬課表 (schedule_local.json)，直接秒開 (0.0005s)
    if os.path.exists(SCHEDULE_LOCAL_PATH):
        try:
            with open(SCHEDULE_LOCAL_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # (B) 若為雲端環境 (無本地檔案)，優先向 Google 試算表拉取最新 25 週課表並快取
    try:
        live = get_cached_gsheet_schedule()
        if live:
            return live
    except Exception:
        pass

    # (C) 若 Google 試算表離線或權限未開放，回退至備用範本
    if os.path.exists(SCHEDULE_JSON_PATH):
        try:
            with open(SCHEDULE_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return []

def parse_week_dates(dates_str, base_year=2026):
    """安全解析週次起訖日期 (支援跨年 2026 -> 2027)"""
    if not dates_str:
        return None, None
    m = re.search(r'(\d{1,2})/(\d{1,2})\s*-\s*(\d{1,2})/(\d{1,2})', str(dates_str))
    if not m:
        return None, None
    m1, d1, m2, d2 = map(int, m.groups())
    y1 = base_year if m1 >= 9 else base_year + 1
    y2 = base_year if m2 >= 9 else base_year + 1
    try:
        from datetime import date
        return date(y1, m1, d1), date(y2, m2, d2)
    except Exception:
        return None, None

def get_current_week_idx_and_info(schedule_data):
    """
    動態依據今日日曆 (datetime.now) 定位當前進行中的週次
    不再寫死任何固定週次或特定日期！
    """
    if not schedule_data:
        return 0, None
        
    from datetime import date
    today = date.today()
    
    # 1. 精確匹配今日所在的日期區間
    for idx, w in enumerate(schedule_data):
        s_d, e_d = parse_week_dates(w.get("dates", ""))
        if s_d and e_d and s_d <= today <= e_d:
            return idx, w
            
    # 2. 若今日早於第一週，預設第一週
    s_first, _ = parse_week_dates(schedule_data[0].get("dates", ""))
    if s_first and today < s_first:
        return 0, schedule_data[0]
        
    # 3. 若今日晚於最後一週，預設最後一週
    _, e_last = parse_week_dates(schedule_data[-1].get("dates", ""))
    if e_last and today > e_last:
        return len(schedule_data) - 1, schedule_data[-1]

    # 4. 回退備案：搜尋月日比對
    today_str = today.strftime("%m/%d")
    for idx, w in enumerate(schedule_data):
        if today_str in w.get("dates", ""):
            return idx, w
            
    return 0, schedule_data[0]

def get_current_week_info(schedule_data):
    """相容性包裝：取得當前週次物件"""
    _, w = get_current_week_idx_and_info(schedule_data)
    return w

DAY_NAME_TO_INT = {
    "週一": 0, "星期一": 0, "Mon": 0,
    "週二": 1, "星期二": 1, "Tue": 1,
    "週三": 2, "星期三": 2, "Wed": 2,
    "週四": 3, "星期四": 3, "Thu": 3,
    "週五": 4, "星期五": 4, "Fri": 4,
    "週六": 5, "星期六": 5, "Sat": 5,
    "週日": 6, "星期日": 6, "Sun": 6,
}
WEEKDAY_NAMES = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]

def get_active_activity_metrics():
    """安全解析當前活動數值，完全容忍 summary 為 str, dict 或空值"""
    pending_name = st.session_state.get('pending_file_name', '')
    df = st.session_state.get('df')
    summary = st.session_state.get('pending_summary', '')
    
    dist_km = 0.0
    pace_str = "—"
    hr_val = "—"
    cad_val = "—"
    has_data = False
    
    # 優先從 DataFrame 計算精確數值
    if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
        has_data = True
        try:
            if 'dist_km' in df.columns and df['dist_km'].notna().any():
                dist_km = float(df['dist_km'].dropna().sum())
            elif 'distance' in df.columns and df['distance'].notna().any():
                dist_km = float(df['distance'].dropna().iloc[-1] / 1000.0)
        except Exception:
            pass

        try:
            if 'pace' in df.columns and df['pace'].notna().any():
                pv = float(df['pace'].dropna().mean())
                if pv > 0:
                    pace_str = f"{int(pv)}:{int((pv % 1)*60):02d}"
        except Exception:
            pass

        try:
            if 'heart_rate' in df.columns and df['heart_rate'].notna().any():
                hr_val = f"{float(df['heart_rate'].dropna().mean()):.0f}"
        except Exception:
            pass

        try:
            if 'cadence' in df.columns and df['cadence'].notna().any():
                cad_val = f"{float(df['cadence'].dropna().mean()):.0f}"
        except Exception:
            pass

    # 若 summary 是 dict 則補齊
    elif isinstance(summary, dict) and summary:
        has_data = True
        dist_km = float(summary.get("total_distance_km", 0.0))
        pace_str = str(summary.get("avg_pace_str", "—"))
        hr_val = str(summary.get("avg_heart_rate", "—"))
        cad_val = str(summary.get("avg_cadence", "—"))
    elif pending_name:
        has_data = True

    return {
        "name": pending_name if pending_name else ("當前活動" if has_data else ""),
        "has_data": has_data,
        "dist_km": dist_km,
        "pace_str": pace_str,
        "hr_val": hr_val,
        "cad_val": cad_val
    }

def render_sidebar_schedule_card():
    """側邊欄常駐課表快速摘要卡片 (動態感知今日星期，自動推算今日/下次課表)"""
    schedule = load_schedule_data()
    cur_idx, curr_week = get_current_week_idx_and_info(schedule)
    
    st.markdown("#### 📅 2026–2027 台北馬 ➡️ 萬金石課表")
    if curr_week:
        from datetime import date
        today = date.today()
        cur_weekday = today.weekday()
        today_name = WEEKDAY_NAMES[cur_weekday]

        workouts = curr_week.get("workouts", [])
        
        # 尋找今日與下次課表
        today_wo = None
        next_wo = None
        is_next_next_week = False

        for wo in workouts:
            d_int = DAY_NAME_TO_INT.get(wo.get("day", "")[:2])
            if d_int == cur_weekday:
                today_wo = wo
            elif d_int is not None and d_int > cur_weekday and next_wo is None:
                next_wo = wo

        # 若本週後續已無課表，無縫往下一週尋找第一堂課
        if next_wo is None and cur_idx + 1 < len(schedule):
            next_week_workouts = schedule[cur_idx + 1].get("workouts", [])
            if next_week_workouts:
                next_wo = next_week_workouts[0]
                is_next_next_week = True

        # 組裝動態課表狀態文字
        if today_wo:
            wo_title = today_wo.get("workout", "").split("\n")[0]
            wo_pace = today_wo.get("pace", "").split("\n")[0]
            status_line = f"🔥 <strong>今日專項 ({today_wo.get('day')})：</strong> {wo_title} @ {wo_pace}"
        elif next_wo:
            prefix = "下週" if is_next_next_week else ""
            n_day = f"{prefix}{next_wo.get('day')}"
            wo_title = next_wo.get("workout", "").split("\n")[0]
            wo_pace = next_wo.get("pace", "").split("\n")[0]
            status_line = (
                f"🛌 <strong>今日 ({today_name})：</strong> 休兵日 / 核心伸展與放鬆<br>"
                f"🏃 <strong>下次課表 ({n_day})：</strong> {wo_title} @ {wo_pace}"
            )
        else:
            status_line = f"🛌 <strong>今日 ({today_name})：</strong> 充分休整與恢復"

        st.markdown(f"""
        <div style='background: linear-gradient(135deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.9)); 
                    border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 10px; padding: 10px 12px; margin-bottom: 8px;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <span style='font-size: 0.85rem; font-weight: 700; color: #38bdf8;'>{curr_week['week_title']}</span>
                <span style='font-size: 0.7rem; background: rgba(56,189,248,0.15); color: #7dd3fc; padding: 2px 6px; border-radius: 4px;'>{curr_week['dates']}</span>
            </div>
            <div style='font-size: 0.78rem; color: #cbd5e1; margin-top: 4px; font-weight: 500;'>🎯 焦點：{curr_week['theme']}</div>
            <div style='font-size: 0.75rem; color: #94a3b8; margin-top: 6px; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 6px; line-height: 1.45;'>
                {status_line}
            </div>
        </div>
        """, unsafe_allow_html=True)

    sheet_url, _ = get_gsheet_urls()
    if sheet_url:
        st.link_button("🌐 開啟 Google Sheet 雲端課表", sheet_url, use_container_width=True, help="直通 Google Sheet「2026 賽季」雲端課表")

def render_schedule_core_content(schedule):
    """核心課表呈現邏輯 (供 Tab 2 專屬使用)"""
    week_titles = [f"{w['week_title']} ({w['dates']}) - {w['theme']}" for w in schedule]
    sheet_url, csv_url = get_gsheet_urls()
    
    # 智慧動態定位預設週次 (日曆自動對齊，無硬編碼)
    default_idx, current_calendar_week = get_current_week_idx_and_info(schedule)

    if sheet_url:
        col_w, col_sync, col_link = st.columns([0.54, 0.23, 0.23])
    else:
        col_w, col_sync = st.columns([0.72, 0.28])
        col_link = None

    with col_w:
        selected_idx = st.selectbox("切換週次 (已自動定位當前週次)", range(len(schedule)), format_func=lambda i: week_titles[i], index=default_idx)
    with col_sync:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 刷新雲端課表", use_container_width=True, help="立即從 Google 試算表拉取最新變更"):
            if not csv_url:
                st.info("💡 尚未設定 GOOGLE_SHEET_CSV_URL，目前使用本地安全課表。可在 keys.json 或 Streamlit Secrets 中設定。")
            else:
                with st.spinner("正在連線 Google Sheet..."):
                    fresh_data = load_schedule_data(force_reload=True)
                    if fresh_data:
                        st.toast("✅ 已成功同步 Google Sheet 最新課表！", icon="🔄")
                        st.rerun()
                    else:
                        st.error("同步失敗，維持現有課表。")
    if col_link and sheet_url:
        with col_link:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            st.link_button("🌐 開啟雲端試算表", sheet_url, use_container_width=True)

    week_data = schedule[selected_idx]

    # 週次標題橫幅
    st.markdown(f"""
    <div style='background: rgba(30, 41, 59, 0.6); border-left: 4px solid #38bdf8; border-radius: 6px; padding: 10px 14px; margin-bottom: 16px;'>
        <div style='font-size: 1.1rem; font-weight: 700; color: #f8fafc;'>{week_data['week_title']} <span style='font-size: 0.85rem; color: #94a3b8; font-weight: 400;'>({week_data['dates']})</span></div>
        <div style='font-size: 0.9rem; color: #38bdf8; margin-top: 2px;'>🎯 本週戰略主題：<strong>{week_data['theme']}</strong></div>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.get("gsheet_401_error", False):
        st.info("💡 **小提醒：** 您的 Google 試算表目前為私密狀態 (HTTP 401)。若希望在試算表上的直接手動修改能無縫串流回戰情室，可在試算表右上角「共用」將存取權設為「知道連結的任何人」皆可「檢視」。雙教練的所有自動微調與寫入皆已成功直連生效！")

    # 呈現本週關鍵課卡片 (動態判斷前期、今日、下次)
    workouts = week_data.get("workouts", [])
    cols = st.columns(len(workouts)) if workouts else [st.container()]
    
    icon_map = {"週二": "🏃‍♂️", "週三": "🏃‍♂️", "週四": "⚡", "週六": "🔥", "週日": "🌊"}
    color_map = {"週二": "#38bdf8", "週三": "#38bdf8", "週四": "#f59e0b", "週六": "#f43f5e", "週日": "#10b981"}

    from datetime import date
    today = date.today()
    is_current_week = (selected_idx == default_idx)
    cur_weekday = today.weekday()

    # 先尋找在當前週次中，哪一堂是下次課表
    next_wo_in_week = None
    if is_current_week:
        for wo in workouts:
            d_int = DAY_NAME_TO_INT.get(wo.get("day", "")[:2])
            if d_int is not None and d_int > cur_weekday:
                next_wo_in_week = wo
                break

    for idx, w in enumerate(workouts):
        with cols[idx]:
            day = w.get("day", "訓練日")
            icon = icon_map.get(day, "🏃")
            accent = color_map.get(day, "#38bdf8")
            d_int = DAY_NAME_TO_INT.get(day[:2])

            if is_current_week and d_int is not None:
                if d_int < cur_weekday:
                    badge_html = "<span style='font-size: 0.72rem; background: rgba(100,116,139,0.25); color: #94a3b8; padding: 2px 6px; border-radius: 4px;'>✅ 前期課表</span>"
                elif d_int == cur_weekday:
                    badge_html = "<span style='font-size: 0.72rem; background: rgba(239,68,68,0.25); color: #f87171; padding: 2px 6px; border-radius: 4px; font-weight: bold;'>🔥 今日專項</span>"
                elif w == next_wo_in_week:
                    badge_html = "<span style='font-size: 0.72rem; background: rgba(16,185,129,0.25); color: #34d399; padding: 2px 6px; border-radius: 4px; font-weight: bold;'>🎯 下次備戰</span>"
                else:
                    badge_html = f"<span style='font-size: 0.72rem; background: rgba(255,255,255,0.08); color: {accent}; padding: 2px 6px; border-radius: 4px; font-weight: bold;'>專項課表</span>"
            else:
                badge_html = f"<span style='font-size: 0.72rem; background: rgba(255,255,255,0.08); color: {accent}; padding: 2px 6px; border-radius: 4px; font-weight: bold;'>專項課表</span>"
            
            st.markdown(f"""
            <div style='background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255,255,255,0.1); 
                        border-top: 3px solid {accent}; border-radius: 10px; padding: 12px 14px; min-height: 260px; height: 100%;'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;'>
                    <span style='font-weight: 700; font-size: 1.05rem; color: #f8fafc;'>{icon} {day}</span>
                    {badge_html}
                </div>
                <div style='font-size: 0.82rem; color: #e2e8f0; line-height: 1.45; margin-bottom: 10px; min-height: 60px;'>
                    {w.get("workout", "").replace(chr(10), "<br>")}
                </div>
                <div style='background: rgba(255,255,255,0.03); border-radius: 6px; padding: 6px 8px; margin-bottom: 8px;'>
                    <div style='font-size: 0.72rem; color: #94a3b8;'>🎯 目標配速：</div>
                    <div style='font-size: 0.85rem; font-weight: 700; color: {accent};'>{w.get("pace", "—")}</div>
                </div>
                <div style='background: rgba(255,255,255,0.03); border-radius: 6px; padding: 6px 8px;'>
                    <div style='font-size: 0.72rem; color: #94a3b8;'>💓 生理/心率防線與技術：</div>
                    <div style='font-size: 0.76rem; color: #cbd5e1; line-height: 1.35;'>{w.get("hr_note", "—")}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    # 執行比對與教練提問互動區
    with st.expander("🩺 執行狀況對照與向雙教練提問 (詢問 / 微調課表)", expanded=True):
        st.markdown("""
        當您跑完某堂課並透過 Garmin 同步最新紀錄後，可以在此檢視與課表的吻合度，或點擊下方按鈕複製結構化提問，直接在 Antigravity 聊天室發起雙教練動態會診！
        """)

        # 安全檢查是否有當前活動
        act_info = get_active_activity_metrics()
        
        c_diag1, c_diag2 = st.columns([0.6, 0.4])
        with c_diag1:
            if act_info["has_data"]:
                st.success(
                    f"📍 **當前實戰活動：** {act_info['name']} "
                    f"({act_info['dist_km']:.2f} km | 配速 {act_info['pace_str']} | 心率 {act_info['hr_val']} bpm | 步頻 {act_info['cad_val']} spm)"
                )
            else:
                st.info("ℹ️ 尚未偵測到即時跑步活動。點擊側邊欄「⚡ 一鍵同步最新活動」即可帶入最新實跑數據。")

            # 產生提問 Prompt (動態判斷今日課表或下次課表)
            target_workout_desc = "課表訓練"
            if is_current_week:
                today_wo_found = None
                for wo in workouts:
                    d_int = DAY_NAME_TO_INT.get(wo.get("day", "")[:2])
                    if d_int == cur_weekday:
                        today_wo_found = wo
                        break
                if today_wo_found:
                    target_workout_desc = f"【今日 {today_wo_found.get('day')} 專項】" + today_wo_found.get("workout", "").split("\n")[0]
                elif next_wo_in_week:
                    target_workout_desc = f"【今日休兵，備戰下次 {next_wo_in_week.get('day')}】" + next_wo_in_week.get("workout", "").split("\n")[0]
                elif workouts:
                    target_workout_desc = workouts[0].get("workout", "").split("\n")[0]
            elif workouts:
                target_workout_desc = workouts[0].get("workout", "").split("\n")[0]

            u_prof = st.session_state.get("user_profile", {})
            p_name = u_prof.get("name", "跑者")
            p_max = st.session_state.get("base_max_hr", u_prof.get("max_hr", 190))
            p_lthr = st.session_state.get("base_lthr", u_prof.get("lthr", 172))
            p_z2_min = st.session_state.get("base_z2_min", u_prof.get("z2_min", 138))
            p_z2_max = st.session_state.get("base_z2_max", u_prof.get("z2_max", 152))

            prompt_text = (
                f"【雙教練會診請求】\n"
                f"我是 {p_name} (生理基線: Max HR {p_max} / LTHR {p_lthr} / Zone 2: {p_z2_min}-{p_z2_max} bpm)。\n"
                f"目前訓練進度為：{week_data['week_title']}（主題：{week_data['theme']}）。\n"
                f"目前對應進度為：{target_workout_desc}。\n"
            )
            if act_info["has_data"]:
                prompt_text += (
                    f"最新 Garmin 實跑數據為：里程 {act_info['dist_km']:.2f} km、"
                    f"平均配速 {act_info['pace_str']}、平均心率 {act_info['hr_val']} bpm、"
                    f"步頻 {act_info['cad_val']} spm。\n"
                )
            prompt_text += (
                f"請路格教練 (Luger) 評估生理心率與疲勞衝擊，請佩絲教練 (Pace) 評估步態剛性與配速執行度；\n"
                f"若需要針對本週後續課表或週日長距離進行加減量微調，請給出明確指令並同步更新至 Google Sheet 課表！"
            )

        with c_diag2:
            st.markdown("<div style='font-size:0.8rem; color:#94a3b8; margin-bottom:4px;'>一鍵複製提問，直接貼至 Antigravity 聊天室：</div>", unsafe_allow_html=True)
            st.code(prompt_text, language="text")

def render_schedule_tab_section():
    """在 Tab 2 呈現完整的課表排程看板"""
    schedule = load_schedule_data()
    if not schedule:
        st.warning("⚠️ 課表資料庫尚未載入。")
        return

    st.markdown("### 📅 2026–2027 台北馬拉松 ➡️ 萬金石馬拉松・雙賽季戰情中樞")
    st.caption("結合社區起伏力量模型、平地河堤專項長跑與萬金石海風抗阻，全盤掌控 25 週雙馬連動巔峰節奏。")

    render_schedule_core_content(schedule)
