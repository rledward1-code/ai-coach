import streamlit as st
import streamlit.components.v1 as st_components
import json
import pandas as pd
import os
import random
from datetime import datetime
import plotly.graph_objects as go
from data_processor import process_data, process_history_summary
from coach_engine import stream_luger, stream_pace, determine_rounds, determine_speakers
from history_manager import (
    save_run_to_history, get_history_snapshot, save_chat_log, load_chat_log, 
    save_global_history, load_global_history, save_user_profile, load_user_profile
)
from memory_manager import sync_memory_store, get_relevant_memories

# --- 1. Session State 初始化 ---
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_log()
if "df" not in st.session_state:
    st.session_state.df = None
if "pending_summary" not in st.session_state:
    st.session_state.pending_summary = ""
if "pending_file_name" not in st.session_state:
    st.session_state.pending_file_name = ""
if "pending_tags" not in st.session_state:
    st.session_state.pending_tags = []
if "pending_rpe" not in st.session_state:
    st.session_state.pending_rpe = 5
if "pending_feeling" not in st.session_state:
    st.session_state.pending_feeling = "普通"
if "pending_plan" not in st.session_state:
    st.session_state.pending_plan = ""
if "visible_messages_count" not in st.session_state:
    st.session_state.visible_messages_count = 20

# --- 2. 金鑰管理 ---
def load_keys():
    if os.path.exists("keys.json"):
        with open("keys.json", "r") as f:
            return json.load(f)
    return {}

keys = load_keys()
st.set_page_config(
    page_title="AI Coach 6.0",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={}
)

# --- 2.5 建立功能彈窗 ---
@st.dialog("上傳歷史總表 (Garmin/Strava)")
def upload_history_dialog():
    st.write("請上傳從運動平台匯出的活動清單 CSV，這能幫助教練了解你的長期訓練背景。")
    h_file = st.file_uploader("選擇 CSV 檔案", type=["csv"], key="global_history_upload_ui")
    if h_file:
        with st.spinner("正在建立跑者長期檔案..."):
            h_save_path = "temp_history.csv"
            with open(h_save_path, "wb") as f:
                f.write(h_file.getbuffer())
            global_summary = process_history_summary(h_save_path)
            save_global_history(global_summary)
            st.success("✅ 長期檔案已更新！")
            st.info(global_summary)
            if st.button("完成並關閉"):
                st.rerun()


# --- 3. CSS (精簡版，不再嘗試 sticky hack) ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117 !important; color: #fafafa !important; }
    [data-testid="stChatMessage"] img {
        width: 55px !important; height: 55px !important;
        border-radius: 50% !important; transition: transform 0.2s;
    }
    [data-testid="stChatMessage"] img:hover {
        transform: scale(2.5) !important; z-index: 9999 !important; position: relative;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 4. 側邊欄：個人檔案 + 檔案上傳 ---
with st.sidebar:
    # 載入持久化設定
    p_data = load_user_profile()

    c1, c2 = st.columns([0.8, 0.2])
    with c1:
        st.header("👤 個人資料")
    with c2:
        st.write("") # 稍微對齊
        if st.button("📊", help="上傳歷史總表"):
            upload_history_dialog()

    u_name = st.text_input("跑者姓名", value=p_data.get("name", "Edward"))
    u_age = st.number_input("年齡", value=p_data.get("age", 56))
    u_gender = st.selectbox("性別", ["男", "女", "其他"], index=["男", "女", "其他"].index(p_data.get("gender", "男")))
    h1, h2, h3 = st.columns(3)
    u_max_hr = h1.number_input("最大心率", value=p_data.get("max_hr", 210))
    u_rest_hr = h2.number_input("靜息心率", value=p_data.get("rest_hr", 56))
    u_threshold_hr = h3.number_input("閾值心率", value=p_data.get("threshold_hr", 193))
    
    # 組裝與即時儲存
    user_profile = f"跑者 ({u_name}): {u_age}歲{u_gender}, 最大心率: {u_max_hr}, 靜息: {u_rest_hr}, 閾值: {u_threshold_hr}"
    save_user_profile({
        "name": u_name,
        "age": u_age,
        "gender": u_gender,
        "max_hr": u_max_hr,
        "rest_hr": u_rest_hr,
        "threshold_hr": u_threshold_hr
    })

    st.divider()
    st.subheader("📎 上傳訓練數據")
    uploaded_file = st.file_uploader("FIT / CSV", type=["fit", "csv"], label_visibility="collapsed")
    if uploaded_file and uploaded_file.name != st.session_state.pending_file_name:
        file_ext = uploaded_file.name.split(".")[-1].lower()
        save_path = f"temp.{file_ext}"
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        df, summary, _, tags = process_data(save_path)
        st.session_state.df = df
        st.session_state.pending_summary = summary
        st.session_state.pending_tags = tags
        st.session_state.pending_file_name = uploaded_file.name
        save_run_to_history(
            summary, 
            tags=tags, 
            rpe=st.session_state.pending_rpe, 
            feeling=st.session_state.pending_feeling, 
            plan=st.session_state.pending_plan
        )

    if st.session_state.pending_file_name:
        st.success(f"✅ {st.session_state.pending_file_name}")
        
        with st.expander("📝 補充本次訓練報告", expanded=True):
            st.session_state.pending_rpe = st.slider("🏃 體感強度 (RPE)", 1, 10, st.session_state.pending_rpe, help="1最輕鬆, 10極限辛苦")
            st.session_state.pending_feeling = st.select_slider("🧠 身體感受", options=["極差", "疲累", "普通", "良好", "神清氣爽"], value=st.session_state.pending_feeling)
            st.session_state.pending_plan = st.text_input("📋 原定計畫描述", placeholder="例如: 輕鬆跑 10K 或 6x800 間歇", value=st.session_state.pending_plan)
            
            if st.button("💾 更新訓練紀錄", use_container_width=True):
                save_run_to_history(
                    st.session_state.pending_summary, 
                    tags=st.session_state.pending_tags,
                    rpe=st.session_state.pending_rpe,
                    feeling=st.session_state.pending_feeling,
                    plan=st.session_state.pending_plan
                )
                st.toast("訓練詳情已同步至紀錄！")

        st.caption("輸入訊息即可發送完整分析。")

        st.caption("輸入訊息即可發送完整分析。")

# --- 5. CSS 注入 ---
st.markdown("""
<style>
/* 讓 height= 容器填滿可用空間 */
section.main > div.block-container {
    padding-bottom: 0 !important;
    padding-top: 1.5rem !important;
}
/* 隱藏 Deploy 和 ... 工具列，但不藏 header（sidebar 展開箭頭在裡面） */
#MainMenu { visibility: hidden !important; }
.stDeployButton { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }
/* chat_input 外層容器也要跟著高 */
[data-testid="stChatInputContainer"] {
    min-height: 90px !important;
}
[data-testid="stChatInputContainer"] textarea {
    min-height: 75px !important;
    max-height: 200px !important;
    resize: vertical !important;
}

/* 強制 chat 容器在上方長出內容時，保持滾動位置不動 (滾動錨點) */
div[data-testid="stVerticalBlockBorderWrapper"] {
    overflow-anchor: auto !important;
}
/* 讓錨點生效：針對每個對話區塊 */
div[data-testid="stChatMessage"] {
    overflow-anchor: auto !important;
}

</style>
""", unsafe_allow_html=True)



# --- 6. 核心處理邏輯 (多輪對話版) ---
def trigger_coach_responses(user_input, data_summary, container):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    time_prefix = f"[系統時間: {now_str}]\n"
    
    # 為路格建立歷史：路格的回覆 = model，佩絲的回覆 = user context（關鍵！）
    # 這樣 Gemini 才知道佩絲是「別人」，不會把兩個角色都演出來
    luger_history = []
    pace_history = []
    for msg in st.session_state.messages:
        t = msg.get("time", "")
        c = msg["content"]
        name = msg.get("name", "")
        
        if msg["role"] == "user":
            luger_history.append({"role": "user", "content": f"({t}) {c}"})
            pace_history.append({"role": "user", "content": f"({t}) {c}"})
            
        elif name == "路格教練":
            # 路格自己說過的話 = model (assistant)
            luger_history.append({"role": "assistant", "content": c})
            # 路格的話對佩絲來說是「別人說的話」，掛在 user 角色下
            if pace_history and pace_history[-1]["role"] == "user":
                pace_history[-1]["content"] += f"\n\n(路格說: {c})"
            else:
                pace_history.append({"role": "user", "content": f"(路格說: {c})"})
                
        elif name == "佩絲教練":
            # 佩絲自己說過的話 = assistant
            pace_history.append({"role": "assistant", "content": c})
            # 佩絲的話對路格來說是「別人說的話」，掛在 user 角色下
            if luger_history and luger_history[-1]["role"] == "user":
                luger_history[-1]["content"] += f"\n\n(同行的佩絲說: {c})"
            else:
                luger_history.append({"role": "user", "content": f"(同行的佩絲說: {c})"})
                
    if luger_history: luger_history = luger_history[:-1]
    if pace_history: pace_history = pace_history[:-1]

    history_context = get_history_snapshot()
    global_hist = load_global_history()
    tag_info = f" [標籤: {', '.join(st.session_state.pending_tags)}]" if st.session_state.get('pending_tags') else ""
    session_report = f"\n[跑者體感回報]: RPE {st.session_state.pending_rpe}, 感受: {st.session_state.pending_feeling}, 原定計畫: {st.session_state.pending_plan if st.session_state.pending_plan else '未註明'}"
    
    # 目前單次任務的完整摘要
    current_session_summary = f"{session_report}\n\n{data_summary if data_summary else ''}"

    memory_context = ""
    if keys.get("OPENAI_API_KEY", ""):
        try:
            sync_memory_store(keys.get("OPENAI_API_KEY", ""))
            memory_context = get_relevant_memories(
                keys.get("OPENAI_API_KEY", ""),
                f"{user_input}\n{history_context}",
                top_k=4,
            )
        except Exception:
            memory_context = ""

    g_key, o_key = keys.get("GEMINI_API_KEY", ""), keys.get("OPENAI_API_KEY", "")
    
    # 決定是否有數據附件 (包含剛上傳的總表或單次數據)
    has_data = bool(data_summary) or bool(global_hist)
    speaker_order = determine_speakers(g_key, user_input, has_data=has_data)
    
    # 整合記憶內容到當前摘要
    if memory_context:
        current_session_summary = f"【相關過往記憶】:\n{memory_context}\n\n{current_session_summary}"
    
    prev_luger = ""
    prev_pace = ""
    full_l, full_p = "", ""
    cp = container   # 渲染在傳入的容器中，確保 chat_input 永遠在容器下方
    round_input = time_prefix + user_input
    
    for speaker in speaker_order:
        if speaker == "luger":
            with cp.chat_message(name="路格教練", avatar="assets/luger.png"):
                holder = st.empty()
                holder.markdown("*💭 路格正在思考...*")
                try:
                    buf = ""
                    for chk in stream_luger(g_key, luger_history, user_profile, current_session_summary, global_hist, round_input, prev_pace_response=prev_pace):
                        buf += chk
                        holder.markdown(buf + "▌")
                    holder.markdown(buf)
                    full_l = buf
                except Exception as e:
                    holder.markdown(f"路格異常: {e}")
            
            st.session_state.messages.append({"role": "assistant", "name": "路格教練", "avatar": "assets/luger.png", "content": full_l, "time": now_str})
            prev_luger = full_l
        
        else:  # pace
            with cp.chat_message(name="佩絲教練", avatar="assets/pace.png"):
                holder = st.empty()
                holder.markdown("*💭 佩絲正在思考...*")
                try:
                    buf = ""
                    for chk in stream_pace(o_key, user_profile, full_l, current_session_summary, global_hist, round_input, prev_luger_response=prev_luger, history=pace_history):
                        buf += chk
                        holder.markdown(buf + "▌")
                    holder.markdown(buf)
                    full_p = buf
                except Exception as e:
                    holder.markdown(f"佩絲異常: {e}")
            
            st.session_state.messages.append({"role": "assistant", "name": "佩絲教練", "avatar": "assets/pace.png", "content": full_p, "time": now_str})
            prev_pace = full_p

    
    # 偵測教練間是否開始自聊：若最後回應提到對方名字，觸發最多 2 輪的教練自主對話
    # Edward 在此期間變成旁觀者
    def _coaches_talking_to_each_other(luger_resp, pace_resp):
        # 只檢測明確提到對方名字，避免「你說」「你覺得」這類通用詞濒繁觸發
        luger_mentions_pace = any(kw in luger_resp for kw in ["佩絲", "Coach Pace"])
        pace_mentions_luger = any(kw in pace_resp for kw in ["路格", "Coach Luger"])
        return luger_mentions_pace and pace_mentions_luger  # 必須兩人都提到對方，才觸發自聘
    
    if _coaches_talking_to_each_other(prev_luger, prev_pace):
        for coach_chat_idx in range(2):  # 最多 2 輪自主對話
            cp = container
            
            # 路格回應佩絲
            full_l_cc = ""
            with cp.chat_message(name="路格教練", avatar="assets/luger.png"):
                holder = st.empty()
                holder.markdown("*💭 路格正在思考...*")
                try:
                    # 用空的 user_input，讓教練自行接話
                    coach_prompt = f"（繼續剛才的討論，對佩絲說話，不需要理會 Edward）"
                    buf = ""
                    for chk in stream_luger(g_key, luger_history, user_profile, full_cv, coach_prompt, prev_pace_response=prev_pace):
                        buf += chk
                        holder.markdown(buf + "▌")
                    holder.markdown(buf)
                    full_l_cc = buf
                except Exception as e:
                    holder.markdown(f"路格異常: {e}")
            st.session_state.messages.append({"role": "assistant", "name": "路格教練", "avatar": "assets/luger.png", "content": full_l_cc, "time": now_str})
            
            # 佩絲回路格
            full_p_cc = ""
            with cp.chat_message(name="佩絲教練", avatar="assets/pace.png"):
                holder = st.empty()
                holder.markdown("*💭 佩絲正在思考...*")
                try:
                    coach_prompt_p = f"（繼續跟路格討論，不需要特別理會 Edward）"
                    buf = ""
                    for chk in stream_pace(o_key, user_profile, full_l_cc, full_cv, coach_prompt_p, prev_luger_response=prev_luger, history=pace_history):
                        buf += chk
                        holder.markdown(buf + "▌")
                    holder.markdown(buf)
                    full_p_cc = buf
                except Exception as e:
                    holder.markdown(f"佩絲異常: {e}")
            st.session_state.messages.append({"role": "assistant", "name": "佩絲教練", "avatar": "assets/pace.png", "content": full_p_cc, "time": now_str})
            
            # 更新 history 讓下一輪自聊能接著說
            luger_history.append({"role": "assistant", "content": full_l_cc})
            if pace_history and pace_history[-1]["role"] == "user":
                pace_history[-1]["content"] += f"\n\n(路格說: {full_l_cc})"
            else:
                pace_history.append({"role": "user", "content": f"(路格說: {full_l_cc})"})
            
            if full_p_cc:
                if luger_history[-1]["role"] == "user":
                    luger_history[-1]["content"] += f"\n\n(佩絲說: {full_p_cc})"
                else:
                    luger_history.append({"role": "user", "content": f"(佩絲說: {full_p_cc})"})
                pace_history.append({"role": "assistant", "content": full_p_cc})
            prev_luger, prev_pace = full_l_cc, full_p_cc
            
            # 若教練們已不再互相提及，停止自主對話
            if not _coaches_talking_to_each_other(full_l_cc, full_p_cc):
                break
    
    save_chat_log(st.session_state.messages)

# --- 7. 分頁介面 ---
tab1, tab2 = st.tabs(["💬 雙教練會診室", "📊 數據看板"])

with tab1:
    chat_box = st.container(height=650)
    with chat_box:
        # --- 分段加載歷史紀錄 ---
        all_msgs = st.session_state.messages
        total_count = len(all_msgs)
        visible_count = st.session_state.visible_messages_count
        
        # 如果還有隱藏的訊息，顯示「載入更多」按鈕
        if total_count > visible_count:
            if st.button(f"⬆️ 載入更早之前的對話 (還有 {total_count - visible_count} 則)", use_container_width=True):
                st.session_state.visible_messages_count += 20
                st.rerun()

        visible_msgs = all_msgs[-visible_count:] if total_count > visible_count else all_msgs
        
        # 提取跑者姓名 (用於顯示聊天頭像名字)
        current_user_name = u_name
        
        turns = []
        for msg in visible_msgs:
            if msg["role"] == "user":
                turns.append([msg])
            elif turns:
                turns[-1].append(msg)

        # 計算隱藏對話的前綴 (Offset) 用於刪除邏輯
        hidden_user_count = sum(1 for m in all_msgs[:-visible_count] if m["role"] == "user")

        for turn_idx, turn in enumerate(turns):
            for msg_pos, msg in enumerate(turn):
                raw_av = msg.get("avatar") or ""
                if raw_av and "/" not in raw_av:
                    raw_av = f"assets/{raw_av}"
                with st.chat_message(name=msg.get("name", current_user_name if msg["role"] == "user" else msg["role"]), avatar=raw_av or None):

                    st.markdown(msg["content"])
                    if "time" in msg:
                        is_last = (msg_pos == len(turn) - 1)
                        if is_last:
                            tc, _, dc = st.columns([8, 1, 1])
                            tc.caption(f"🕒 {msg['time']}")
                            
                            # 修正對應到全域消息索引
                            global_turn_idx = hidden_user_count + turn_idx
                            if dc.button("🗑️", key=f"del_{global_turn_idx}", help="刪除此組對話"):
                                count = 0
                                msg_idx = 0
                                for i, m in enumerate(st.session_state.messages):
                                    if m["role"] == "user":
                                        if count == global_turn_idx:
                                            msg_idx = i
                                            break
                                        count += 1
                                end_idx = msg_idx + 1
                                while end_idx < len(st.session_state.messages) and st.session_state.messages[end_idx]["role"] != "user":
                                    end_idx += 1
                                del st.session_state.messages[msg_idx:end_idx]
                                save_chat_log(st.session_state.messages)
                                st.rerun()
                        else:
                            st.caption(f"🕒 {msg['time']}")
            
            st.divider() # 每一組全走完後，加一條分隔線



    # 狀態提示：有附件時顯示，否則靜默
    if st.session_state.get("pending_file_name"):
        st.caption(f"✅ `{st.session_state.pending_file_name}` 已就緒，輸入訊息後一起發送")

    user_input = st.chat_input("詢問教練...")
    if user_input:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        final_content = user_input
        this_turn_summary = ""

        if st.session_state.pending_summary:
            this_turn_summary = st.session_state.pending_summary
            tags_display = f" [{', '.join(st.session_state.pending_tags)}]" if st.session_state.pending_tags else ""
            final_content = f"📎 [附件: {st.session_state.pending_file_name}]{tags_display}\n\n{user_input}"
            st.session_state.pending_summary = ""
            st.session_state.pending_tags = []

        st.session_state.messages.append({"role": "user", "name": u_name, "avatar": f"assets/{u_name}.png" if os.path.exists(f"assets/{u_name}.png") else None, "content": final_content, "time": now_str})

        with chat_box:
            with st.chat_message(name=u_name, avatar=f"assets/{u_name}.png" if os.path.exists(f"assets/{u_name}.png") else None):
                st.markdown(final_content)

        trigger_coach_responses(user_input, this_turn_summary, chat_box)
        st.rerun()

with tab2:
    if st.session_state.df is not None and not st.session_state.df.empty:
        df = st.session_state.df
        st.subheader("📊 數據看板")
        g_map = {'heart_rate': '💓 心率', 'pace': '⏱️ 配速', 'cadence': '👣 步頻'}
        cols = [c for c in df.columns if c in g_map]
        sel = []
        if cols:
            cc = st.columns(len(cols))
            for i, c in enumerate(cols):
                with cc[i]:
                    if st.checkbox(g_map[c], value=(c in ['heart_rate','pace']), key=f"vf_{c}"): sel.append(c)
        if sel:
            fig = go.Figure()
            for m in sel: fig.add_trace(go.Scatter(x=df.index, y=df[m], name=g_map[m], mode='lines'))
            fig.update_layout(template="plotly_dark", height=500)
            if 'pace' in sel: fig.update_layout(yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("👋 請由左側側邊欄上傳數據。")