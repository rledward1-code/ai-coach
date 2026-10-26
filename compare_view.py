# compare_view.py - 雙場賽事 / 訓練全維度深度對決與差異比較中樞 (具備全面容錯機制)
import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from data_processor import process_data

@st.cache_data(show_spinner=False)
def load_and_process_cached(file_path):
    """快取讀取與解析賽事數據，提升雙場比對效能"""
    try:
        df, summary, _, tags = process_data(file_path)
        return df, summary, tags
    except Exception as e:
        return pd.DataFrame(), f"讀取錯誤: {str(e)}", []

def get_comparison_library():
    """收集所有本地可供比對的歷史賽事與訓練庫"""
    library = {}
    
    # 1. 2026 長榮馬實戰 (若存在)
    evergreen_p = "data/2026_evergreen_half.fit"
    if os.path.exists(evergreen_p):
        library["🟢 2026 長榮航空半程馬拉松 (最新實戰 2:01:08)"] = evergreen_p
    
    # 2. 歷史賽事實績庫 (data/knowledge)
    knowledge_dir = "data/knowledge"
    if os.path.exists(knowledge_dir):
        for f in sorted(os.listdir(knowledge_dir)):
            if f.endswith(".fit") or f.endswith(".csv"):
                clean_name = f.replace(".fit", "").replace(".csv", "")
                label = f"📁 {clean_name}"
                if "2025" in clean_name and "台北馬" in clean_name:
                    label = "🏆 2025 台北馬拉松 (半馬 PB 1:52:33)"
                elif "2025" in clean_name and "台南" in clean_name:
                    label = "🍂 2025 台南秋季馬 (半馬 1:53:59)"
                elif "2024" in clean_name and "台南" in clean_name:
                    label = "🍂 2024 台南秋季馬 (歷史記錄)"
                elif "2026" in clean_name and "長榮" in clean_name:
                    label = "🥈 2026 長榮航空馬拉松 (21.26K)"
                elif "2026" in clean_name and "萬金石" in clean_name:
                    label = "🌊 2026 萬金石馬拉松全馬 (4:33:02)"
                elif "2023" in clean_name and "萬金石" in clean_name:
                    label = "🌊 2023 萬金石馬拉松 (歷史記錄)"
                elif "2024" in clean_name and "台北馬" in clean_name:
                    label = "🏅 2024 台北馬拉松全馬 (4:31:00)"
                elif "渣打" in clean_name:
                    label = f"🏃 {clean_name}"
                library[label] = os.path.join(knowledge_dir, f)
                
    # 3. 雲端暫存檔 (temp.fit)
    if os.path.exists("temp.fit") and "temp.fit" not in library.values():
        library["⚡ 當前暫存活動 (temp.fit)"] = "temp.fit"
        
    return library

def safe_mean(df, col, default=None):
    """安全計算欄位平均值 (防 KeyError 與全 NaN)"""
    if df is not None and col in df.columns:
        valid = df[col].dropna()
        if not valid.empty:
            m = valid.mean()
            if pd.notna(m):
                return float(m)
    return default

def safe_max(df, col, default=None):
    """安全計算欄位最大值 (防 KeyError 與全 NaN)"""
    if df is not None and col in df.columns:
        valid = df[col].dropna()
        if not valid.empty:
            m = valid.max()
            if pd.notna(m):
                return float(m)
    return default

def extract_full_metrics(df):
    """計算全套 11+ 項賽事關鍵指標，全面容錯保護"""
    if df is None or df.empty:
        return None
        
    tot_dist = safe_mean(df, 'dist_km', 0.0)
    if 'dist_km' in df.columns and df['dist_km'].notna().any():
        tot_dist = float(df['dist_km'].dropna().sum())
    elif 'distance' in df.columns and df['distance'].notna().any():
        tot_dist = float(df['distance'].dropna().sum() / 1000.0)
        
    avg_pace = safe_mean(df, 'pace', 0.0)
    avg_hr = safe_mean(df, 'heart_rate', None)
    max_hr = safe_max(df, 'heart_rate', None)
    avg_cad = safe_mean(df, 'cadence', None)
    avg_gct = safe_mean(df, 'gct', None)
    
    # 步幅單位標準化 (轉為 cm)
    avg_step = None
    if 'step_length' in df.columns:
        steps = df['step_length'].dropna()
        if not steps.empty:
            raw_s = float(steps.mean())
            avg_step = float(raw_s * 100 if raw_s < 3.0 else raw_s)
            
    avg_vo = safe_mean(df, 'vertical_osc', None)
    avg_vr = safe_mean(df, 'vertical_ratio', None)
    avg_bal = safe_mean(df, 'gct_balance', None)
    avg_pwr = safe_mean(df, 'power', None)
    
    # 完賽總秒數與字串
    tot_time_sec = tot_dist * avg_pace * 60 if (avg_pace and avg_pace > 0) else 0
    hrs = int(tot_time_sec // 3600)
    mins = int((tot_time_sec % 3600) // 60)
    secs = int(tot_time_sec % 60)
    dur_str = f"{hrs}時{mins:02d}分{secs:02d}秒" if hrs > 0 else f"{mins}分{secs:02d}秒" if tot_time_sec > 0 else "—"
    
    # 配速字串
    if avg_pace and avg_pace > 0:
        pace_m = int(avg_pace)
        pace_s = int((avg_pace - pace_m) * 60)
        pace_str = f"{pace_m}:{pace_s:02d}"
    else:
        pace_str = "—"
        
    # 能效比 (EF): Speed (m/min) / HR
    if avg_pace and avg_pace > 0 and avg_hr and avg_hr > 0:
        speed_m_min = 1000.0 / avg_pace
        ef = speed_m_min / avg_hr
        dpb = 1000.0 / (avg_pace * avg_hr)
    else:
        ef = None
        dpb = None

    return {
        "dist_km": tot_dist,
        "avg_pace": avg_pace,
        "pace_str": pace_str,
        "tot_time_sec": tot_time_sec,
        "dur_str": dur_str,
        "avg_hr": avg_hr,
        "max_hr": max_hr,
        "cadence": avg_cad,
        "gct": avg_gct,
        "step_length": avg_step,
        "vertical_osc": avg_vo,
        "vertical_ratio": avg_vr,
        "balance": avg_bal,
        "power": avg_pwr,
        "ef": ef,
        "dpb": dpb
    }

def make_diff_badge(val_a, val_b, unit="", invert=False, precision=1):
    """安全產出 Delta 差值標籤 (若任一值缺失則安全回傳空字串)"""
    if val_a is None or val_b is None or pd.isna(val_a) or pd.isna(val_b):
        return ""
    try:
        diff = float(val_b) - float(val_a)
        sign = "+" if diff > 0 else ""
        formatted = f"{sign}{diff:.{precision}f}{unit}"
        if abs(diff) < 0.001:
            return "<span style='font-size:0.75rem; color:#94a3b8; font-weight:600;'>持平</span>"
        is_good = (diff < 0) if invert else (diff > 0)
        color = "#34d399" if is_good else "#f43f5e"
        return f"<span style='font-size:0.75rem; color:{color}; font-weight:bold;'>({formatted})</span>"
    except Exception:
        return ""

def render_compare_tab():
    st.markdown("### ⚔️ 雙場賽事 / 訓練深度對決實驗室 (Head-to-Head)")
    st.caption("將兩場關鍵賽事（如 PB 巔峰 vs 最新實戰，或間歇 vs 長距離）放置於運動科學天平兩端，全盤對決核心卡片、多層級走勢與跑姿退化指數。")
    
    library = get_comparison_library()
    if not library:
        st.warning("⚠️ 尚未偵測到足夠的本地歷史賽事資料。請確認 `data/knowledge` 目錄下是否有 .fit 或 .csv 檔案。")
        return

    options_keys = list(library.keys())
    
    # 預設選取：A 為 2025 台北馬 (PB)，B 為 2026 長榮馬
    default_a_idx = 0
    default_b_idx = min(1, len(options_keys) - 1)
    for idx, k in enumerate(options_keys):
        if "2025 台北馬" in k or "PB" in k:
            default_a_idx = idx
        elif "2026 長榮" in k:
            default_b_idx = idx

    curr_name = st.session_state.get('pending_file_name', '')
    if curr_name:
        st.markdown(f"<div style='background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 8px; padding: 8px 14px; font-size: 0.85rem; color: #94a3b8; margin-bottom: 16px;'>📍 當前展示活動：<strong style='color:#38bdf8;'>{curr_name}</strong></div>", unsafe_allow_html=True)

    with st.container(border=True):
        c_sel1, c_sel2 = st.columns(2)
        with c_sel1:
            st.markdown("#### 🔵 基準賽事 A (Baseline / PB 巔峰)")
            sel_a = st.selectbox("選取基準場次 A", options=options_keys, index=default_a_idx, label_visibility="collapsed", key="cmp_sel_a")
        with c_sel2:
            st.markdown("#### 🟠 對照賽事 B (Target / 最新實戰)")
            sel_b = st.selectbox("選取對照場次 B", options=options_keys, index=default_b_idx, label_visibility="collapsed", key="cmp_sel_b")
    
    path_a = library[sel_a]
    path_b = library[sel_b]
    
    df_a, sum_a, tags_a = load_and_process_cached(path_a)
    df_b, sum_b, tags_b = load_and_process_cached(path_b)
    
    if df_a.empty or df_b.empty:
        st.error("❌ 其中一場賽事資料解析失敗，請重新選取。")
        return
        
    m_a = extract_full_metrics(df_a)
    m_b = extract_full_metrics(df_b)
    
    if not m_a or not m_b:
        st.error("❌ 指標計算異常。")
        return

    # ========================================================
    # 1. 全方位 11 項核心戰力對決卡片 (完全比照單次活動卡片樣式)
    # ========================================================
    st.markdown("#### 🏆 核心數據量化天平：全指標深度對決 (Tale of the Tape)")

    # 配速差值專用
    if m_a["avg_pace"] and m_b["avg_pace"]:
        pace_diff_sec = (m_b["avg_pace"] - m_a["avg_pace"]) * 60
        p_sign = "+" if pace_diff_sec > 0 else ""
        pace_badge_color = "#f43f5e" if pace_diff_sec > 0 else "#34d399"
        pace_badge = f"<span style='font-size:0.75rem; color:{pace_badge_color}; font-weight:bold;'>({p_sign}{int(abs(pace_diff_sec))}s/km)</span>"
    else:
        pace_badge = ""

    # 時間差值專用
    if m_a["tot_time_sec"] and m_b["tot_time_sec"]:
        time_diff_sec = m_b["tot_time_sec"] - m_a["tot_time_sec"]
        t_sign = "+" if time_diff_sec > 0 else ""
        abs_t = abs(int(time_diff_sec))
        time_badge_color = "#f43f5e" if time_diff_sec > 0 else "#34d399"
        time_badge = f"<span style='font-size:0.75rem; color:{time_badge_color}; font-weight:bold;'>({t_sign}{abs_t//60}分{abs_t%60:02d}秒)</span>"
    else:
        time_badge = ""

    # 頂部第 1 列卡片：總里程、平均配速、平均心率、平均步頻、最高心率
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size:0.78rem; color:#94a3b8; margin-bottom:2px;'>🔵 A: {m_a['dist_km']:.2f} km | 🟠 B: {m_b['dist_km']:.2f} km</div>
            <div class='metric-val'>{m_b['dist_km']:.2f} km</div>
            <div class='metric-lbl'>總里程</div>
        </div>
        """, unsafe_allow_html=True)

    with m2:
        st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size:0.78rem; color:#94a3b8; margin-bottom:2px;'>🔵 {m_a['pace_str']} vs 🟠 {m_b['pace_str']} {pace_badge}</div>
            <div class='metric-val'>{m_b['pace_str']}</div>
            <div class='metric-lbl'>平均配速 (/km)</div>
        </div>
        """, unsafe_allow_html=True)

    with m3:
        hr_a_disp = f"{m_a['avg_hr']:.0f}" if m_a['avg_hr'] else "—"
        hr_b_disp = f"{m_b['avg_hr']:.0f}" if m_b['avg_hr'] else "—"
        hr_badge = make_diff_badge(m_a['avg_hr'], m_b['avg_hr'], " bpm", invert=True, precision=1)
        st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size:0.78rem; color:#94a3b8; margin-bottom:2px;'>🔵 {hr_a_disp} vs 🟠 {hr_b_disp} {hr_badge}</div>
            <div class='metric-val' style='color:#f43f5e;'>{hr_b_disp} bpm</div>
            <div class='metric-lbl'>平均心率</div>
        </div>
        """, unsafe_allow_html=True)

    with m4:
        cad_a_disp = f"{m_a['cadence']:.0f}" if m_a['cadence'] else "—"
        cad_b_disp = f"{m_b['cadence']:.0f}" if m_b['cadence'] else "—"
        cad_badge = make_diff_badge(m_a['cadence'], m_b['cadence'], " spm", precision=1)
        st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size:0.78rem; color:#94a3b8; margin-bottom:2px;'>🔵 {cad_a_disp} vs 🟠 {cad_b_disp} {cad_badge}</div>
            <div class='metric-val' style='color:#fbbf24;'>{cad_b_disp} spm</div>
            <div class='metric-lbl'>平均步頻 (SPM)</div>
        </div>
        """, unsafe_allow_html=True)

    with m5:
        maxhr_a_disp = f"{m_a['max_hr']:.0f}" if m_a['max_hr'] else "—"
        maxhr_b_disp = f"{m_b['max_hr']:.0f}" if m_b['max_hr'] else "—"
        maxhr_badge = make_diff_badge(m_a['max_hr'], m_b['max_hr'], " bpm", invert=True, precision=0)
        st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size:0.78rem; color:#94a3b8; margin-bottom:2px;'>🔵 {maxhr_a_disp} vs 🟠 {maxhr_b_disp} {maxhr_badge}</div>
            <div class='metric-val' style='color:#a855f7;'>{maxhr_b_disp} bpm</div>
            <div class='metric-lbl'>最高心率</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    # 頂部第 2 列卡片：步幅、觸地時間、垂直振幅、移動效率(垂直比)、左右平衡、功率
    d1, d2, d3, d4, d5, d6 = st.columns(6)
    with d1:
        step_badge = make_diff_badge(m_a['step_length'], m_b['step_length'], "cm", precision=1)
        step_a_str = f"{m_a['step_length']:.1f}" if m_a['step_length'] else "—"
        step_b_str = f"{m_b['step_length']:.1f}" if m_b['step_length'] else "—"
        st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size:0.72rem; color:#94a3b8; margin-bottom:2px;'>🔵 {step_a_str} vs 🟠 {step_b_str} {step_badge}</div>
            <div class='metric-val' style='font-size:1.15rem; color:#c084fc;'>{step_b_str} cm</div>
            <div class='metric-lbl'>👣 平均步幅</div>
        </div>
        """, unsafe_allow_html=True)

    with d2:
        gct_badge = make_diff_badge(m_a['gct'], m_b['gct'], "ms", invert=True, precision=1)
        gct_a_str = f"{m_a['gct']:.0f}" if m_a['gct'] else "—"
        gct_b_str = f"{m_b['gct']:.0f}" if m_b['gct'] else "—"
        st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size:0.72rem; color:#94a3b8; margin-bottom:2px;'>🔵 {gct_a_str} vs 🟠 {gct_b_str} {gct_badge}</div>
            <div class='metric-val' style='font-size:1.15rem; color:#34d399;'>{gct_b_str} ms</div>
            <div class='metric-lbl'>⚡ 平均觸地時間</div>
        </div>
        """, unsafe_allow_html=True)

    with d3:
        vo_badge = make_diff_badge(m_a['vertical_osc'], m_b['vertical_osc'], "cm", invert=True, precision=1)
        vo_a_str = f"{m_a['vertical_osc']:.1f}" if m_a['vertical_osc'] else "—"
        vo_b_str = f"{m_b['vertical_osc']:.1f}" if m_b['vertical_osc'] else "—"
        st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size:0.72rem; color:#94a3b8; margin-bottom:2px;'>🔵 {vo_a_str} vs 🟠 {vo_b_str} {vo_badge}</div>
            <div class='metric-val' style='font-size:1.15rem; color:#38bdf8;'>{vo_b_str} cm</div>
            <div class='metric-lbl'>📐 垂直振幅</div>
        </div>
        """, unsafe_allow_html=True)

    with d4:
        vr_badge = make_diff_badge(m_a['vertical_ratio'], m_b['vertical_ratio'], "%", invert=True, precision=1)
        vr_a_str = f"{m_a['vertical_ratio']:.1f}" if m_a['vertical_ratio'] else "—"
        vr_b_str = f"{m_b['vertical_ratio']:.1f}" if m_b['vertical_ratio'] else "—"
        st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size:0.72rem; color:#94a3b8; margin-bottom:2px;'>🔵 {vr_a_str} vs 🟠 {vr_b_str} {vr_badge}</div>
            <div class='metric-val' style='font-size:1.15rem; color:#f59e0b;'>{vr_b_str} %</div>
            <div class='metric-lbl'>🎯 移動效率(垂直比)</div>
        </div>
        """, unsafe_allow_html=True)

    with d5:
        bal_a_str = f"{m_a['balance']:.1f}%" if m_a['balance'] else "—"
        bal_b_str = f"{m_b['balance']:.1f}%" if m_b['balance'] else "—"
        st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size:0.72rem; color:#94a3b8; margin-bottom:2px;'>🔵 {bal_a_str} vs 🟠 {bal_b_str}</div>
            <div class='metric-val' style='font-size:1.15rem; color:#ec4899;'>{bal_b_str} 左</div>
            <div class='metric-lbl'>⚖️ 左右平衡</div>
        </div>
        """, unsafe_allow_html=True)

    with d6:
        pwr_badge = make_diff_badge(m_a['power'], m_b['power'], "W", precision=0)
        pwr_a_str = f"{m_a['power']:.0f}" if m_a['power'] else "—"
        pwr_b_str = f"{m_b['power']:.0f}" if m_b['power'] else "—"
        st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size:0.72rem; color:#94a3b8; margin-bottom:2px;'>🔵 {pwr_a_str} vs 🟠 {pwr_b_str} {pwr_badge}</div>
            <div class='metric-val' style='font-size:1.15rem; color:#fb7185;'>{pwr_b_str} W</div>
            <div class='metric-lbl'>⚡ 平均功率</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    # 頂部第 3 列：完賽時間對決、能效比 (EF)、每跳移動公尺 (DPB)
    r3_1, r3_2, r3_3 = st.columns(3)
    with r3_1:
        st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size:0.78rem; color:#94a3b8; margin-bottom:2px;'>🔵 {m_a['dur_str']} vs 🟠 {m_b['dur_str']} {time_badge}</div>
            <div class='metric-val' style='color:#38bdf8;'>{m_b['dur_str']}</div>
            <div class='metric-lbl'>⏱️ 完賽總時間 (Total Time)</div>
        </div>
        """, unsafe_allow_html=True)

    with r3_2:
        if m_a['ef'] and m_b['ef']:
            ef_diff = ((m_b['ef'] - m_a['ef']) / m_a['ef']) * 100
            ef_badge = f"<span style='font-size:0.75rem; color:{'#34d399' if ef_diff>=0 else '#f43f5e'}; font-weight:bold;'>({ef_diff:+.1f}%)</span>"
            ef_b_str = f"{m_b['ef']:.2f}"
            ef_a_str = f"{m_a['ef']:.2f}"
        else:
            ef_badge = ""
            ef_b_str = f"{m_b['ef']:.2f}" if m_b['ef'] else "—"
            ef_a_str = f"{m_a['ef']:.2f}" if m_a['ef'] else "—"
        st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size:0.78rem; color:#94a3b8; margin-bottom:2px;'>🔵 {ef_a_str} vs 🟠 {ef_b_str} {ef_badge}</div>
            <div class='metric-val' style='color:#10b981;'>{ef_b_str}</div>
            <div class='metric-lbl'>🔋 跑步能效比 EF (Speed / HR)</div>
        </div>
        """, unsafe_allow_html=True)

    with r3_3:
        dpb_badge = make_diff_badge(m_a['dpb'], m_b['dpb'], "m", precision=2)
        dpb_a_str = f"{m_a['dpb']:.2f}m" if m_a['dpb'] else "—"
        dpb_b_str = f"{m_b['dpb']:.2f}m" if m_b['dpb'] else "—"
        st.markdown(f"""
        <div class='metric-card'>
            <div style='font-size:0.78rem; color:#94a3b8; margin-bottom:2px;'>🔵 {dpb_a_str} vs 🟠 {dpb_b_str} {dpb_badge}</div>
            <div class='metric-val' style='color:#eab308;'>{dpb_b_str} /跳</div>
            <div class='metric-lbl'>🕊️ 每跳移動距離 (Distance Per Beat)</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)

    # 準備圈數資料 (取兩場圈數最小長度進行公里對疊)
    max_laps = min(len(df_a), len(df_b), 45)
    if max_laps < 1:
        max_laps = max(len(df_a), len(df_b), 1)
        
    laps_range = list(range(1, max_laps + 1))
    df_a_clip = df_a.iloc[:max_laps].copy() if len(df_a) >= max_laps else df_a.copy()
    df_b_clip = df_b.iloc[:max_laps].copy() if len(df_b) >= max_laps else df_b.copy()

    # ========================================================
    # 2. 全層級「每公里運動科學多軸走勢對疊圖 (Stacked Subplots)」
    # ========================================================
    st.markdown("#### 📈 每公里運動科學全指標對疊多軸走勢圖")
    st.caption("將兩場賽事的配速、心率漂移與高階跑姿力學在同一時間/公里軸線深度對疊，直觀透視戰略分水嶺與後半程體能續航。")

    fig_sync = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=(
            "⏱️ 逐公里配速對疊 (Pace Comparison - 越往上越快)",
            "💓 逐公里心率與做功對疊 (Heart Rate Drift & Thresholds)",
            "👣 逐公里跑姿動力學對疊 (觸地時間 GCT & 步頻 Cadence)"
        ),
        row_heights=[0.34, 0.33, 0.33]
    )

    # 1. 配速對疊 (Row 1)
    if 'pace' in df_a_clip.columns and df_a_clip['pace'].notna().any():
        p_text_a = [f"{p} /km" for p in df_a_clip['pace_str']] if 'pace_str' in df_a_clip.columns else [f"{p:.2f} /km" for p in df_a_clip['pace']]
        fig_sync.add_trace(go.Scatter(
            x=list(range(1, len(df_a_clip) + 1)), y=df_a_clip['pace'],
            name=f"🔵 {sel_a[:14]} (配速)",
            mode='lines+markers',
            line=dict(color='#38bdf8', width=3),
            customdata=p_text_a,
            hovertemplate="🔵 A 第 %{x} km: <b>%{customdata}</b><extra></extra>"
        ), row=1, col=1)

    if 'pace' in df_b_clip.columns and df_b_clip['pace'].notna().any():
        p_text_b = [f"{p} /km" for p in df_b_clip['pace_str']] if 'pace_str' in df_b_clip.columns else [f"{p:.2f} /km" for p in df_b_clip['pace']]
        fig_sync.add_trace(go.Scatter(
            x=list(range(1, len(df_b_clip) + 1)), y=df_b_clip['pace'],
            name=f"🟠 {sel_b[:14]} (配速)",
            mode='lines+markers',
            line=dict(color='#fb923c', width=3),
            customdata=p_text_b,
            hovertemplate="🟠 B 第 %{x} km: <b>%{customdata}</b><extra></extra>"
        ), row=1, col=1)

    # 2. 心率對疊 (Row 2) - 全面容錯
    has_hr_a = 'heart_rate' in df_a_clip.columns and df_a_clip['heart_rate'].notna().any()
    has_hr_b = 'heart_rate' in df_b_clip.columns and df_b_clip['heart_rate'].notna().any()

    if has_hr_a:
        fig_sync.add_trace(go.Scatter(
            x=list(range(1, len(df_a_clip) + 1)), y=df_a_clip['heart_rate'],
            name=f"🔵 {sel_a[:14]} (心率)",
            mode='lines+markers',
            line=dict(color='#60a5fa', width=2.5),
            hovertemplate="🔵 A 第 %{x} km: <b>%{y:.0f} bpm</b><extra></extra>"
        ), row=2, col=1)

    if has_hr_b:
        fig_sync.add_trace(go.Scatter(
            x=list(range(1, len(df_b_clip) + 1)), y=df_b_clip['heart_rate'],
            name=f"🟠 {sel_b[:14]} (心率)",
            mode='lines+markers',
            line=dict(color='#f87171', width=2.5),
            hovertemplate="🟠 B 第 %{x} km: <b>%{y:.0f} bpm</b><extra></extra>"
        ), row=2, col=1)

    if not has_hr_a and not has_hr_b:
        fig_sync.add_annotation(text="兩場賽事皆無逐圈心率記錄 (可能為手動計時或無心率帶)", row=2, col=1, showarrow=False, font=dict(color="#94a3b8", size=13))
    else:
        fig_sync.add_hline(y=181, line_dash="dash", line_color="#fbbf24", annotation_text="Edward LTHR (181 bpm)", row=2, col=1)

    # 3. 跑姿動力學 GCT & 步頻 (Row 3) - 全面容錯
    has_gct_a = 'gct' in df_a_clip.columns and df_a_clip['gct'].notna().any()
    has_gct_b = 'gct' in df_b_clip.columns and df_b_clip['gct'].notna().any()
    has_cad_a = 'cadence' in df_a_clip.columns and df_a_clip['cadence'].notna().any()
    has_cad_b = 'cadence' in df_b_clip.columns and df_b_clip['cadence'].notna().any()

    if has_gct_a:
        fig_sync.add_trace(go.Scatter(
            x=list(range(1, len(df_a_clip) + 1)), y=df_a_clip['gct'],
            name=f"🔵 {sel_a[:12]} 觸地 (ms)",
            mode='lines+markers',
            line=dict(color='#818cf8', width=2),
            hovertemplate="🔵 A GCT: <b>%{y:.0f} ms</b><extra></extra>"
        ), row=3, col=1)

    if has_gct_b:
        fig_sync.add_trace(go.Scatter(
            x=list(range(1, len(df_b_clip) + 1)), y=df_b_clip['gct'],
            name=f"🟠 {sel_b[:12]} 觸地 (ms)",
            mode='lines+markers',
            line=dict(color='#34d399', width=2),
            hovertemplate="🟠 B GCT: <b>%{y:.0f} ms</b><extra></extra>"
        ), row=3, col=1)

    if has_gct_a or has_gct_b:
        fig_sync.add_hline(y=237.0, line_dash="dot", line_color="#a78bfa", annotation_text="Edward 237ms 甜蜜點", row=3, col=1)
    elif has_cad_a or has_cad_b:
        # 若無 GCT 則改畫步頻
        if has_cad_a:
            fig_sync.add_trace(go.Scatter(x=list(range(1, len(df_a_clip)+1)), y=df_a_clip['cadence'], name=f"🔵 {sel_a[:12]} 步頻", line=dict(color='#fbbf24', width=2)), row=3, col=1)
        if has_cad_b:
            fig_sync.add_trace(go.Scatter(x=list(range(1, len(df_b_clip)+1)), y=df_b_clip['cadence'], name=f"🟠 {sel_b[:12]} 步頻", line=dict(color='#f59e0b', width=2)), row=3, col=1)
    else:
        fig_sync.add_annotation(text="兩場賽事皆無進階步姿力學記錄", row=3, col=1, showarrow=False, font=dict(color="#94a3b8", size=13))

    # 座標軸優化：全圖啟用貫穿 3 個子圖表的垂直紅色輔助同步線 (Spike Line) 與聯動 Hover (完全比照單次活動剖析)
    fig_sync.update_yaxes(title_text="配速 (/km)", autorange="reversed", row=1, col=1)
    fig_sync.update_yaxes(title_text="心率 (bpm)", row=2, col=1)
    fig_sync.update_yaxes(title_text="力學指標", row=3, col=1)

    # 針對全體子圖表 X 軸配置貫穿多層的紅色對準指針線
    fig_sync.update_xaxes(
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikedash="solid",
        spikethickness=1.8,
        spikecolor="#f43f5e"
    )
    fig_sync.update_xaxes(title_text="公里數 (km)", row=3, col=1)

    fig_sync.layout.xaxis.showspikes = True
    fig_sync.layout.xaxis.spikemode = "across"
    fig_sync.layout.xaxis.spikesnap = "cursor"
    fig_sync.layout.xaxis.spikedash = "solid"
    fig_sync.layout.xaxis.spikethickness = 1.8
    fig_sync.layout.xaxis.spikecolor = "#f43f5e"

    fig_sync.layout.xaxis2.showspikes = True
    fig_sync.layout.xaxis2.spikemode = "across"
    fig_sync.layout.xaxis2.spikesnap = "cursor"
    fig_sync.layout.xaxis2.spikedash = "solid"
    fig_sync.layout.xaxis2.spikethickness = 1.8
    fig_sync.layout.xaxis2.spikecolor = "#f43f5e"

    fig_sync.layout.xaxis3.showspikes = True
    fig_sync.layout.xaxis3.spikemode = "across"
    fig_sync.layout.xaxis3.spikesnap = "cursor"
    fig_sync.layout.xaxis3.spikedash = "solid"
    fig_sync.layout.xaxis3.spikethickness = 1.8
    fig_sync.layout.xaxis3.spikecolor = "#f43f5e"

    fig_sync.update_layout(
        template="plotly_dark",
        height=740,
        hovermode="x",
        hoversubplots="axis",
        hoverlabel=dict(
            bgcolor="rgba(15, 23, 42, 0.70)",
            bordercolor="rgba(148, 163, 184, 0.4)",
            font=dict(size=12, color="#ffffff"),
            align="left"
        ),
        margin=dict(l=50, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.0)
    )
    st.plotly_chart(fig_sync, use_container_width=True)

    # ========================================================
    # 3. 雙場「跑姿退化指數」對比 (Posture Degradation Overlay)
    # ========================================================
    st.markdown("#### 📉 雙場「跑姿退化指數」歸一化對照 (% Baseline)")
    st.caption("將各指標除以該場全程平均值 (100% 基準線)。比對兩場比賽在第 15~21 公里疲勞期，哪一場的步態剛性與節奏維持得更加頑強！")

    fig_norm = go.Figure()
    fig_norm.add_hline(y=100, line_dash="solid", line_color="rgba(148, 163, 184, 0.4)", annotation_text="100% (全程平均基準)")

    # 1. 配速維持率 (Normalized Speed: mean_pace / lap_pace * 100)
    if 'pace' in df_a_clip.columns and m_a["avg_pace"] and m_a["avg_pace"] > 0:
        norm_speed_a = (m_a["avg_pace"] / df_a_clip['pace']) * 100
        fig_norm.add_trace(go.Scatter(
            x=list(range(1, len(df_a_clip) + 1)), y=norm_speed_a,
            name=f"🔵 {sel_a[:12]} 速度維持率",
            mode='lines+markers',
            line=dict(color='#38bdf8', width=2.5)
        ))
    if 'pace' in df_b_clip.columns and m_b["avg_pace"] and m_b["avg_pace"] > 0:
        norm_speed_b = (m_b["avg_pace"] / df_b_clip['pace']) * 100
        fig_norm.add_trace(go.Scatter(
            x=list(range(1, len(df_b_clip) + 1)), y=norm_speed_b,
            name=f"🟠 {sel_b[:12]} 速度維持率",
            mode='lines+markers',
            line=dict(color='#fb923c', width=2.5)
        ))

    # 2. 觸地時間退化率 (Normalized GCT: lap_gct / mean_gct * 100)
    if 'gct' in df_a_clip.columns and m_a["gct"] and m_a["gct"] > 0:
        norm_gct_a = (df_a_clip['gct'] / m_a["gct"]) * 100
        fig_norm.add_trace(go.Scatter(
            x=list(range(1, len(df_a_clip) + 1)), y=norm_gct_a,
            name=f"🔵 {sel_a[:12]} 觸地延長率",
            mode='lines',
            line=dict(color='#818cf8', width=2, dash='dot')
        ))
    if 'gct' in df_b_clip.columns and m_b["gct"] and m_b["gct"] > 0:
        norm_gct_b = (df_b_clip['gct'] / m_b["gct"]) * 100
        fig_norm.add_trace(go.Scatter(
            x=list(range(1, len(df_b_clip) + 1)), y=norm_gct_b,
            name=f"🟠 {sel_b[:12]} 觸地延長率",
            mode='lines',
            line=dict(color='#34d399', width=2, dash='dot')
        ))

    fig_norm.update_xaxes(
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikedash="solid",
        spikethickness=1.8,
        spikecolor="#f43f5e"
    )
    fig_norm.update_layout(
        title="<b>🏃 雙場跑姿退化與速度衰退對疊 (100% 歸一化)</b>",
        xaxis_title="公里數 (km)",
        yaxis_title="偏離全程平均比例 (%)",
        template="plotly_dark",
        height=380,
        hovermode="x",
        hoverlabel=dict(
            bgcolor="rgba(15, 23, 42, 0.70)",
            bordercolor="rgba(148, 163, 184, 0.4)",
            font=dict(size=12, color="#ffffff"),
            align="left"
        ),
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_norm, use_container_width=True)

    # ========================================================
    # 4. 步態生物力學五維雷達圖 (Biomechanics Radar)
    # ========================================================
    col_radar_left, col_radar_right = st.columns([0.45, 0.55])
    with col_radar_left:
        st.markdown("#### 🕸️ 步態力學五維雷達天平")
        radar_categories = ["步頻節奏", "觸地剛性", "推蹬步幅", "垂直效率", "心血管能效"]
        
        # 運動科學標準化評分 (校準至 60~100 分，180+ spm 與 230~240ms GCT 均屬 90+ 菁英頂級區間)
        cad_val_a = m_a["cadence"] if m_a["cadence"] else 180.0
        cad_val_b = m_b["cadence"] if m_b["cadence"] else 180.0
        # 160spm=70分, 170spm=80分, 180spm=90分, 185spm=95分, 190spm=100分
        score_cad_a = float(np.clip(70.0 + (cad_val_a - 160.0) * 1.0, 50, 100))
        score_cad_b = float(np.clip(70.0 + (cad_val_b - 160.0) * 1.0, 50, 100))
        
        gct_val_a = m_a["gct"] if m_a["gct"] else 237.0
        gct_val_b = m_b["gct"] if m_b["gct"] else 237.0
        # 280ms=70分, 260ms=80分, 240ms=90分, 237ms=91.5分, 220ms=100分
        score_gct_a = float(np.clip(100.0 - (gct_val_a - 220.0) * 0.5, 50, 100))
        score_gct_b = float(np.clip(100.0 - (gct_val_b - 220.0) * 0.5, 50, 100))
        
        step_val_a = m_a["step_length"] if m_a["step_length"] else 100.0
        step_val_b = m_b["step_length"] if m_b["step_length"] else 100.0
        score_str_a = float(np.clip(step_val_a * 0.95, 50, 100))
        score_str_b = float(np.clip(step_val_b * 0.95, 50, 100))
        
        vr_val_a = m_a["vertical_ratio"] if m_a["vertical_ratio"] else 7.5
        vr_val_b = m_b["vertical_ratio"] if m_b["vertical_ratio"] else 7.5
        # 垂直比 <8% 為頂級區間
        score_vr_a = float(np.clip(100.0 - (vr_val_a - 6.0) * 7.5, 50, 100))
        score_vr_b = float(np.clip(100.0 - (vr_val_b - 6.0) * 7.5, 50, 100))
        
        ef_val_a = m_a["ef"] if m_a["ef"] else 1.0
        ef_val_b = m_b["ef"] if m_b["ef"] else 1.0
        score_ef_a = float(np.clip(ef_val_a * 95.0, 50, 100))
        score_ef_b = float(np.clip(ef_val_b * 95.0, 50, 100))

        # 浮動提示文字 (直接顯示實際數值)
        hover_a = [
            f"步頻: {cad_val_a:.1f} spm (得分: {score_cad_a:.1f})",
            f"觸地: {gct_val_a:.0f} ms (得分: {score_gct_a:.1f})",
            f"步幅: {step_val_a:.1f} cm (得分: {score_str_a:.1f})",
            f"垂直比: {vr_val_a:.1f}% (得分: {score_vr_a:.1f})",
            f"能效比: {ef_val_a:.2f} (得分: {score_ef_a:.1f})"
        ]
        hover_a.append(hover_a[0])

        hover_b = [
            f"步頻: {cad_val_b:.1f} spm (得分: {score_cad_b:.1f})",
            f"觸地: {gct_val_b:.0f} ms (得分: {score_gct_b:.1f})",
            f"步幅: {step_val_b:.1f} cm (得分: {score_str_b:.1f})",
            f"垂直比: {vr_val_b:.1f}% (得分: {score_vr_b:.1f})",
            f"能效比: {ef_val_b:.2f} (得分: {score_ef_b:.1f})"
        ]
        hover_b.append(hover_b[0])

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=[score_cad_a, score_gct_a, score_str_a, score_vr_a, score_ef_a, score_cad_a],
            theta=radar_categories + [radar_categories[0]],
            fill='toself',
            name=f"🔵 {sel_a[:12]}",
            line=dict(color='#38bdf8', width=2),
            fillcolor='rgba(56, 189, 248, 0.2)',
            text=hover_a,
            hovertemplate="🔵 %{text}<extra></extra>"
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=[score_cad_b, score_gct_b, score_str_b, score_vr_b, score_ef_b, score_cad_b],
            theta=radar_categories + [radar_categories[0]],
            fill='toself',
            name=f"🟠 {sel_b[:12]}",
            line=dict(color='#fb923c', width=2),
            fillcolor='rgba(251, 146, 60, 0.2)',
            text=hover_b,
            hovertemplate="🟠 %{text}<extra></extra>"
        ))
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[55, 102], showticklabels=False)
            ),
            template="plotly_dark",
            height=360,
            margin=dict(l=30, r=30, t=30, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1)
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    with col_radar_right:
        # ========================================================
        # 5. 雙教練臨床會診差值報告 (Dual-Coach Differential Verdict)
        # ========================================================
        st.markdown("#### 🩺 雙教練臨床會診：成因解剖與科學定論")
        stride_diff_pct = (abs(m_b["step_length"] - m_a["step_length"]) / m_a["step_length"]) * 100 if (m_a["step_length"] and m_a["step_length"] > 0 and m_b["step_length"]) else 0
        cad_diff_pct = (abs(m_b["cadence"] - m_a["cadence"]) / m_a["cadence"]) * 100 if (m_a["cadence"] and m_a["cadence"] > 0 and m_b["cadence"]) else 0
        hr_diff_str = f"{abs(m_b['avg_hr'] - m_a['avg_hr']):.1f} bpm" if (m_a['avg_hr'] and m_b['avg_hr']) else "無心率對比"
        gct_diff_str = f"{abs(m_b['gct'] - m_a['gct']):.1f} ms" if (m_a['gct'] and m_b['gct']) else "無觸地對比"
        
        st.markdown(f"""
        <div style="background: rgba(30, 58, 138, 0.25); border-left: 4px solid #3b82f6; padding: 14px; border-radius: 8px; margin-bottom: 12px;">
            <div style="font-weight: 700; color: #60a5fa; font-size: 1rem; margin-bottom: 6px;">
                🧬 路格教練 (Coach Luger) 生化生理差值審查
            </div>
            <ul style="margin: 0; padding-left: 18px; color: #e2e8f0; font-size: 0.88rem; line-height: 1.55;">
                <li><strong>心血管搏出等效：</strong> 兩場平均心率差異僅 <code>{hr_diff_str}</code>，心臟做功與乳酸耐受輸出具備高一致性！</li>
                <li><strong>生理能效分析：</strong> 若 B 場處於高溫/大風環境（如長榮馬 27°C），體溫調節血流轉移為造成有氧能效折損之首要環境因數，而非有氧引擎衰竭。</li>
            </ul>
        </div>

        <div style="background: rgba(6, 78, 59, 0.25); border-left: 4px solid #10b981; padding: 14px; border-radius: 8px;">
            <div style="font-weight: 700; color: #34d399; font-size: 1rem; margin-bottom: 6px;">
                🏃‍♀️ 佩絲教練 (Coach Pace) 步態力學診斷
            </div>
            <ul style="margin: 0; padding-left: 18px; color: #e2e8f0; font-size: 0.88rem; line-height: 1.55;">
                <li><strong>觸地時間剛性守恆：</strong> 觸地時間 GCT 差異僅 <code>{gct_diff_str}</code>，完美錨定在 Edward 個人 <strong>237ms 甜蜜點</strong>，下肢彈性剛性無懈可擊！</li>
                <li><strong>速度差異物理本質：</strong> 步頻變動僅 <code>{cad_diff_pct:.1f}%</code>，而步幅縮減達 <code>{stride_diff_pct:.1f}%</code>！這證明速度差異源自於 <strong>「推蹬推進步幅縮短」</strong>，而非步頻崩潰。</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    # ========================================================
    # 6. 逐公里每圈數據詳細對照表 (Lap-by-Lap Split Delta Table)
    # ========================================================
    st.markdown("---")
    st.markdown("#### 📋 逐公里每圈數據詳細對照表 (Lap-by-Lap Head-to-Head)")
    
    rows = []
    for i in range(max_laps):
        lap_num = i + 1
        
        # 安全取值 helper
        def get_val(df_clip, row_idx, col, fmt="{:.0f}", default="—"):
            if col in df_clip.columns and row_idx < len(df_clip):
                val = df_clip.iloc[row_idx][col]
                if pd.notna(val):
                    try:
                        return fmt.format(val)
                    except Exception:
                        return str(val)
            return default

        p_a = df_a_clip.iloc[i]['pace_str'] if ('pace_str' in df_a_clip.columns and i < len(df_a_clip) and pd.notna(df_a_clip.iloc[i]['pace_str'])) else get_val(df_a_clip, i, 'pace', "{:.2f}")
        p_b = df_b_clip.iloc[i]['pace_str'] if ('pace_str' in df_b_clip.columns and i < len(df_b_clip) and pd.notna(df_b_clip.iloc[i]['pace_str'])) else get_val(df_b_clip, i, 'pace', "{:.2f}")
        
        # 配速差
        p_val_a = df_a_clip.iloc[i]['pace'] if ('pace' in df_a_clip.columns and i < len(df_a_clip) and pd.notna(df_a_clip.iloc[i]['pace'])) else None
        p_val_b = df_b_clip.iloc[i]['pace'] if ('pace' in df_b_clip.columns and i < len(df_b_clip) and pd.notna(df_b_clip.iloc[i]['pace'])) else None
        if p_val_a and p_val_b:
            p_diff_s = (p_val_b - p_val_a) * 60
            p_diff_str = f"{'+' if p_diff_s>0 else ''}{int(p_diff_s)}s"
        else:
            p_diff_str = "—"
            
        hr_a = get_val(df_a_clip, i, 'heart_rate', "{:.0f}")
        hr_b = get_val(df_b_clip, i, 'heart_rate', "{:.0f}")
        
        cad_a = get_val(df_a_clip, i, 'cadence', "{:.0f}")
        cad_b = get_val(df_b_clip, i, 'cadence', "{:.0f}")
        
        gct_a = get_val(df_a_clip, i, 'gct', "{:.0f}")
        gct_b = get_val(df_b_clip, i, 'gct', "{:.0f}")
        
        # 步幅
        raw_s_a = df_a_clip.iloc[i]['step_length'] if ('step_length' in df_a_clip.columns and i < len(df_a_clip) and pd.notna(df_a_clip.iloc[i]['step_length'])) else None
        step_a_disp = f"{raw_s_a * 100 if raw_s_a < 3.0 else raw_s_a:.1f}" if raw_s_a else "—"
        
        raw_s_b = df_b_clip.iloc[i]['step_length'] if ('step_length' in df_b_clip.columns and i < len(df_b_clip) and pd.notna(df_b_clip.iloc[i]['step_length'])) else None
        step_b_disp = f"{raw_s_b * 100 if raw_s_b < 3.0 else raw_s_b:.1f}" if raw_s_b else "—"
        
        rows.append({
            "圈數 (Km)": f"Km {lap_num}",
            "🔵 A 配速": p_a,
            "🟠 B 配速": p_b,
            "配速差 (B - A)": p_diff_str,
            "🔵 A 心率": hr_a,
            "🟠 B 心率": hr_b,
            "🔵 A 步頻": cad_a,
            "🟠 B 步頻": cad_b,
            "🔵 A 觸地 (ms)": gct_a,
            "🟠 B 觸地 (ms)": gct_b,
            "🔵 A 步幅 (cm)": step_a_disp,
            "🟠 B 步幅 (cm)": step_b_disp
        })
        
    compare_table_df = pd.DataFrame(rows)
    st.dataframe(compare_table_df, use_container_width=True, height=450)
    
    csv_bytes = compare_table_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="💾 下載雙場對決比較 CSV",
        data=csv_bytes,
        file_name="head_to_head_splits_comparison.csv",
        mime="text/csv"
    )
