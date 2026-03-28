import streamlit as st
import json
import pandas as pd
import os
import plotly.graph_objects as go
from data_processor import process_fit_data
# from garmin_fetcher import get_garmin_data (removed)
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
    user_profile = f"跑者 (Edward): {u_age}歲{u_gender}, 最大心率: {u_max_hr}, 靜息: {u_rest_hr}, 閾值: {u_threshold_hr}, 類型: {u_type}"

# --- 5. 置頂控制區 (Fixed Top) ---
header_container = st.container()
with header_container:
    st.markdown('<div class="fixed-top-header">', unsafe_allow_html=True)
    st.subheader("🏃‍♂️ AI Coach 6.0")
    st.markdown('</div>', unsafe_allow_html=True)

# --- 6. 核心處理邏輯 ---
def trigger_coach_responses(user_input):
    """
    統一處理 AI 教練的回話流程 (支援動態順序與數據載入)
    """
    # 整理歷史訊息
    gemini_history = []
    for msg in st.session_state.messages: # 此时 user_input 已經在 messages 裡了
        if msg["role"] == "user":
            gemini_history.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant":
            if msg.get("name") == "路格教練":
                if gemini_history and gemini_history[-1]["role"] == "assistant":
                    gemini_history[-1]["content"] += "\n\n" + msg["content"]
                else:
                    gemini_history.append({"role": "assistant", "content": msg["content"]})
            else:
                context_msg = f"(同事 {msg.get('name', '教練')} 說): {msg['content']}"
                if gemini_history and gemini_history[-1]["role"] == "user":
                    gemini_history[-1]["content"] += "\n\n" + context_msg
                else:
                    gemini_history.append({"role": "user", "content": context_msg})
    
    # 移除最後一筆 (即當前 user_input)，因 engine 內會手動加在尾部或處理
    if gemini_history:
        gemini_history = gemini_history[:-1]

    history_context = get_history_snapshot()
    full_context_summary = f"{history_context}\n\n[本次任務數據]:\n{st.session_state.summary}"

    g_key = keys.get("GEMINI_API_KEY", "")
    o_key = keys.get("OPENAI_API_KEY", "")

    # 決定回答順序
    is_pace_first = ("佩絲" in user_input.lower() or "pace" in user_input.lower())
    full_luger_response = ""
    full_pace_response = ""

    chat_placeholder = st.container()

    if is_pace_first:
        # 佩絲先
        with chat_placeholder.chat_message(name="佩絲教練", avatar="pace.png"):
            p_holder = st.empty()
            try:
                p_stream = stream_pace(o_key, user_profile, "", full_context_summary, user_input)
                for chunk in p_stream:
                    full_pace_response += chunk
                    p_holder.markdown(full_pace_response + "▌")
                p_holder.markdown(full_pace_response)
            except Exception as e: st.error(f"佩絲異常: {e}")
        
        with chat_placeholder.chat_message(name="路格教練", avatar="luger.png"):
            l_holder = st.empty()
            try:
                l_stream = stream_luger(g_key, gemini_history, user_profile, full_context_summary, user_input)
                for chunk in l_stream:
                    full_luger_response += chunk
                    l_holder.markdown(full_luger_response + "▌")
                l_holder.markdown(full_luger_response)
            except Exception as e: st.error(f"路格異常: {e}")
        
        st.session_state.messages.append({"role": "assistant", "name": "佩絲教練", "avatar": "pace.png", "content": full_pace_response})
        st.session_state.messages.append({"role": "assistant", "name": "路格教練", "avatar": "luger.png", "content": full_luger_response})
    else:
        # 路格先
        with chat_placeholder.chat_message(name="路格教練", avatar="luger.png"):
            l_holder = st.empty()
            try:
                l_stream = stream_luger(g_key, gemini_history, user_profile, full_context_summary, user_input)
                for chunk in l_stream:
                    full_luger_response += chunk
                    l_holder.markdown(full_luger_response + "▌")
                l_holder.markdown(full_luger_response)
            except Exception as e: st.error(f"路格異常: {e}")
        
        with chat_placeholder.chat_message(name="佩絲教練", avatar="pace.png"):
            p_holder = st.empty()
            try:
                p_stream = stream_pace(o_key, user_profile, full_luger_response, full_context_summary, user_input)
                for chunk in p_stream:
                    full_pace_response += chunk
                    p_holder.markdown(full_pace_response + "▌")
                p_holder.markdown(full_pace_response)
            except Exception as e: st.error(f"佩絲異常: {e}")
            
        st.session_state.messages.append({"role": "assistant", "name": "路格教練", "avatar": "luger.png", "content": full_luger_response})
        st.session_state.messages.append({"role": "assistant", "name": "佩絲教練", "avatar": "pace.png", "content": full_pace_response})

    save_chat_log(st.session_state.messages)

# --- 7. 介面分頁 ---
tab1, tab2 = st.tabs(["💬 雙教練會診室", "📊 數據看板"])

with tab1:
    chat_box = st.container()
    for msg in st.session_state.messages:
        with chat_box.chat_message(name=msg.get("name", msg["role"]), avatar=msg.get("avatar")):
            st.markdown(msg["content"])

    # --- 文件上傳入口 ---
    uploaded_file = st.file_uploader("📎 上傳跑步數據 (.fit / .csv)", type=["fit", "csv"], label_visibility="collapsed")
    if uploaded_file:
        if "last_file" not in st.session_state or st.session_state.last_file != uploaded_file.name:
            file_ext = uploaded_file.name.split(".")[-1].lower()
            save_path = f"temp.{file_ext}"
            with open(save_path, "wb") as f: f.write(uploaded_file.getbuffer())
            
            # 解析數據
            df, summary, metrics = process_fit_data(save_path) 
            st.session_state.df = df
            st.session_state.summary = summary
            st.session_state.metrics = metrics
            st.session_state.last_file = uploaded_file.name
            save_run_to_history(summary)
            
            # 手動新增上傳訊息並觸發回話
            u_msg = f"我上傳了一個檔案：`{uploaded_file.name}`，教練們請根據這份數據給我分析。"
            st.session_state.messages.append({"role": "user", "name": "Edward", "avatar": "Edward.png", "content": u_msg})
            with chat_box.chat_message(name="Edward", avatar="Edward.png"):
                st.markdown(u_msg)
            
            trigger_coach_responses(u_msg)
            st.rerun()

    user_input = st.chat_input("詢問教練...")
    if user_input:
        st.session_state.messages.append({"role": "user", "name": "Edward", "avatar": "Edward.png", "content": user_input})
        with chat_box.chat_message(name="Edward", avatar="Edward.png"):
            st.markdown(user_input)
        
        trigger_coach_responses(user_input)
        st.rerun()

with tab2:
    if st.session_state.df is not None and not st.session_state.df.empty:
        df = st.session_state.df
        st.subheader("📊 專業數據看板")
        # 直接使用 metrics 字典
        garmin_map = {
            'heart_rate': '💓 心率 (bpm)', 'pace': '⏱️ 跑步配速 (min/km)', 
            'cadence': '👣 步頻 (spm)', 'power': '⚡ 跑步功率 (W)',
            'vertical_oscillation': '⬆️ 垂直振幅 (cm)', 'stance_time': '⏱️ 觸地時間 (ms)', 
            'dist_km': '📏 距離 (km)', 'altitude': '⛰️ 海拔 (m)'
        }
        all_numeric_cols = [c for c in df.columns if c in garmin_map and pd.api.types.is_numeric_dtype(df[c])]
        
        selected_metrics = []
        check_cols = st.columns(4)
        for i, col in enumerate(all_numeric_cols):
            with check_cols[i % 4]:
                if st.checkbox(garmin_map.get(col, col), value=(col in ['heart_rate', 'pace']), key=f"v2_{col}"):
                    selected_metrics.append(col)
        
        if selected_metrics:
            fig = go.Figure()
            for m in selected_metrics:
                fig.add_trace(go.Scatter(x=df.index, y=df[m], name=garmin_map.get(m, m), mode='lines'))
            fig.update_layout(template="plotly_dark", height=600, hovermode="x unified")
            if 'pace' in selected_metrics: # 配速軸反轉 (越小越快)
                fig.update_layout(yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("👋 請由上方上傳數據檔案進行分析。")