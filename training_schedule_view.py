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

SCHEDULE_JSON_PATH = "data/schedule_8weeks.json"

def derive_csv_url_from_sheet_url(sheet_url: str) -> str:
    """
    智慧解析：自動從任何標準 Google 試算表瀏覽網址推導出 CSV 串流匯出網址
    使用者只需貼上瀏覽器網址，系統自動完成串流轉換
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
    
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

def get_gsheet_urls():
    """
    安全解析 Google Sheet 網址
    優先序：1. Session 狀態 (設定介面即時修改) -> 2. Streamlit Secrets -> 3. 本地 keys.json
    防止個人 Google 試算表 ID 外洩至公開 Git 儲存庫
    """
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
    """向 Google 試算表 CSV 串流 API 拉取即時最新課表 (若未設定金鑰則安全略過)"""
    _, csv_url = get_gsheet_urls()
    if not csv_url:
        return []

    try:
        req = urllib.request.Request(csv_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
            
        reader = csv.reader(io.StringIO(content))
        all_rows = list(reader)
        
        schedule = []
        curr_week = None
        
        # 課表從第 16 列 (索引 15) 開始
        for r in all_rows[15:45]:
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
                w_title = lines[0] if len(lines) > 0 else f"第 {len(schedule)+5} 週"
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
            with open(SCHEDULE_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(schedule, f, ensure_ascii=False, indent=2)
                
        return schedule
    except Exception as e:
        return []

@st.cache_data(ttl=180, show_spinner=False)
def get_cached_gsheet_schedule():
    """快取 3 分鐘向 Google Sheet 探詢最新版本，兼具極速流暢與動態同步"""
    return fetch_schedule_from_gsheet(save_local=True)

def load_schedule_data(force_reload=False):
    """
    載入 8 週完整課表：
    1. 支援手動強制刷新 (force_reload=True)
    2. 自動快取連動 Google 試算表 (3 分鐘自動更新)
    3. 離線防護：若斷網自動回退至本地 data/schedule_8weeks.json 備份
    """
    if force_reload:
        st.cache_data.clear()
        fresh = fetch_schedule_from_gsheet(save_local=True)
        if fresh:
            return fresh

    try:
        live = get_cached_gsheet_schedule()
        if live:
            return live
    except Exception:
        pass

    # 離線備用 (Fallback)
    if os.path.exists(SCHEDULE_JSON_PATH):
        try:
            with open(SCHEDULE_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def get_current_week_info(schedule_data):
    """取得當前預設或選定的週次資料 (預設為 Week 5: 10/26 - 11/01)"""
    if not schedule_data:
        return None
    return schedule_data[0]

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
    """側邊欄常駐課表快速摘要卡片 (資訊直觀，直達 Tab 2 與 Google Sheet)"""
    schedule = load_schedule_data()
    curr_week = get_current_week_info(schedule)
    
    st.markdown("#### 📅 2026 台北馬拉松衝刺課表")
    if curr_week:
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.9)); 
                    border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 10px; padding: 10px 12px; margin-bottom: 8px;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <span style='font-size: 0.85rem; font-weight: 700; color: #38bdf8;'>{curr_week['week_title']}</span>
                <span style='font-size: 0.7rem; background: rgba(56,189,248,0.15); color: #7dd3fc; padding: 2px 6px; border-radius: 4px;'>{curr_week['dates']}</span>
            </div>
            <div style='font-size: 0.78rem; color: #cbd5e1; margin-top: 4px; font-weight: 500;'>🎯 焦點：{curr_week['theme']}</div>
            <div style='font-size: 0.75rem; color: #94a3b8; margin-top: 6px; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 6px;'>
                🏃 <strong>下次課表 (週二)：</strong> 社區排酸 4 圈 (5.5K) @ 7:00~7:20
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
    
    if sheet_url:
        col_w, col_sync, col_link = st.columns([0.54, 0.23, 0.23])
    else:
        col_w, col_sync = st.columns([0.72, 0.28])
        col_link = None

    with col_w:
        selected_idx = st.selectbox("切換週次 (預設第 5 週・本週)", range(len(schedule)), format_func=lambda i: week_titles[i], index=0)
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

    # 呈現本週 3 堂關鍵課卡片 (週二、週四、週日)
    workouts = week_data.get("workouts", [])
    cols = st.columns(len(workouts)) if workouts else [st.container()]
    
    icon_map = {"週二": "🏃‍♂️", "週四": "⚡", "週日": "🌊"}
    color_map = {"週二": "#38bdf8", "週四": "#f59e0b", "週日": "#10b981"}

    for idx, w in enumerate(workouts):
        with cols[idx]:
            day = w.get("day", "訓練日")
            icon = icon_map.get(day, "🏃")
            accent = color_map.get(day, "#38bdf8")
            
            st.markdown(f"""
            <div style='background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255,255,255,0.1); 
                        border-top: 3px solid {accent}; border-radius: 10px; padding: 12px 14px; min-height: 260px; height: 100%;'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;'>
                    <span style='font-weight: 700; font-size: 1.05rem; color: #f8fafc;'>{icon} {day}</span>
                    <span style='font-size: 0.72rem; background: rgba(255,255,255,0.08); color: {accent}; padding: 2px 6px; border-radius: 4px; font-weight: bold;'>專項課表</span>
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

            # 產生提問 Prompt (動態帶入當前跑者姓名與生理基線)
            workout_sample = workouts[0].get("workout", "").split("\n")[0] if workouts else "課表訓練"
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
                f"我今日執行的課表為：{workout_sample}。\n"
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

    st.markdown("### 📅 2026 台北馬拉松・8週實戰課表與執行中樞")
    st.caption("結合社區三圈地形模型、河堤平地專項長距離與 Coggan 負荷監控，全盤掌控 8 週破 PB 巔峰節奏。")

    render_schedule_core_content(schedule)
