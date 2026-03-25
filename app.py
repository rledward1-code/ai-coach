import streamlit as st
import json
import os
import plotly.graph_objects as go
from data_processor import process_fit_data
from garmin_fetcher import get_garmin_data
from coach_engine import stream_luger, stream_pace
from history_manager import save_run_to_history, get_history_snapshot, save_chat_log, load_chat_log

# --- 1. 初始化 Session State ---
if "conversation_step" not in st.session_state:
    st.session_state.conversation_step = "idle"
if "last_luger_response" not in st.session_state:
    st.session_state.last_luger_response = ""
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_log()
if "df" not in st.session_state:
    st.session_state.df = None
if "summary" not in st.session_state:
    st.session_state.summary = "目前無數據上傳"
if "metrics" not in st.session_state:
    st.session_state.metrics = {}

# --- 2. 金鑰管理 ---
def load_keys():
    if os.path.exists("keys.json"):
        with open("keys.json", "r") as f:
            return json.load(f)
    return {}

keys = load_keys()
st.set_page_config(page_title="AI Coach 6.0", layout="wide")

# --- 3. UI 佈局 CSS 強化 ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117 !important; color: #fafafa !important; }
    
    /* 頂部固定組件 */
    .fixed-top-header {
        position: sticky;
        top: 0;
        background-color: #0e1117;
        z-index: 1000;
        padding: 10px 20px;
        border-bottom: 2px solid #30363d;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    }
    
    /* 讓 Tab 緊貼 Header */
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        position: sticky;
        top: 85px;
        background-color: #0e1117 !important;
        z-index: 999;
        padding-top: 5px;
        border-bottom: 1px solid #30363d;
    }
    
    /* 頭像縮放效果 */
    [data-testid="stChatMessage"] img {
        width: 55px !important;
        height: 55px !important;
        border-radius: 50% !important;
        transition: transform 0.3s ease-in-out !important;
    }
    [data-testid="stChatMessage"] img:hover {
        transform: scale(2.5) !important;
        z-index: 1100 !important;
        position: relative;
    }
    
    /* 隱藏文件上傳器的多餘邊距 */
    [data-testid="stFileUploadDropzone"] {
        padding: 5px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 4. 側邊欄：個人檔案 ---
with st.sidebar:
    st.header("👤 跑者個人檔案")
    u_age = st.number_input("年齡", value=56)
    u_gender = st.selectbox("性別", ["男", "女", "其他"], index=0)
    h1, h2, h3 = st.columns(3)
    u_max_hr = h1.number_input("最大心率", value=210)
    u_rest_hr = h2.number_input("靜息心率", value=56)
    u_threshold_hr = h3.number_input("閾值心率", value=193)
    u_type = st.selectbox("跑步類型", ["輕鬆跑 (E)", "馬拉松配速 (M)", "乳酸閾值 (T)", "間歇 (I)", "全馬比賽", "半馬比賽"], index=5)
    user_profile = f"跑者: {u_age}歲{u_gender}, 最大心率: {u_max_hr}, 靜息: {u_rest_hr}, 閾值: {u_threshold_hr}, 類型: {u_type}"

# --- 5. 置頂控制區 (Fixed Top) ---
header_container = st.container()
with header_container:
    st.markdown('<div class="fixed-top-header">', unsafe_allow_html=True)
    t1, t2 = st.columns([1, 1.5], vertical_alignment="center")
    with t1:
        st.subheader("🏃‍♂️ AI Coach 6.0")
    with t2:
        sync_col, upload_col = st.columns([0.8, 1.2])
        with sync_col:
            if st.button("⬇️ Garmin 同步", use_container_width=True):
                g_email = keys.get("GARMIN_EMAIL", "")
                g_pass = keys.get("GARMIN_PASSWORD", "")
                if g_email and g_pass:
                    with st.spinner("⏳"):
                        success, msg, api_summary = get_garmin_data(g_email, g_pass)
                        if success:
                            df, _, metrics = process_fit_data("temp.fit")
                            st.session_state.df = df
                            st.session_state.summary = api_summary
                            st.session_state.metrics = metrics
                            save_run_to_history(api_summary)
                            st.rerun()
                        else: st.error(msg)
        with upload_col:
            uploaded_file = st.file_uploader("手動上傳 .fit", type=["fit"], label_visibility="collapsed")
            if uploaded_file:
                if "last_file" not in st.session_state or st.session_state.last_file != uploaded_file.name:
                    with open("temp.fit", "wb") as f: f.write(uploaded_file.getbuffer())
                    df, summary, metrics = process_fit_data("temp.fit")
                    st.session_state.df = df
                    st.session_state.summary = summary
                    st.session_state.metrics = metrics
                    st.session_state.last_file = uploaded_file.name
                    save_run_to_history(summary)
                    st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- 6. 介面分頁 ---
tab1, tab2 = st.tabs(["💬 雙教練會診室", "📊 數據看板"])

with tab1:
    chat_container = st.container()
    for msg in st.session_state.messages:
        with chat_container.chat_message(name=msg.get("name", msg["role"]), avatar=msg.get("avatar")):
            st.markdown(msg["content"])

    user_input = st.chat_input("詢問教練...")
    if user_input:
        st.session_state.messages.append({"role": "user", "name": "跑者", "avatar": "🏃‍♂️", "content": user_input})
        with chat_container.chat_message(name="跑者", avatar="🏃‍♂️"):
            st.markdown(user_input)
        
        # 整理歷史訊息
        gemini_history = []
        current_model_text = ""
        for msg in st.session_state.messages[:-1]:
            if msg["role"] == "user":
                if current_model_text:
                    gemini_history.append({"role": "assistant", "content": current_model_text.strip()})
                    current_model_text = ""
                gemini_history.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                prefix = f"【{msg.get('name', '助手')}】\n"
                current_model_text += prefix + msg["content"] + "\n\n"
        if current_model_text:
            gemini_history.append({"role": "assistant", "content": current_model_text.strip()})

        history_context = get_history_snapshot()
        full_context_summary = f"{history_context}\n\n[本次任務數據]:\n{st.session_state.summary}"

        g_key = keys.get("GEMINI_API_KEY", "")
        o_key = keys.get("OPENAI_API_KEY", "")

        # --- 👨‍🏫 路格教練 ---
        with chat_container.chat_message(name="路格教練", avatar="luger.png"):
            luger_placeholder = st.empty()
            full_luger_response = ""
            try:
                luger_stream = stream_luger(g_key, gemini_history, user_profile, full_context_summary, user_input)
                for chunk in luger_stream:
                    full_luger_response += chunk
                    luger_placeholder.markdown(full_luger_response + "▌")
                luger_placeholder.markdown(full_luger_response)
            except Exception as e:
                st.error(f"路格異常: {e}")
                full_luger_response = "數據分析暫時中斷。"
        st.session_state.messages.append({"role": "assistant", "name": "路格教練", "avatar": "luger.png", "content": full_luger_response})

        # --- 👩‍🏫 佩絲教練 ---
        with chat_container.chat_message(name="佩絲教練", avatar="pace.png"):
            pace_placeholder = st.empty()
            full_pace_response = ""
            try:
                pace_stream = stream_pace(o_key, user_profile, full_luger_response, full_context_summary)
                for chunk in pace_stream:
                    full_pace_response += chunk
                    pace_placeholder.markdown(full_pace_response + "▌")
                pace_placeholder.markdown(full_pace_response)
            except Exception as e:
                st.error(f"佩絲異常: {e}")
        st.session_state.messages.append({"role": "assistant", "name": "佩絲教練", "avatar": "pace.png", "content": full_pace_response})
        
        save_chat_log(st.session_state.messages)

with tab2:
    if st.session_state.df is not None:
        df = st.session_state.df
        st.subheader("📊 Garmin 專業數據看板")
        garmin_map = {
            'heart_rate': '💓 心率 (bpm)', 'enhanced_speed': '⏱️ 平均配速 (m/s)', 
            'speed': '🏃 即時速度 (m/s)', 'cadence': '👣 步頻 (spm)', 
            'step_length': '📏 步幅 (mm)', 'altitude': '⛰️ 海拔 (m)', 
            'power': '⚡ 跑步功率 (W)', 'vertical_oscillation': '⬆️ 垂直振幅 (cm)',
            'stance_time': '⏱️ 觸地時間 (ms)', 'dist_km': '📏 距離 (km)'
        }
        all_numeric_cols = [c for c in df.select_dtypes(include=['number']).columns if c != 'timestamp']
        selected_metrics = []
        check_cols = st.columns(4)
        for i, col in enumerate(all_numeric_cols):
            with check_cols[i % 4]:
                display_name = garmin_map.get(col, f"🔍 ({col})")
                if st.checkbox(display_name, value=(col in ['heart_rate', 'enhanced_speed']), key=f"v2_{col}"):
                    selected_metrics.append(col)
        if selected_metrics:
            fig = go.Figure()
            for m in selected_metrics:
                fig.add_trace(go.Scatter(x=df.index, y=df[m], name=garmin_map.get(m, m), mode='lines'))
            fig.update_layout(template="plotly_dark", height=600, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("👋 請由上方同步或上傳數據。")