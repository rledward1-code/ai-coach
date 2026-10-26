# app.py
"""
AI Coach 運動科學戰情儀表板 (Sports Science Dashboard)
專為 Edward (Max HR 210 / Rest HR 53 / LTHR 193) 量身打造。
提供三大分頁視角：
  - 🎛️ 課表微調模擬器 (支援間歇 / 節奏 / LSD 三模式)
  - 📈 心率配速解析圖 (雙 Y 軸曲線 + 5K 分段對比圖)
  - 📋 每公里詳細數據 (Lap by Lap 完整指標表)
"""

import os
import json
import time
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data_processor import process_data
import garmin_cloud
from compare_view import render_compare_tab
from training_schedule_view import (
    render_sidebar_schedule_card,
    render_schedule_tab_section,
    get_gsheet_urls,
    save_gsheet_settings,
    derive_csv_url_from_sheet_url,
    load_schedule_data
)

# --- 1. 頁面配置 ---
st.set_page_config(
    page_title="AI Coach 運動科學戰情看板",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. 樣式優化 (CSS) ---
st.markdown("""
<style>
/* 1. 頂部 Header 保持透明極簡，隱藏 Deploy 按鈕與裝飾條，保留收合與展開按鈕 */
header[data-testid="stHeader"],
header.stAppHeader {
    background: transparent !important;
    height: 2.4rem !important;
    min-height: 2.4rem !important;
    display: block !important;
    visibility: visible !important;
    z-index: 99 !important;
    pointer-events: none !important;
}

[data-testid="stToolbar"] {
    display: flex !important;
    visibility: visible !important;
    background: transparent !important;
    height: 2.4rem !important;
}

/* 徹底隱藏右上角部署按鈕、選單與裝飾彩條 */
.stDeployButton,
[data-testid="stAppDeployButton"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
#MainMenu {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    width: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* 側邊欄收合時的展開按鈕 (stExpandSidebarButton / >>) 保持立體可點擊 */
[data-testid="stExpandSidebarButton"],
button[data-testid="stExpandSidebarButton"],
[data-testid="stToolbar"] [data-testid="stExpandSidebarButton"] {
    display: flex !important;
    visibility: visible !important;
    pointer-events: auto !important;
    margin-left: 0.5rem !important;
    margin-top: 0.2rem !important;
}

[data-testid="stExpandSidebarButton"] button,
button[data-testid="stExpandSidebarButton"] {
    pointer-events: auto !important;
    background: rgba(30, 41, 59, 0.9) !important;
    border: 1px solid rgba(56, 189, 248, 0.5) !important;
    border-radius: 8px !important;
    padding: 3px 8px !important;
    color: #38bdf8 !important;
    cursor: pointer !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.3) !important;
    transition: all 0.2s ease !important;
}

[data-testid="stExpandSidebarButton"] button:hover,
button[data-testid="stExpandSidebarButton"]:hover {
    background: rgba(56, 189, 248, 0.25) !important;
    border-color: #38bdf8 !important;
    transform: scale(1.08) !important;
}

/* 2. 主畫面 (Main Container) 緊湊對齊，消除無謂空隙 */
.main .block-container,
[data-testid="stMainBlockContainer"],
[data-testid="block-container"],
section.main > div:first-child,
section.main > div.block-container {
    padding-top: 0.9rem !important;
    padding-bottom: 0.8rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 100% !important;
}

/* 3. 側邊欄頂部 Header 保持超緊湊，保留收合雙箭頭按鈕 (<<) */
[data-testid="stSidebarHeader"] {
    display: flex !important;
    visibility: visible !important;
    justify-content: flex-end !important;
    align-items: center !important;
    height: 2.2rem !important;
    min-height: 2.2rem !important;
    padding: 0.15rem 0.6rem 0rem 0.6rem !important;
    margin: 0 !important;
    background: transparent !important;
}

/* 側邊欄收合按鈕 (stSidebarCollapseButton / <<) 樣式美化 */
[data-testid="stSidebarCollapseButton"],
button[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarHeader"] button {
    display: flex !important;
    visibility: visible !important;
    pointer-events: auto !important;
    opacity: 0.8 !important;
    color: #94a3b8 !important;
    transition: all 0.2s ease !important;
    cursor: pointer !important;
}

[data-testid="stSidebarCollapseButton"]:hover,
[data-testid="stSidebarHeader"] button:hover {
    opacity: 1 !important;
    color: #38bdf8 !important;
    transform: scale(1.1) !important;
}

[data-testid="stSidebar"],
[data-testid="stSidebarContent"],
[data-testid="stSidebarUserContent"],
section[data-testid="stSidebar"] > div {
    padding-top: 0.2rem !important;
}

[data-testid="stSidebarUserContent"] > div:first-child {
    margin-top: 0rem !important;
    padding-top: 0rem !important;
}

iframe {
    width: 100% !important;
    border: none !important;
}

/* 指標卡樣式 */
.metric-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 12px 16px;
    text-align: center;
}
.metric-val {
    font-size: 1.45rem;
    font-weight: 700;
    color: #3b82f6;
}
.metric-lbl {
    font-size: 0.8rem;
    color: #94a3b8;
}

/* 分頁樣式加強 */
button[data-baseweb="tab"] {
    font-size: 1rem !important;
    font-weight: 600 !important;
    padding-top: 10px !important;
    padding-bottom: 10px !important;
}

/* 自訂 Dialog 彈窗寬度與質感美化 (超寬舒適視野) */
[data-testid="stDialog"] div[role="dialog"] {
    width: 860px !important;
    max-width: 92vw !important;
    border-radius: 14px !important;
    border: 1px solid rgba(56, 189, 248, 0.35) !important;
    box-shadow: 0 20px 45px rgba(0, 0, 0, 0.6) !important;
}
</style>
""", unsafe_allow_html=True)

# --- 3. 讀取設定與跑者設定檔 ---
KEYS_FILE = "keys.json"
keys = {}
if os.path.exists(KEYS_FILE):
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            keys = json.load(f)
    except Exception:
        pass

# 初始化 Session State
if "df" not in st.session_state:
    st.session_state.df = None
if "pending_summary" not in st.session_state:
    st.session_state.pending_summary = ""
if "pending_file_name" not in st.session_state:
    st.session_state.pending_file_name = ""
if "pending_tags" not in st.session_state:
    st.session_state.pending_tags = []
if "synced_rhr" not in st.session_state:
    st.session_state.synced_rhr = 60
if "synced_sleep" not in st.session_state:
    st.session_state.synced_sleep = 56
if "synced_hrv" not in st.session_state:
    st.session_state.synced_hrv = 35
if "synced_b_min" not in st.session_state:
    st.session_state.synced_b_min = 32
if "synced_b_max" not in st.session_state:
    st.session_state.synced_b_max = 39
if "synced_hrv_status" not in st.session_state:
    st.session_state.synced_hrv_status = "BALANCED"
if "mfa_pending" not in st.session_state:
    st.session_state.mfa_pending = False
if "garmin_pending_client" not in st.session_state:
    st.session_state.garmin_pending_client = None
prof_init = load_user_profile() if "load_user_profile" in globals() else {}
if "base_max_hr" not in st.session_state:
    st.session_state.base_max_hr = prof_init.get('max_hr', 210)
if "base_rest_hr" not in st.session_state:
    st.session_state.base_rest_hr = prof_init.get('rest_hr', 56)
if "base_lthr" not in st.session_state:
    st.session_state.base_lthr = prof_init.get('lthr', 186)
if "base_z2_min" not in st.session_state:
    st.session_state.base_z2_min = prof_init.get('z2_min', 145)
if "base_z2_max" not in st.session_state:
    st.session_state.base_z2_max = prof_init.get('z2_max', 165)
if "base_source" not in st.session_state:
    st.session_state.base_source = "Garmin 手錶動態同步"

def apply_synced_readiness(readiness):
    """將 Garmin 雲端拉取的晨檢指標寫入 Session State，並透過 Key Versioning 強制元件即刻重置至最新雲端值"""
    if not readiness:
        return
    rhr = int(readiness.get("rhr", 54))
    sleep = int(readiness.get("sleep_score", 96))
    hrv = int(readiness.get("hrv_last_night", 33))
    b_min = int(readiness.get("hrv_baseline_min", 32))
    b_max = int(readiness.get("hrv_baseline_max", 39))
    status = readiness.get("hrv_status", "BALANCED")

    st.session_state.synced_rhr = rhr
    st.session_state.synced_sleep = sleep
    st.session_state.synced_hrv = hrv
    st.session_state.synced_b_min = b_min
    st.session_state.synced_b_max = b_max
    st.session_state.synced_hrv_status = status

    # 關鍵：遞增版本號，強制 Streamlit 銷毀舊快取並以最新 value 重新初始化所有拉桿與選單
    st.session_state.readiness_sync_ver = st.session_state.get("readiness_sync_ver", 0) + 1


def load_user_profile():
    defaults = {
        "name": "跑者",
        "age": 56,
        "gender": "男",
        "weight_kg": 53.0,
        "height_cm": 170.0,
        "max_hr": 197,
        "rest_hr": 57,
        "lthr": 181,
        "z2_min": 144,
        "z2_max": 159,
        "pb_full_time": "04:31:00",
        "pb_half_time": "01:52:33",
        "pb_full_min": 271.0,
        "pb_half_min": 112.55,
        "pb_full_label": "全馬 4:31:00 (2024台北馬)",
        "pb_half_label": "半馬 1:52:33 (2025台北馬)"
    }
    p_path = "data/user_profile.json"
    if os.path.exists(p_path):
        try:
            with open(p_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
        except Exception:
            pass
    return defaults

def save_user_profile(data):
    p_path = "data/user_profile.json"
    os.makedirs(os.path.dirname(p_path), exist_ok=True)
    with open(p_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if "user_profile" not in st.session_state:
    st.session_state.user_profile = load_user_profile()

profile = st.session_state.user_profile
user_name = profile.get("name", "跑者")

@st.dialog("⚙️ 跑者個人設定與生理基線 (Profile & Baseline)", width="large")
def open_profile_dialog():
    curr = st.session_state.get("user_profile", load_user_profile())
    st.caption("自訂跑者基本資訊、心率區間與歷史最佳成績，一鍵將整套 AI Coach 系統切換為您個人或新使用者的專屬教練！")
    
    t_prof, t_hr, t_pb, t_garmin, t_gsheet = st.tabs(["👤 基本資料", "💓 生理心率基線", "🏆 最佳戰績", "⌚ Garmin 綁定", "📊 Google 試算表"])
    
    with t_prof:
        c1, c2 = st.columns(2)
        with c1:
            u_name = st.text_input("跑者姓名 / 稱謂", value=curr.get("name", "跑者"))
            u_gender = st.selectbox("性別", options=["男", "女", "其他"], index=0 if curr.get("gender") == "男" else 1)
        with c2:
            u_age = st.number_input("年齡 (歲)", min_value=10, max_value=100, value=int(curr.get("age", 56)))
            u_weight = st.number_input("體重 (kg)", min_value=30.0, max_value=200.0, value=float(curr.get("weight_kg", 53.0)), step=0.5)

    with t_hr:
        st.markdown("<div style='font-size:0.85rem; color:#94a3b8; margin-bottom: 6px;'>設定您的最大心率、晨脈與 Zone 2 守護防線：</div>", unsafe_allow_html=True)
        ch1, ch2, ch3 = st.columns(3)
        with ch1:
            u_max_hr = st.number_input("最高心率 (Max HR)", min_value=140, max_value=230, value=int(curr.get("max_hr", 197)))
            u_rest_hr = st.number_input("安靜心率 (Rest HR)", min_value=35, max_value=100, value=int(curr.get("rest_hr", 57)))
        with ch2:
            u_lthr = st.number_input("乳酸閾值 (LTHR)", min_value=120, max_value=210, value=int(curr.get("lthr", 181)))
        with ch3:
            u_z2_min = st.number_input("Zone 2 下限", min_value=100, max_value=180, value=int(curr.get("z2_min", 144)))
            u_z2_max = st.number_input("Zone 2 上限", min_value=110, max_value=190, value=int(curr.get("z2_max", 159)))
            
        if garmin_cloud.has_valid_token():
            if st.button("🔄 一鍵帶入 Garmin 手錶動態分區", use_container_width=True):
                zones, msg = garmin_cloud.fetch_user_hr_zones()
                if zones:
                    st.success(f"已從 Garmin 讀取：Max {zones['max_hr']}, LTHR {zones['lthr']}, Zone 2: {zones['z2_min']}-{zones['z2_max']}")
                    u_max_hr = zones['max_hr']
                    u_rest_hr = zones['rest_hr']
                    u_lthr = zones['lthr']
                    u_z2_min = zones['z2_min']
                    u_z2_max = zones['z2_max']

    with t_pb:
        st.markdown("<div style='font-size:0.85rem; color:#94a3b8; margin-bottom: 6px;'>歷史實戰最佳成績 (作為課表等效跑力推演之基準錨定)：</div>", unsafe_allow_html=True)
        cpb1, cpb2 = st.columns(2)
        with cpb1:
            pb_f_str = st.text_input("全馬 PB (時:分:秒)", value=curr.get("pb_full_time", "04:31:00"), placeholder="04:31:00")
            pb_f_lbl = st.text_input("全馬賽事註記", value=curr.get("pb_full_label", "全馬 4:31:00 (2024台北馬)"))
        with cpb2:
            pb_h_str = st.text_input("半馬 PB (時:分:秒)", value=curr.get("pb_half_time", "01:52:33"), placeholder="01:52:33")
            pb_h_lbl = st.text_input("半馬賽事註記", value=curr.get("pb_half_label", "半馬 1:52:33 (2025台北馬)"))

    with t_garmin:
        st.markdown("<div style='font-size:0.85rem; color:#94a3b8; margin-bottom: 6px;'>綁定 Garmin 官方 Personal API，享受全自動秒級動態同步：</div>", unsafe_allow_html=True)
        st.markdown("""
        **📋 取得 API Token 步驟：**
        1. 點擊前往 👉 [**Garmin Connect Personal API Token 申請頁面**](https://connect.garmin.com/app/settings/personalApiToken)
        2. 登入您的 Garmin 帳號，點擊 **「產生權杖 (Generate Token)」**
        3. 複製以 `GCDC_` 開頭的金鑰字串並貼入下方欄位。
        """)
        st.markdown("""
        <div style='background: rgba(16, 185, 129, 0.08); border-left: 3px solid #10b981; padding: 8px 12px; border-radius: 4px; font-size: 0.8rem; color: #a7f3d0; margin-bottom: 10px;'>
            🛡️ <strong>本機隱私安全聲明 (Local-Only Privacy)</strong>：<br>
            您的 Garmin API Token <strong>僅保存在本機檔案中 (Local Storage)</strong>，絕不上傳任何第三方雲端或外部伺服器。所有連線均由您的瀏覽器/電腦直接向 Garmin 官方伺服器 (<code>connectapi.garmin.com</code>) 發起請求，隱私 100% 自主掌控。
        </div>
        """, unsafe_allow_html=True)
        has_token = garmin_cloud.has_valid_token()
        if has_token:
            st.success("🔒 **系統狀態：已綁定有效 Garmin Token (安全隱藏保護)**")
            token_placeholder = "已配置金鑰。若需更換請在此輸入新 Token"
        else:
            st.info("ℹ️ **系統狀態：尚未配置 Token (可在此輸入金鑰直接啟用)**")
            token_placeholder = "GCDC_xxxxxxxx-xxxx..."

        in_api_k = st.text_input(
            "Garmin Personal API Token",
            value="",
            type="password",
            placeholder=token_placeholder,
            help="基於最高安全防護原則，系統絕不在畫面上回顯真實 Token 字串，防止瀏覽器檢查外洩"
        )
        if st.button("💾 驗證並儲存 Garmin Token", use_container_width=True):
            if in_api_k and in_api_k.strip():
                with st.spinner("向 Garmin 官方伺服器驗證中..."):
                    ok, vmsg = garmin_cloud.save_personal_api_key(in_api_k.strip())
                    if ok:
                        st.session_state.cloud_activities = []
                        st.success(vmsg)
                        st.rerun()
                    else:
                        st.error(vmsg)
            else:
                st.warning("請輸入欲更新的 API Token")

    with t_gsheet:
        cur_sheet_url, cur_csv_url = get_gsheet_urls()
        cur_webhook = st.session_state.get("GOOGLE_SHEET_WEBHOOK_URL", "")
        if not cur_webhook and os.path.exists("keys.json"):
            try:
                with open("keys.json", "r", encoding="utf-8") as f:
                    cur_webhook = json.load(f).get("GOOGLE_SHEET_WEBHOOK_URL", "")
            except Exception:
                pass

        st.markdown("<div style='font-size:0.85rem; color:#94a3b8; margin-bottom: 6px;'>連動個人 8 週課表 Google 試算表：</div>", unsafe_allow_html=True)
        st.markdown("""
        <div style='background: rgba(56, 189, 248, 0.08); border-left: 3px solid #38bdf8; padding: 8px 12px; border-radius: 4px; font-size: 0.8rem; color: #bae6fd; margin-bottom: 12px;'>
            💡 <strong>智慧解析</strong>：直接貼上瀏覽器中的 Google 試算表網址，系統會自動解析並推導即時 CSV 串流，完全無需手動拼湊匯出參數！
        </div>
        """, unsafe_allow_html=True)

        in_sheet_url = st.text_input(
            "Google 試算表瀏覽網址 (Sheet URL)",
            value=cur_sheet_url,
            placeholder="https://docs.google.com/spreadsheets/d/.../edit#gid=...",
            help="開啟 Google 試算表後，直接複製瀏覽器網址列整串網址貼入即可"
        )
        
        has_webhook = bool(cur_webhook)
        wh_placeholder = "🔒 已配置專屬 Webhook。若需更換請輸入新網址" if has_webhook else "https://script.google.com/macros/s/.../exec"

        in_webhook_url = st.text_input(
            "Google Apps Script Webhook 網址 (選填，用於雙向回寫同步)",
            value="",
            type="password",
            placeholder=wh_placeholder,
            help="基於隱私防護，系統不在畫面上回顯真實 Webhook 網址"
        )

        with st.expander("📖 如何建立您專屬的 Google Apps Script Webhook？(點擊展開 3 步驟與範例代碼)", expanded=False):
            st.markdown("""
            **雙向回寫同步 Webhook** 能讓 Antigravity 雙教練或系統自動為您調整課表、寫入最新賽事實績至試算表。

            **🛠️ 3 分鐘架設步驟：**
            1. 打開您的 Google 試算表，點擊頂部選單 **「擴充功能」->「Apps Script」**。
            2. 將編輯器內原有代碼清空，複製貼上下方的「標準 Webhook 腳本」。
            3. 點擊右上角 **「部署」->「新部署作業」**：
               * 點選齒輪圖示，選取 **「網頁應用程式 (Web app)」**。
               * 說明：`AI Coach Webhook`
               * 執行身分：**我 (您的 Google 帳號)**
               * 誰可以存取：**所有人 (Anyone)** *(確保雲端能向端點 POST 課表與成績)*
            4. 點擊 **「部署」** 並同意存取授權，複製產生的 **「網頁應用程式網址」** (以 `/exec` 結尾) 並貼回上方欄位！
            """)
            gas_sample_code = """/**
 * AI Coach Google Apps Script Webhook 輕量範本
 * 支援功能：
 * 1. 課表指定儲存格微調 (update_cell)
 * 2. 多列多欄課表批次同步 (set_range)
 * 3. 賽事實績自動追加 (appendRow)
 */
function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({
    status: "ok",
    message: "AI Coach 跑步賽事與課表智能同步端點正常運作中！"
  })).setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.tryLock(10000);
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return ContentService.createTextOutput(JSON.stringify({ status: "error", message: "缺少內容" }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    var data = JSON.parse(e.postData.contents);
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(data.sheet_name || "成績") || ss.getActiveSheet();
    var action = data.action || "";

    // 1. 單一儲存格更新 (如教練微調某日配速)
    if (action === "update_cell") {
      sheet.getRange(data.cell).setValue(data.value);
      return ContentService.createTextOutput(JSON.stringify({ status: "success", cell: data.cell, value: data.value }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    // 2. 多列多欄批次寫入 (如同步整週最新課表)
    if (action === "set_range" && data.values) {
      sheet.getRange(data.start_row || 1, data.start_col || 1, data.values.length, data.values[0].length).setValues(data.values);
      return ContentService.createTextOutput(JSON.stringify({ status: "success", rows: data.values.length }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    // 3. 賽事實績追加寫入
    if (data.row) {
      sheet.appendRow(data.row);
      return ContentService.createTextOutput(JSON.stringify({ status: "success", message: "賽事已追加！" }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    return ContentService.createTextOutput(JSON.stringify({ status: "ok" }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ status: "error", message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}"""
            st.code(gas_sample_code, language="javascript")
            st.caption("💡 完整版高階代碼（支援半馬/全馬分區插行與歷史刪除）請參閱專案根目錄的 `google_apps_script.js`。")

        c_g_save, c_g_test = st.columns(2)
        with c_g_save:
            if st.button("💾 儲存試算表設定", use_container_width=True):
                target_sheet = in_sheet_url.strip() if in_sheet_url else cur_sheet_url
                target_wh = in_webhook_url.strip() if in_webhook_url else cur_webhook
                if target_sheet:
                    save_gsheet_settings(target_sheet, target_wh)
                    st.cache_data.clear()
                    st.success("✅ 試算表設定已儲存！")
                    st.rerun()
                else:
                    save_gsheet_settings("", target_wh)
                    st.info("已清空自訂試算表，系統恢復為本地安全課表。")
                    st.rerun()
                    
        with c_g_test:
            if st.button("🧪 測試連線並同步課表", use_container_width=True):
                target_sheet = in_sheet_url.strip() if in_sheet_url else cur_sheet_url
                target_wh = in_webhook_url.strip() if in_webhook_url else cur_webhook
                if target_sheet:
                    save_gsheet_settings(target_sheet, target_wh)
                    with st.spinner("連線 Google 試算表中..."):
                        test_sched = load_schedule_data(force_reload=True)
                        if test_sched:
                            st.success(f"🎉 連線成功！已同步 {len(test_sched)} 週實戰課表。")
                        else:
                            st.error("連線失敗，請檢查網址或試算表共用權限。")
                else:
                    st.warning("請先輸入 Google 試算表網址")

    st.markdown("<div style='height:15px;'></div>", unsafe_allow_html=True)
    c_save, c_reset = st.columns([0.7, 0.3])
    with c_save:
        if st.button("💾 儲存並更新系統預設值", type="primary", use_container_width=True):
            def parse_to_min(s, default_min):
                try:
                    parts = list(map(int, s.strip().split(":")))
                    if len(parts) == 3:
                        return parts[0] * 60 + parts[1] + parts[2] / 60.0
                    elif len(parts) == 2:
                        return parts[0] + parts[1] / 60.0
                except:
                    pass
                return default_min

            pb_f_min = parse_to_min(pb_f_str, 271.0)
            pb_h_min = parse_to_min(pb_h_str, 112.55)

            new_profile = {
                "name": u_name,
                "age": u_age,
                "gender": u_gender,
                "weight_kg": u_weight,
                "max_hr": u_max_hr,
                "rest_hr": u_rest_hr,
                "lthr": u_lthr,
                "z2_min": u_z2_min,
                "z2_max": u_z2_max,
                "pb_full_time": pb_f_str,
                "pb_half_time": pb_h_str,
                "pb_full_min": round(pb_f_min, 2),
                "pb_half_min": round(pb_h_min, 2),
                "pb_full_label": pb_f_lbl,
                "pb_half_label": pb_h_lbl
            }
            save_user_profile(new_profile)
            st.session_state.user_profile = new_profile
            st.session_state.base_max_hr = u_max_hr
            st.session_state.base_rest_hr = u_rest_hr
            st.session_state.base_lthr = u_lthr
            st.session_state.base_z2_min = u_z2_min
            st.session_state.base_z2_max = u_z2_max
            st.success("✅ 個人設定已儲存並同步至系統！")
            st.rerun()
    with c_reset:
        if st.button("🔄 還原系統預設", use_container_width=True):
            system_defaults = {
                "name": "跑者",
                "age": 56,
                "gender": "男",
                "weight_kg": 53.0,
                "height_cm": 170.0,
                "max_hr": 197,
                "rest_hr": 57,
                "lthr": 181,
                "z2_min": 144,
                "z2_max": 159,
                "pb_full_time": "04:31:00",
                "pb_half_time": "01:52:33",
                "pb_full_min": 271.0,
                "pb_half_min": 112.55,
                "pb_full_label": "全馬 4:31:00 (2024台北馬)",
                "pb_half_label": "半馬 1:52:33 (2025台北馬)"
            }
            save_user_profile(system_defaults)
            st.session_state.user_profile = system_defaults
            st.session_state.base_max_hr = 197
            st.session_state.base_rest_hr = 57
            st.session_state.base_lthr = 181
            st.session_state.base_z2_min = 144
            st.session_state.base_z2_max = 159
            st.rerun()

# --- 4. 側邊欄：資料載入與同步中樞 ---
with st.sidebar:
    c_av, c_name, c_sett = st.columns([0.28, 0.44, 0.28])
    with c_av:
        avatar_path = None
        for p in ["assets/Edward.png", "assets/edward.png"]:
            if os.path.exists(p):
                avatar_path = p
                break
        if avatar_path:
            st.image(avatar_path, width=50)
        else:
            st.markdown("<div style='font-size: 2.2rem; line-height: 1;'>🏃</div>", unsafe_allow_html=True)
    with c_name:
        display_name = user_name if user_name else "跑者"
        st.markdown(f"<div style='padding-top: 4px; font-weight: 700; font-size: 1.15rem; color: #f8fafc; line-height: 1.2;'>{display_name}</div><div style='font-size: 0.72rem; color: #94a3b8;'>運動員基線</div>", unsafe_allow_html=True)
    with c_sett:
        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
        if st.button("⚙️ 設定", help="修改跑者個人生理基線與歷史最佳戰績 (支援任何新跑者開箱即用)"):
            open_profile_dialog()

    if user_name and user_name not in ["Edward", "跑者", "Runner"]:
        st.markdown(f"### 🏃 {user_name} 運動生理基線")
    else:
        st.markdown("### 🏃 運動生理基線")
    
    active_max_hr = st.session_state.get('base_max_hr', profile.get('max_hr', 197))
    active_rest_hr = st.session_state.get('base_rest_hr', profile.get('rest_hr', 57))
    active_lthr = st.session_state.get('base_lthr', profile.get('lthr', 181))
    active_z2_min = st.session_state.get('base_z2_min', profile.get('z2_min', 144))
    active_z2_max = st.session_state.get('base_z2_max', profile.get('z2_max', 159))

    st.session_state.active_max_hr = active_max_hr
    st.session_state.active_rest_hr = active_rest_hr
    st.session_state.active_lthr = active_lthr
    st.session_state.active_z2_min = active_z2_min
    st.session_state.active_z2_max = active_z2_max
    st.session_state.active_base_mode = st.session_state.get('base_source', '個人專屬基線')

    st.caption(f"Max HR: **{active_max_hr}** | Rest HR: **{active_rest_hr}** | LTHR: **{active_lthr}**")
    st.markdown(
        f"<span style='background: rgba(16,185,129,0.15); color: #10b981; padding: 3px 8px; border-radius: 6px; font-size: 0.8rem; font-weight: bold;'>Zone 2: {active_z2_min}–{active_z2_max} bpm (神聖有氧區間)</span>",
        unsafe_allow_html=True
    )
    st.divider()

    # --- 📅 2026 台北馬拉松衝刺課表常駐入口 ---
    render_sidebar_schedule_card()
    st.divider()

    # --- ☁️ Garmin Connect 雲端中樞 (主要資料來源) ---
    st.markdown("#### ☁️ Garmin Connect 雲端中樞")
    if garmin_cloud.has_valid_token():
        st.markdown("<span style='color: #10b981; font-size: 0.8rem; font-weight: bold;'>🟢 官方 Personal API 授權正常</span>", unsafe_allow_html=True)

        # 快捷鍵：一鍵同步晨檢與最新活動
        if st.button("⚡ 一鍵同步今日晨檢與最新活動", use_container_width=True, type="primary"):
            with st.spinner("從 Garmin Connect 雲端拉取中..."):
                client, login_msg = garmin_cloud.login_with_tokens()
                if client:
                    readiness, r_msg = garmin_cloud.fetch_today_readiness(client)
                    if readiness:
                        apply_synced_readiness(readiness)
                    # 同步手錶動態心率分區基線
                    zones, z_msg = garmin_cloud.fetch_user_hr_zones()
                    if zones:
                        st.session_state.base_max_hr = zones["max_hr"]
                        st.session_state.base_rest_hr = zones["rest_hr"]
                        st.session_state.base_lthr = zones["lthr"]
                        st.session_state.base_z2_min = zones["z2_min"]
                        st.session_state.base_z2_max = zones["z2_max"]
                        st.session_state.base_source = f"Garmin 手錶動態分區 ({zones['sport']})"
                    fit_p, a_msg = garmin_cloud.fetch_and_save_latest_activity(client)
                    if fit_p and os.path.exists(fit_p):
                        df, summary, _, tags = process_data(fit_p)
                        st.session_state.df = df
                        st.session_state.pending_summary = summary
                        st.session_state.pending_tags = tags
                        st.session_state.pending_file_name = a_msg
                    st.toast(f"✅ 晨檢與最新活動已同步！{a_msg if fit_p else ''}", icon="⚡")
                    st.rerun()
                else:
                    st.error(login_msg)

        # 雲端歷史跑步活動選取
        st.markdown("<div style='font-size: 0.85rem; font-weight: 600; margin-top: 10px; margin-bottom: 4px; color: #cbd5e1;'>選取 Garmin 雲端跑步活動：</div>", unsafe_allow_html=True)
        if "cloud_activities" not in st.session_state or not st.session_state.cloud_activities:
            with st.spinner("載入 Garmin 雲端活動清單..."):
                st.session_state.cloud_activities = garmin_cloud.fetch_recent_activities(limit=15)
        
        cloud_acts = st.session_state.get("cloud_activities", [])
        if cloud_acts:
            cloud_options = {a["label"]: a for a in cloud_acts}
            selected_cloud_label = st.selectbox(
                "Garmin 雲端活動", 
                options=list(cloud_options.keys()), 
                label_visibility="collapsed"
            )
            col_c1, col_c2 = st.columns([0.72, 0.28])
            with col_c1:
                if st.button("📥 載入選定雲端活動", use_container_width=True):
                    chosen = cloud_options[selected_cloud_label]
                    with st.spinner(f"從雲端下載並解析 {chosen['name']}..."):
                        save_p, msg = garmin_cloud.download_activity_fit(chosen["id"], f"temp_{chosen['id']}.fit")
                        if save_p and os.path.exists(save_p):
                            df, summary, _, tags = process_data(save_p)
                            st.session_state.df = df
                            st.session_state.pending_summary = summary
                            st.session_state.pending_tags = tags
                            st.session_state.pending_file_name = f"{chosen['date']} {chosen['name']} ({chosen['dist_km']}K)"
                            # 同步狀態指針至 active_activity.json
                            try:
                                with open("data/active_activity.json", "w", encoding="utf-8") as f_act:
                                    json.dump({
                                        "activity_id": str(chosen["id"]),
                                        "name": st.session_state.pending_file_name,
                                        "date": chosen.get("date", ""),
                                        "dist_km": chosen.get("dist_km", 0),
                                        "dur_str": chosen.get("dur_str", ""),
                                        "fit_path": save_p,
                                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")
                                    }, f_act, ensure_ascii=False, indent=2)
                                st.session_state.active_loaded_id = str(chosen["id"])
                            except Exception:
                                pass
                            st.success(f"✅ 已成功載入：{chosen['name']}")
                            st.rerun()
                        else:
                            st.error(f"下載失敗: {msg}")
            with col_c2:
                if st.button("🔄 刷新", use_container_width=True, help="重新整理 Garmin 雲端活動清單"):
                    st.session_state.cloud_activities = garmin_cloud.fetch_recent_activities(limit=15)
                    st.rerun()
        else:
            st.info("尚無雲端跑步活動紀錄或連線逾時")
            if st.button("🔄 重試載入清單", use_container_width=True):
                st.session_state.cloud_activities = garmin_cloud.fetch_recent_activities(limit=15)
                st.rerun()
    else:
        st.markdown("<span style='color: #f59e0b; font-size: 0.8rem; font-weight: bold;'>⚠️ 尚未綁定 Garmin 官方 API</span>", unsafe_allow_html=True)
        st.caption("請點擊左上方「⚙️ 設定」中的「☁️ Garmin 連結」頁籤輸入 API Token，享受全自動秒級同步。")
        if st.button("⚙️ 前往設定 Garmin 連結", use_container_width=True):
            open_profile_dialog()

    st.divider()

    with st.expander("📁 備用手動上傳 FIT / CSV", expanded=False):
        st.caption("非 Garmin 裝置或離線測試檔案手動匯入：")
        uploaded_file = st.file_uploader("上傳 FIT / CSV", type=["fit", "csv"], label_visibility="collapsed")
        if uploaded_file and uploaded_file.name != st.session_state.pending_file_name:
            file_ext = uploaded_file.name.split(".")[-1].lower()
            save_path = f"temp.{file_ext}"
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            with st.spinner("解析中..."):
                df, summary, _, tags = process_data(save_path)
                st.session_state.df = df
                st.session_state.pending_summary = summary
                st.session_state.pending_tags = tags
                st.session_state.pending_file_name = uploaded_file.name
            st.success(f"✅ {uploaded_file.name} 載入成功！")
            st.rerun()

    # 智慧同步機制：優先響應對話端 (Chat / MCP) 寫入的主動切換狀態
    ACTIVE_STATE_FILE = "data/active_activity.json"
    if os.path.exists(ACTIVE_STATE_FILE):
        try:
            with open(ACTIVE_STATE_FILE, "r", encoding="utf-8") as f_act:
                active_meta = json.load(f_act)
            act_id = str(active_meta.get("activity_id", ""))
            last_id = str(st.session_state.get("active_loaded_id", ""))
            if act_id and act_id != last_id:
                target_fit = active_meta.get("fit_path", "temp.fit")
                if os.path.exists(target_fit):
                    df, summary, _, tags = process_data(target_fit)
                    st.session_state.df = df
                    st.session_state.pending_summary = summary
                    st.session_state.pending_tags = tags
                    st.session_state.pending_file_name = active_meta.get("name", "雲端同步活動")
                    st.session_state.active_loaded_id = act_id
                    st.session_state.active_file_mtime = os.path.getmtime(ACTIVE_STATE_FILE)
                    st.toast(f"🚀 對話端已自動將戰情室切換至：{st.session_state.pending_file_name}", icon="⚡")
        except Exception:
            pass

    # 智慧即時心跳監聽：每 2 秒無感監控 data/active_activity.json，實現對話端免點擊即時自動推播
    @st.fragment(run_every="2s")
    def auto_sync_watcher():
        state_file = "data/active_activity.json"
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f_act:
                    active_meta = json.load(f_act)
                act_id = str(active_meta.get("activity_id", ""))
                curr_id = str(st.session_state.get("active_loaded_id", ""))
                # 只有在兩者皆存在且不相等時才觸發全域重新整理，避免初始空狀態引發無窮迴圈
                if act_id and curr_id and act_id != curr_id:
                    st.rerun(scope="app")
            except Exception:
                pass
        st.caption("⚡ 對話端即時同步中 (自動跳轉已開啟)")

    auto_sync_watcher()

    # 若尚未載入任何活動，預設由 temp.fit 初始化
    if st.session_state.df is None and os.path.exists("temp.fit"):
        try:
            df, summary, _, tags = process_data("temp.fit")
            st.session_state.df = df
            st.session_state.pending_summary = summary
            st.session_state.pending_tags = tags
            st.session_state.pending_file_name = "2026 長榮航空半程馬拉松 (21.26K)"
        except Exception:
            pass

# --- 5. 主畫面：三大分頁戰情看板 ---

# 頁首標題與跑者提醒
col_h_left, col_h_right = st.columns([0.7, 0.3])
with col_h_left:
    st.title("🏃 AI Coach 運動科學戰情看板")
with col_h_right:
    st.markdown("""
    <div style='background: rgba(59,130,246,0.1); border: 1px solid rgba(59,130,246,0.25); border-radius: 8px; padding: 8px 12px; font-size: 0.8rem;'>
        🤖 <strong>雙教練外腦已啟動：</strong><br>
        直接在 Antigravity 聊天室發問，享受頂級推理與動態會診！
    </div>
    """, unsafe_allow_html=True)

# 宣告五大核心分頁 (依照跑者每日使用動線優化：1.體能晨檢 -> 2.課表排程 -> 3.活動深度解析 -> 4.配速模擬與推演 -> 5.雙場對決比較)
tab_pmc, tab_schedule, tab_activity, tab_sim, tab_compare = st.tabs([
    "🔋 體能就緒與 PMC 負荷",
    "📅 8週課表實戰排程",
    "📈 單次活動深度剖析",
    "🎛️ 配速模擬與大賽推演",
    "⚔️ 雙場對決比較 (Head-to-Head)"
])

# ==========================================
# TAB 1: 體能就緒與 PMC 負荷管理
# ==========================================
with tab_pmc:
    st.markdown("### 🔋 每日晨脈就緒度 & PMC 體能管理中樞")
    st.caption("連動自律神經 HRV、晨脈、身體電量，評估今日就緒狀態；結合 Coggan 經典 42天 CTL / 7天 ATL / TSB 曲線掌控大賽巔峰！")

    # --- 1. 晨脈與每日就緒度 (Morning Readiness) ---
    st.markdown("#### 🌅 每日晨脈與體能就緒度 (Daily Readiness)")

    if garmin_cloud.has_valid_token():
        c_sync_info, c_sync_status = st.columns([0.72, 0.28])
        with c_sync_info:
            rhr_val = st.session_state.get('synced_rhr', 60)
            sleep_val = st.session_state.get('synced_sleep', 56)
            hrv_val = st.session_state.get('synced_hrv', 35)
            st.markdown(
                f"<div style='font-size: 0.88rem; color: #cbd5e1; padding-top: 4px;'>"
                f"📡 <strong>Garmin 雲端動態同步</strong>：晨脈 <code style='color:#38bdf8; font-size: 0.95rem;'>{rhr_val} bpm</code> | "
                f"睡眠 <code style='color:#38bdf8; font-size: 0.95rem;'>{sleep_val} 分</code> | "
                f"夜間 HRV <code style='color:#38bdf8; font-size: 0.95rem;'>{hrv_val} ms</code> "
                f"<span style='color: #64748b;'>（手錶更新後點擊側邊欄「⚡ 一鍵同步」即可即時更新）</span>"
                f"</div>",
                unsafe_allow_html=True
            )
        with c_sync_status:
            st.markdown("<div style='text-align: right; font-size: 0.8rem; color: #10b981; padding-top: 6px;'>🟢 雲端數據已連動</div>", unsafe_allow_html=True)
    else:
        st.info("💡 **自動化提示**：左側側邊欄已新增 **「☁️ Garmin Connect 雲端同步」**，點擊側邊欄「⚡ 一鍵同步」即可全自動載入晨脈、睡眠與 HRV！")
    
    r_col1, r_col2 = st.columns([0.48, 0.52])
    with r_col1:
        with st.container(border=True):
            st.markdown("**⚙️ 今日晨間生理感測模擬 (Garmin Sync)**")
            sync_ver = st.session_state.get("readiness_sync_ver", 0)
            cur_rhr = int(st.session_state.get('synced_rhr', 60))
            cur_sleep = int(st.session_state.get('synced_sleep', 56))

            mock_rhr = st.slider(
                "今日晨脈 (Rest HR, bpm)", 
                min_value=46, 
                max_value=66, 
                value=cur_rhr, 
                step=1, 
                key=f"slider_mock_rhr_{sync_ver}", 
                help=f"個人基線晨脈為 {active_rest_hr} bpm。"
            )
            mock_sleep = st.slider(
                "昨晚睡眠分數 (Sleep Score, 分)", 
                min_value=40, 
                max_value=100, 
                value=cur_sleep, 
                step=1, 
                key=f"slider_mock_sleep_{sync_ver}"
            )
            
            st.markdown("**夜間心率變異度 (HRV, 動態自律神經指標)**")
            hrv_input_mode = st.radio(
                "HRV 填寫模式",
                options=["⚡ 簡易模式 (直接依手錶 綠/橘/紅 狀態)", "🎯 數值模式 (自訂當前 Garmin 動態基線)"],
                horizontal=True,
                label_visibility="collapsed"
            )

            if "簡易模式" in hrv_input_mode:
                def_idx = 0
                if st.session_state.get('synced_hrv_status') == 'UNBALANCED': def_idx = 1
                elif st.session_state.get('synced_hrv_status') == 'LOW': def_idx = 2

                hrv_options = [
                    "🟢 平衡 (Balanced) — 落在灰色基線內 (如 10/18~10/24 穩健恢復)",
                    "🟡 不平衡 (Unbalanced) — 略低於基線 (如 10/13、10/16 橘色方塊)",
                    "🔴 偏低 (Low / Poor) — 顯著低於基線 (如 10/2~10/5 紅色三角)"
                ]

                hrv_quick = st.selectbox(
                    "Garmin 今日 HRV 狀態判定",
                    options=hrv_options,
                    index=def_idx,
                    key=f"select_hrv_quick_{sync_ver}",
                    help="直接對照 Garmin Connect 每日總計圖表上的圖示顏色即可，免去計算浮動基準。"
                )
                if "🟢" in hrv_quick:
                    hrv_tag = "🟢 平衡 (Balanced)"
                    hrv_col = "#10b981"
                    hrv_score = 45.0
                    mock_hrv_val = int(st.session_state.get('synced_hrv', 35))
                    hrv_desc = f"落在 Garmin 動態灰色基準帶內 ({mock_hrv_val} ms)，自律神經與副交感恢復穩定。"
                elif "🟡" in hrv_quick:
                    hrv_tag = "🟡 不平衡 (Unbalanced)"
                    hrv_col = "#f59e0b"
                    hrv_score = 35.0
                    mock_hrv_val = int(st.session_state.get('synced_hrv', 30))
                    hrv_desc = f"略低於 Garmin 動態基準帶 ({mock_hrv_val} ms)，身體正進行微幅代謝或組織修復，體能基底仍在。"
                else:
                    hrv_tag = "🔴 偏低 (Low / Poor)"
                    hrv_col = "#f43f5e"
                    hrv_score = 12.0
                    mock_hrv_val = 26
                    hrv_desc = "顯著跌破 Garmin 動態基準，交感神經處於過亢疲勞期，需充分休整。"

                st.markdown(f"<div style='font-size: 0.8rem; background: rgba(255,255,255,0.03); padding: 8px 10px; border-radius: 8px; border-left: 3px solid {hrv_col}; margin-top: 4px;'><strong style='color:{hrv_col};'>{hrv_tag}</strong>：{hrv_desc}</div>", unsafe_allow_html=True)

            else:
                c_base1, c_base2 = st.columns(2)
                cur_bmin = int(st.session_state.get('synced_b_min', 32))
                cur_bmax = int(st.session_state.get('synced_b_max', 39))
                cur_hrv = int(st.session_state.get('synced_hrv', 35))

                with c_base1:
                    b_min = st.number_input("Garmin 當前基線下限 (ms)", value=cur_bmin, min_value=20, max_value=60, step=1, key=f"num_b_min_{sync_ver}", help="從 Garmin 圖表灰色帶下緣讀取，目前為 32 ms")
                with c_base2:
                    b_max = st.number_input("Garmin 當前基線上限 (ms)", value=cur_bmax, min_value=25, max_value=70, step=1, key=f"num_b_max_{sync_ver}", help="從 Garmin 圖表灰色帶上緣讀取，目前為 39 ms")

                mock_hrv_val = st.slider("昨晚夜間平均 HRV (ms)", min_value=20, max_value=50, value=cur_hrv, step=1, key=f"slider_mock_hrv_{sync_ver}")

                if b_min <= mock_hrv_val <= b_max:
                    hrv_tag = "🟢 平衡 (Balanced)"
                    hrv_col = "#10b981"
                    hrv_score = 45.0
                    hrv_desc = f"{mock_hrv_val} ms 穩落於當前基準區間 ({b_min}–{b_max} ms)。"
                elif mock_hrv_val < b_min:
                    diff = b_min - mock_hrv_val
                    if diff <= 2:
                        hrv_tag = "🟡 不平衡 (輕微偏低)"
                        hrv_col = "#f59e0b"
                        hrv_score = 36.0
                        hrv_desc = f"{mock_hrv_val} ms 僅低於當前下限 {b_min} ms (-{diff}ms)，屬正常小波動。"
                    else:
                        hrv_tag = "🔴 偏低 (Low / Poor)"
                        hrv_col = "#f43f5e"
                        hrv_score = max(10.0, 30.0 - diff * 3)
                        hrv_desc = f"{mock_hrv_val} ms 顯著低於當前下限 {b_min} ms (-{diff}ms)，累積疲勞中。"
                else:
                    hrv_tag = "🔵 偏高 (High)"
                    hrv_col = "#38bdf8"
                    hrv_score = 38.0
                    hrv_desc = f"{mock_hrv_val} ms 高於當前上限 {b_max} ms。"

                st.markdown(f"<div style='font-size: 0.8rem; background: rgba(255,255,255,0.03); padding: 8px 10px; border-radius: 8px; border-left: 3px solid {hrv_col}; margin-top: 4px;'><strong style='color:{hrv_col};'>{hrv_tag}</strong>：{hrv_desc}</div>", unsafe_allow_html=True)

    # 計算綜合就緒度分數 (符合 Garmin Body Battery & Readiness 權重)
    rhr_penalty = max(0, (mock_rhr - 53) * 2.5)
    sleep_factor = (mock_sleep / 100) * 45
    readiness_score = int(np.clip(sleep_factor + hrv_score - rhr_penalty + 10, 20, 100))

    with r_col2:
        if readiness_score >= 82:
            status_text = "🟢 體能充沛 (極佳狀態)"
            status_color = "#10b981"
            if "🟢" in hrv_tag:
                luger_rec = f"睡眠 {mock_sleep} 分修復極佳！HRV 處於 {hrv_tag} 且晨脈僅 {mock_rhr} bpm 相當穩定，生化儲備與自律神經完全滿血！"
                pace_rec = f"就緒度達 {readiness_score} 分！今日按原定課表全力出擊（亞索800m/乳酸閾值/長跑皆宜）！"
            else:
                luger_rec = f"睡眠 {mock_sleep} 分高分修復！HRV 雖略受壓 ({mock_hrv_val} ms)，但晨脈僅 {mock_rhr} bpm，體能儲備足以消化訓練！"
                pace_rec = f"就緒度達 {readiness_score} 分！可照常吃課表，間歇若感到微喘組間多走動 10 秒即可。"
        elif readiness_score >= 65:
            status_text = "🟡 中度疲勞 (建議減量)"
            status_color = "#f59e0b"
            luger_rec = f"晨脈上浮至 {mock_rhr} bpm，HRV 狀態為 {hrv_tag}，交感神經微幅緊繃，心率飄移會比平時明顯。"
            pace_rec = "微調適配：間歇組數建議由 6 組縮減至 4 組，或巡航配速放寬 8-10 秒/km。"
        else:
            status_text = "🔴 嚴重疲勞 (禁止高強度)"
            status_color = "#f43f5e"
            luger_rec = f"⚠️ 警報！HRV 處於 {hrv_tag} ({mock_hrv_val} ms) 且晨脈高達 {mock_rhr} bpm，若強行吃課表極易引發阿基里斯腱發炎或免疫低下！"
            pace_rec = "強制煞車：今日取消強度課表，改為 Zone 2 慢跑 30 分鐘，或直接休跑以滾筒伸展。"

        st.markdown(f"""
        <div style='background: rgba(15,23,42,0.85); padding: 16px; border-radius: 12px; border: 1px solid {status_color}; height: 100%; display: flex; flex-direction: column; justify-content: space-between;'>
            <div>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <span style='font-size: 0.85rem; color: #94a3b8;'>今日體能就緒綜合指數</span>
                    <span style='font-weight: bold; color: {status_color}; font-size: 0.9rem;'>{status_text}</span>
                </div>
                <div style='font-size: 2.5rem; font-weight: 800; color: {status_color}; margin: 4px 0;'>
                    {readiness_score} <span style='font-size: 1rem; color: #64748b; font-weight: normal;'>/ 100</span>
                </div>
            </div>
            <div style='font-size: 0.8rem; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 8px;'>
                <p style='margin: 0 0 4px 0; color: #cbd5e1;'>🛡️ <strong>路格教練：</strong>{luger_rec}</p>
                <p style='margin: 0; color: #93c5fd;'>⚡ <strong>佩絲教練：</strong>{pace_rec}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    # --- 2. PMC 體能管理圖表 (Performance Management Chart) ---
    st.markdown("#### 📈 PMC 體能管理趨勢圖 (CTL 體能 / ATL 疲勞 / TSB 狀況)")
    st.caption("Coggan 運動科學經典：42天長期體能積累 (CTL)、7天急性疲勞 (ATL)、狀況平衡 (TSB = CTL - ATL)。掌握大賽超量恢復巔峰！")

    # --- 數據來源選擇 (Garmin 實體 vs 週期模擬) ---
    has_garmin = garmin_cloud.has_valid_token()
    source_options = []
    if has_garmin:
        source_options.append("☁️ Garmin Connect 真實體能負荷 (真實 CTL / ATL / TSB 軌跡)")
    source_options.append("🧪 訓練週期沙盤模擬 (Taper 減量 / Build 堆疊 / Base 基礎期)")

    col_src, col_btn = st.columns([3, 1])
    with col_src:
        pmc_source = st.radio("PMC 數據來源", options=source_options, horizontal=True, label_visibility="collapsed")
    with col_btn:
        force_sync = False
        if has_garmin and "Garmin" in pmc_source:
            if st.button("🔄 同步 Garmin 最新活動", use_container_width=True):
                force_sync = True

    df_pmc = None
    diagnosis_text = None
    diag_level = "info"
    data_note = ""

    if "Garmin" in pmc_source and has_garmin:
        with st.spinner("從 Garmin Connect 雲端拉取歷史活動與負荷..."):
            pmc_res, pmc_msg = garmin_cloud.fetch_user_pmc_data(force_refresh=force_sync)
            if pmc_res and "records" in pmc_res:
                df_all = pd.DataFrame(pmc_res["records"])
                df_all['Date'] = pd.to_datetime(df_all['Date'])
                
                # 時間跨度選擇
                col_range, col_info = st.columns([2, 3])
                with col_range:
                    time_window = st.select_slider(
                        "圖表檢視區間",
                        options=["最近 30 天", "最近 60 天", "最近 90 天", "近半年 (完整 180 天)"],
                        value="最近 90 天"
                    )
                with col_info:
                    cached_at_str = pmc_res.get("cached_at", "")[:16].replace("T", " ")
                    st.caption(f"📅 資料範圍：{pmc_res.get('earliest_date')} ～ {pmc_res.get('latest_date')} | 🕒 最近更新：{cached_at_str}")

                days_map = {"最近 30 天": 30, "最近 60 天": 60, "最近 90 天": 90, "近半年 (完整 180 天)": 185}
                days_filter = days_map.get(time_window, 90)
                cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_filter)
                df_pmc = df_all[df_all['Date'] >= cutoff].copy()
                
                summary = pmc_res.get("summary", {})
                curr_ctl = summary.get("ctl", df_pmc['CTL'].iloc[-1])
                curr_atl = summary.get("atl", df_pmc['ATL'].iloc[-1])
                curr_tsb = summary.get("tsb", df_pmc['TSB'].iloc[-1])
                diagnosis_text = summary.get("diagnosis", "")
                diag_level = summary.get("diag_level", "info")
                data_note = f"📊 數據源自 Garmin 官方 Firstbeat EPOC 運動負荷 (共累積 {pmc_res.get('total_days')} 天連續生理追蹤)"
            else:
                st.warning(f"未能取得 Garmin 歷史活動：{pmc_msg}，切換為模擬模式。")

    if df_pmc is None:
        pmc_mode = st.radio(
            "訓練週期模擬階段",
            options=["賽前 14 天減量超量恢復期 (Taper 衝刺 PB)", "專項體能堆疊期 (Build 巔峰強度)", "賽後休整與基礎有氧期 (Base Recovery)"],
            horizontal=True
        )
        np.random.seed(42)
        end_date = pd.Timestamp.now().floor('D')
        dates = pd.date_range(end=end_date, periods=60, freq='D')
        daily_tss = []
        for i in range(60):
            if "減量超量恢復" in pmc_mode:
                if i < 42:
                    tss = float(np.random.choice([0, 60, 85, 110, 75, 130, 0]))
                else:
                    tss = float(np.random.choice([0, 30, 45, 0, 40, 20, 0]))
            elif "專項體能堆疊" in pmc_mode:
                tss = float(np.random.choice([0, 75, 115, 90, 140, 0, 160]))
            else:
                tss = float(np.random.choice([0, 45, 60, 0, 50, 70, 0]))
            daily_tss.append(tss)

        ctl = [48.0]
        atl = [42.0]
        for t in daily_tss[1:]:
            ctl.append(ctl[-1] + (t - ctl[-1]) / 42.0)
            atl.append(atl[-1] + (t - atl[-1]) / 7.0)

        tsb = [c - a for c, a in zip(ctl, atl)]
        df_pmc = pd.DataFrame({
            'Date': dates,
            'TSS': daily_tss,
            'CTL': [round(x, 1) for x in ctl],
            'ATL': [round(x, 1) for x in atl],
            'TSB': [round(x, 1) for x in tsb],
            'Details': ["沙盤模擬負荷"] * 60
        })
        curr_ctl = df_pmc['CTL'].iloc[-1]
        curr_atl = df_pmc['ATL'].iloc[-1]
        curr_tsb = df_pmc['TSB'].iloc[-1]
        data_note = "🧪 模式：數值模型沙盤推演 (非真實紀錄)"

    # 繪製雙子圖 PMC Plotly
    fig_pmc = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("CTL 體能 (42天) vs ATL 疲勞 (7天) 與每日運動負荷", "TSB 競技狀況指數 (超量恢復與黃金減量窗口)"),
        row_heights=[0.6, 0.4]
    )

    # TSS / 負荷柱狀
    hover_tss = [f"<b>{d.strftime('%Y-%m-%d')}</b><br>負荷: {tss:.1f}<br>明細: {det}" for d, tss, det in zip(df_pmc['Date'], df_pmc['TSS'], df_pmc['Details'])]
    fig_pmc.add_trace(
        go.Bar(
            x=df_pmc['Date'], 
            y=df_pmc['TSS'], 
            name="每日訓練負荷 (TSS / EPOC)", 
            marker_color='rgba(148, 163, 184, 0.35)',
            hovertext=hover_tss,
            hoverinfo="text"
        ),
        row=1, col=1
    )
    # CTL 曲線 (體能)
    fig_pmc.add_trace(
        go.Scatter(
            x=df_pmc['Date'], 
            y=df_pmc['CTL'], 
            name="CTL 體能 (Fitness, 42天)", 
            line=dict(color="#3b82f6", width=2.8)
        ),
        row=1, col=1
    )
    # ATL 曲線 (疲勞)
    fig_pmc.add_trace(
        go.Scatter(
            x=df_pmc['Date'], 
            y=df_pmc['ATL'], 
            name="ATL 疲勞 (Fatigue, 7天)", 
            line=dict(color="#f43f5e", width=2.2, dash='dot')
        ),
        row=1, col=1
    )

    # TSB 曲線與正負填色
    tsb_colors = ['#10b981' if v >= 0 else '#ef4444' for v in df_pmc['TSB']]
    fig_pmc.add_trace(
        go.Bar(x=df_pmc['Date'], y=df_pmc['TSB'], name="TSB 競技狀況", marker_color=tsb_colors),
        row=2, col=1
    )
    fig_pmc.add_hline(y=0, line_color="#94a3b8", line_width=1, row=2, col=1)
    fig_pmc.add_hrect(
        y0=10, y1=25,
        fillcolor="rgba(16, 185, 129, 0.22)",
        line_width=0,
        annotation_text="🏆 破 PB 黃金減量超量恢復窗口 (+10 ~ +25 TSB)",
        annotation_position="top left",
        row=2, col=1
    )

    fig_pmc.update_layout(
        template="plotly_dark",
        height=530,
        margin=dict(l=40, r=40, t=40, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified"
    )
    st.plotly_chart(fig_pmc, use_container_width=True)

    # PMC 三大指標摘要
    p1, p2, p3 = st.columns(3)
    with p1:
        st.markdown(f"<div class='metric-card'><div class='metric-val' style='color:#3b82f6;'>{curr_ctl:.1f}</div><div class='metric-lbl'>長期體能 (CTL / Fitness)</div></div>", unsafe_allow_html=True)
    with p2:
        st.markdown(f"<div class='metric-card'><div class='metric-val' style='color:#f43f5e;'>{curr_atl:.1f}</div><div class='metric-lbl'>短期疲勞 (ATL / Fatigue)</div></div>", unsafe_allow_html=True)
    with p3:
        tsb_c = "#10b981" if curr_tsb >= 0 else "#f43f5e"
        st.markdown(f"<div class='metric-card'><div class='metric-val' style='color:{tsb_c};'>{curr_tsb:+.1f}</div><div class='metric-lbl'>競技狀況 (TSB / Form)</div></div>", unsafe_allow_html=True)

    # 教練會診評語
    if diagnosis_text:
        bg_col = "rgba(16, 185, 129, 0.12)" if diag_level == "success" else ("rgba(245, 158, 11, 0.12)" if diag_level == "warning" else ("rgba(239, 68, 68, 0.15)" if diag_level == "danger" else "rgba(59, 130, 246, 0.12)"))
        border_col = "#10b981" if diag_level == "success" else ("#f59e0b" if diag_level == "warning" else ("#ef4444" if diag_level == "danger" else "#3b82f6"))
        st.markdown(f"""
        <div style='background:{bg_col}; border-left: 4px solid {border_col}; border-radius: 8px; padding: 12px 16px; margin-top: 10px;'>
            <div style='font-size: 0.95rem; font-weight: 600; color: #f8fafc;'>雙教練會診狀態診斷：</div>
            <div style='font-size: 0.9rem; color: #cbd5e1; margin-top: 4px;'>{diagnosis_text}</div>
            <div style='font-size: 0.78rem; color: #94a3b8; margin-top: 6px;'>{data_note}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.caption(data_note)

# TAB 2: 雙教練課表模擬與大賽推演
# ==========================================
# ==========================================
# TAB 2: 8週課表實戰排程與執行中樞
# ==========================================
with tab_schedule:
    render_schedule_tab_section()

# TAB 3: 單次活動深度剖析 (圖表與每公里明細)
# ==========================================
with tab_activity:
    curr_name = st.session_state.get('pending_file_name', '')
    if curr_name:
        st.markdown(f"<div style='background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 8px; padding: 8px 14px; font-size: 0.85rem; color: #94a3b8; margin-bottom: 16px;'>📍 當前展示活動：<strong style='color:#38bdf8;'>{curr_name}</strong></div>", unsafe_allow_html=True)
    if st.session_state.df is not None and not st.session_state.df.empty:
        df = st.session_state.df
        
        # 1. 核心基礎數值
        tot_km = df['dist_km'].sum() if 'dist_km' in df.columns else len(df)
        avg_hr = df['heart_rate'].mean() if 'heart_rate' in df.columns and df['heart_rate'].notna().any() else None
        max_hr = df['heart_rate'].max() if 'heart_rate' in df.columns and df['heart_rate'].notna().any() else None
        avg_cad = df['cadence'].mean() if 'cadence' in df.columns and df['cadence'].notna().any() else None
        avg_pace_val = df['pace'].mean() if 'pace' in df.columns and df['pace'].notna().any() else None
        
        if avg_pace_val and not np.isnan(avg_pace_val):
            avg_pace_str = f"{int(avg_pace_val)}:{int((avg_pace_val % 1)*60):02d}"
        else:
            avg_pace_str = "N/A"

        # 頂部第 1 列：總里程、配速、心率、步頻、最高心率
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.markdown(f"<div class='metric-card'><div class='metric-val'>{tot_km:.2f} km</div><div class='metric-lbl'>總里程</div></div>", unsafe_allow_html=True)
        with m2:
            st.markdown(f"<div class='metric-card'><div class='metric-val'>{avg_pace_str}</div><div class='metric-lbl'>平均配速 (/km)</div></div>", unsafe_allow_html=True)
        with m3:
            hr_display = f"{avg_hr:.0f} bpm" if avg_hr and not np.isnan(avg_hr) else "N/A"
            st.markdown(f"<div class='metric-card'><div class='metric-val' style='color:#f43f5e;'>{hr_display}</div><div class='metric-lbl'>平均心率</div></div>", unsafe_allow_html=True)
        with m4:
            cad_display = f"{avg_cad:.0f} spm" if avg_cad and not np.isnan(avg_cad) else "N/A"
            st.markdown(f"<div class='metric-card'><div class='metric-val' style='color:#fbbf24;'>{cad_display}</div><div class='metric-lbl'>平均步頻 (SPM)</div></div>", unsafe_allow_html=True)
        with m5:
            max_hr_display = f"{max_hr:.0f} bpm" if max_hr and not np.isnan(max_hr) else "N/A"
            st.markdown(f"<div class='metric-card'><div class='metric-val' style='color:#a855f7;'>{max_hr_display}</div><div class='metric-lbl'>最高心率</div></div>", unsafe_allow_html=True)

        # 頂部第 2 列：高階跑姿動力學金牌摘要 (步幅、觸地、垂直振幅、移動效率比、左右平衡、功率)
        avg_step = df['step_length'].mean() if 'step_length' in df.columns and df['step_length'].notna().any() else None
        avg_gct = df['gct'].mean() if 'gct' in df.columns and df['gct'].notna().any() else None
        avg_vo = df['vertical_osc'].mean() if 'vertical_osc' in df.columns and df['vertical_osc'].notna().any() else None
        avg_vr = df['vertical_ratio'].mean() if 'vertical_ratio' in df.columns and df['vertical_ratio'].notna().any() else None
        avg_bal = df['gct_balance'].mean() if 'gct_balance' in df.columns and df['gct_balance'].notna().any() else None
        avg_pwr = df['power'].mean() if 'power' in df.columns and df['power'].notna().any() else None

        has_dynamics = any(v is not None for v in [avg_step, avg_gct, avg_vo, avg_vr, avg_bal, avg_pwr])
        if has_dynamics:
            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            d1, d2, d3, d4, d5, d6 = st.columns(6)
            with d1:
                step_str = f"{avg_step:.1f} cm" if avg_step else "—"
                st.markdown(f"<div class='metric-card'><div class='metric-val' style='font-size:1.15rem; color:#c084fc;'>{step_str}</div><div class='metric-lbl'>👣 平均步幅</div></div>", unsafe_allow_html=True)
            with d2:
                gct_str = f"{avg_gct:.0f} ms" if avg_gct else "—"
                st.markdown(f"<div class='metric-card'><div class='metric-val' style='font-size:1.15rem; color:#34d399;'>{gct_str}</div><div class='metric-lbl'>⚡ 平均觸地時間</div></div>", unsafe_allow_html=True)
            with d3:
                vo_str = f"{avg_vo:.1f} cm" if avg_vo else "—"
                st.markdown(f"<div class='metric-card'><div class='metric-val' style='font-size:1.15rem; color:#38bdf8;'>{vo_str}</div><div class='metric-lbl'>📐 垂直振幅</div></div>", unsafe_allow_html=True)
            with d4:
                vr_str = f"{avg_vr:.1f} %" if avg_vr else "—"
                st.markdown(f"<div class='metric-card'><div class='metric-val' style='font-size:1.15rem; color:#f59e0b;'>{vr_str}</div><div class='metric-lbl'>🎯 移動效率(垂直比)</div></div>", unsafe_allow_html=True)
            with d5:
                bal_str = f"{avg_bal:.1f}% 左" if avg_bal else "—"
                st.markdown(f"<div class='metric-card'><div class='metric-val' style='font-size:1.15rem; color:#ec4899;'>{bal_str}</div><div class='metric-lbl'>⚖️ 左右平衡</div></div>", unsafe_allow_html=True)
            with d6:
                pwr_str = f"{avg_pwr:.0f} W" if avg_pwr else "—"
                st.markdown(f"<div class='metric-card'><div class='metric-val' style='font-size:1.15rem; color:#fb7185;'>{pwr_str}</div><div class='metric-lbl'>⚡ 平均功率</div></div>", unsafe_allow_html=True)

        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

        # 視覺化控制列
        col_c_head, col_c_mode = st.columns([0.48, 0.52])
        with col_c_head:
            st.markdown("#### 📈 每公里運動科學走勢圖")
        with col_c_mode:
            chart_view_mode = st.radio(
                "圖表視圖模式",
                options=["📊 Garmin 經典分層聯動子圖 (推薦)", "📈 趨勢歸一化對照 (% Baseline)"],
                horizontal=True,
                label_visibility="collapsed"
            )

        if 'lap' in df.columns:
            x_axis = pd.to_numeric(df['lap'], errors='coerce').fillna(1).astype(int)
        else:
            x_axis = list(range(1, len(df) + 1))

        p_valid = df['pace'].dropna() if 'pace' in df.columns else pd.Series(dtype=float)
        hr_valid = df['heart_rate'].dropna() if 'heart_rate' in df.columns else pd.Series(dtype=float)
        cur_z2_max = st.session_state.get('active_z2_max', 159)
        cur_lthr = st.session_state.get('active_lthr', 181)

        # 檢查可用的高階跑姿與動力學欄位
        avail_dyn_opts = []
        if any(c in df.columns and df[c].notna().any() for c in ['step_length', 'gct']):
            avail_dyn_opts.append("👣 步幅 (cm) vs 觸地時間 (ms)")
        if any(c in df.columns and df[c].notna().any() for c in ['vertical_osc', 'vertical_ratio']):
            avail_dyn_opts.append("📐 垂直振幅 (cm) vs 移動效率比 (%)")
        if any(c in df.columns and df[c].notna().any() for c in ['cadence', 'power']):
            avail_dyn_opts.append("⚡ 步頻 (SPM) vs 跑步功率 (W)")
        if 'gct_balance' in df.columns and df['gct_balance'].notna().any():
            avail_dyn_opts.append("⚖️ 左右觸地平衡 (%)")

        if "分層聯動子圖" in chart_view_mode:
            has_row3 = len(avail_dyn_opts) > 0
            selected_dyn_group = "👣 步幅 (cm) vs 觸地時間 (ms)"
            if has_row3:
                c_dyn_lbl, c_dyn_sel = st.columns([0.32, 0.68])
                with c_dyn_lbl:
                    st.caption("🔍 **第 3 層跑姿動力學切換：**")
                with c_dyn_sel:
                    selected_dyn_group = st.selectbox(
                        "第 3 層動力學指標切換", 
                        options=avail_dyn_opts, 
                        label_visibility="collapsed"
                    )

            rows_cnt = 3 if has_row3 else 2
            r_heights = [0.38, 0.34, 0.28] if rows_cnt == 3 else [0.52, 0.48]
            
            sub_titles = [
                '⏱️ 配速走勢 (min/km，越快越往上)',
                '💓 心率走勢與生理防線 (Zone 2 & LTHR)',
            ]
            if rows_cnt == 3:
                sub_titles.append(f'🏃 高階動力學走勢：{selected_dyn_group}')

            fig = make_subplots(
                rows=rows_cnt, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.11,
                row_heights=r_heights,
                subplot_titles=sub_titles,
                specs=[[{}], [{}], [{'secondary_y': True}]] if rows_cnt == 3 else [[{}], [{}]]
            )

            # Subplot 1: 配速
            if not p_valid.empty:
                fig.add_trace(go.Scatter(
                    x=x_axis, y=df['pace'],
                    name="⏱️ 配速",
                    mode="lines+markers",
                    line=dict(color="#3b82f6", width=2.8),
                    marker=dict(size=5, color="#60a5fa"),
                    text=df['pace_str'] if 'pace_str' in df.columns else None,
                    hovertemplate="⏱️ 配速: <b>%{text} /km</b><extra></extra>"
                ), row=1, col=1)
                
                p_min, p_max = p_valid.min(), p_valid.max()
                fig.update_yaxes(
                    title_text="配速 (/km)",
                    autorange="reversed",
                    range=[p_max + 0.35, p_min - 0.35],
                    row=1, col=1
                )
                if avg_pace_val and not np.isnan(avg_pace_val):
                    fig.add_hline(
                        y=avg_pace_val, line_dash="dash", line_color="rgba(148, 163, 184, 0.6)",
                        annotation_text=f"平均 {avg_pace_str}", annotation_position="top left",
                        row=1, col=1
                    )

            # Subplot 2: 心率
            if not hr_valid.empty:
                fig.add_trace(go.Scatter(
                    x=x_axis, y=df['heart_rate'],
                    name="💓 心率",
                    mode="lines+markers",
                    line=dict(color="#f43f5e", width=2.8),
                    marker=dict(size=5, color="#fb7185"),
                    hovertemplate="💓 心率: <b>%{y:.0f} bpm</b><extra></extra>"
                ), row=2, col=1)
                
                hr_min, hr_max = hr_valid.min(), hr_valid.max()
                fig.update_yaxes(
                    title_text="心率 (bpm)",
                    range=[min(hr_min - 6, cur_z2_max - 10), max(hr_max + 6, cur_lthr + 8)],
                    row=2, col=1
                )
                fig.add_hline(y=cur_z2_max, line_dash="dot", line_color="#10b981", annotation_text=f"Zone 2 上限 ({cur_z2_max} bpm)", row=2, col=1)
                fig.add_hline(y=cur_lthr, line_dash="dash", line_color="#ef4444", annotation_text=f"LTHR 乳酸閾值 ({cur_lthr} bpm)", row=2, col=1)

            # Subplot 3: 跑姿動力學
            if rows_cnt == 3:
                if "步幅" in selected_dyn_group and "觸地" in selected_dyn_group:
                    if 'step_length' in df.columns and df['step_length'].notna().any():
                        fig.add_trace(go.Scatter(
                            x=x_axis, y=df['step_length'],
                            name="👣 步幅 (cm)",
                            mode="lines+markers",
                            line=dict(color="#c084fc", width=2.2),
                            marker=dict(size=4),
                            hovertemplate="👣 步幅: <b>%{y:.1f} cm</b><extra></extra>"
                        ), row=3, col=1, secondary_y=False)
                        st_valid = df['step_length'].dropna()
                        fig.update_yaxes(
                            title_text="步幅 (cm)",
                            range=[st_valid.min() - 3, st_valid.max() + 3],
                            row=3, col=1, secondary_y=False
                        )

                    if 'gct' in df.columns and df['gct'].notna().any():
                        fig.add_trace(go.Scatter(
                            x=x_axis, y=df['gct'],
                            name="⚡ 觸地時間 (ms)",
                            mode="lines+markers",
                            line=dict(color="#34d399", width=2.2, dash="dot"),
                            marker=dict(size=4),
                            hovertemplate="⚡ 觸地時間: <b>%{y:.0f} ms</b><extra></extra>"
                        ), row=3, col=1, secondary_y=True)
                        gct_valid = df['gct'].dropna()
                        fig.update_yaxes(
                            title_text="觸地 (ms，越短越好)",
                            autorange="reversed",
                            range=[gct_valid.max() + 8, gct_valid.min() - 8],
                            row=3, col=1, secondary_y=True
                        )

                elif "垂直振幅" in selected_dyn_group:
                    if 'vertical_osc' in df.columns and df['vertical_osc'].notna().any():
                        fig.add_trace(go.Scatter(
                            x=x_axis, y=df['vertical_osc'],
                            name="📐 垂直振幅 (cm)",
                            mode="lines+markers",
                            line=dict(color="#f59e0b", width=2.2),
                            marker=dict(size=4),
                            hovertemplate="📐 垂直振幅: <b>%{y:.1f} cm</b><extra></extra>"
                        ), row=3, col=1, secondary_y=False)
                        vo_valid = df['vertical_osc'].dropna()
                        fig.update_yaxes(
                            title_text="垂直振幅 (cm)",
                            range=[vo_valid.min() - 0.5, vo_valid.max() + 0.5],
                            row=3, col=1, secondary_y=False
                        )

                    if 'vertical_ratio' in df.columns and df['vertical_ratio'].notna().any():
                        fig.add_trace(go.Scatter(
                            x=x_axis, y=df['vertical_ratio'],
                            name="🎯 移動效率/垂直比 (%)",
                            mode="lines+markers",
                            line=dict(color="#ec4899", width=2.2, dash="dot"),
                            marker=dict(size=4),
                            hovertemplate="🎯 垂直比: <b>%{y:.1f}%</b><extra></extra>"
                        ), row=3, col=1, secondary_y=True)
                        vr_valid = df['vertical_ratio'].dropna()
                        fig.update_yaxes(
                            title_text="垂直比 (%)，越低越好",
                            autorange="reversed",
                            range=[vr_valid.max() + 1.0, vr_valid.min() - 1.0],
                            row=3, col=1, secondary_y=True
                        )

                elif "步頻" in selected_dyn_group:
                    if 'cadence' in df.columns and df['cadence'].notna().any():
                        fig.add_trace(go.Scatter(
                            x=x_axis, y=df['cadence'],
                            name="👣 步頻 (SPM)",
                            mode="lines+markers",
                            line=dict(color="#fbbf24", width=2.2),
                            marker=dict(size=4),
                            hovertemplate="👣 步頻: <b>%{y:.0f} spm</b><extra></extra>"
                        ), row=3, col=1, secondary_y=False)
                        cad_v = df['cadence'].dropna()
                        fig.update_yaxes(
                            title_text="步頻 (SPM)",
                            range=[cad_v.min() - 4, cad_v.max() + 4],
                            row=3, col=1, secondary_y=False
                        )

                    if 'power' in df.columns and df['power'].notna().any():
                        fig.add_trace(go.Scatter(
                            x=x_axis, y=df['power'],
                            name="⚡ 跑步功率 (W)",
                            mode="lines+markers",
                            line=dict(color="#06b6d4", width=2.2, dash="dot"),
                            marker=dict(size=4),
                            hovertemplate="⚡ 跑步功率: <b>%{y:.0f} W</b><extra></extra>"
                        ), row=3, col=1, secondary_y=True)
                        pwr_valid = df['power'].dropna()
                        fig.update_yaxes(
                            title_text="功率 (Watts)",
                            range=[pwr_valid.min() - 10, pwr_valid.max() + 10],
                            row=3, col=1, secondary_y=True
                        )

                elif "左右" in selected_dyn_group:
                    if 'gct_balance' in df.columns and df['gct_balance'].notna().any():
                        fig.add_trace(go.Scatter(
                            x=x_axis, y=df['gct_balance'],
                            name="⚖️ 左右觸地平衡 (%)",
                            mode="lines+markers",
                            line=dict(color="#10b981", width=2.2),
                            marker=dict(size=4),
                            hovertemplate="⚖️ 觸地平衡: <b>%{y:.1f}%</b><extra></extra>"
                        ), row=3, col=1, secondary_y=False)
                        fig.add_hline(y=50.0, line_dash="dash", line_color="#94a3b8", annotation_text="50.0% 完美對稱", row=3, col=1)
                        bal_v = df['gct_balance'].dropna()
                        fig.update_yaxes(
                            title_text="左右觸地平衡 (%)",
                            range=[min(47.0, bal_v.min() - 1.0), max(53.0, bal_v.max() + 1.0)],
                            row=3, col=1, secondary_y=False
                        )

            # 全子圖跨層同步貫穿導引線 (Spikeline) 與全指標聯動追蹤
            # 關鍵突破：Plotly make_subplots 預設會為每層分配獨立的 xaxis/xaxis2/xaxis3，
            # 導致 hover 與 spikeline 被限制在個別子圖。此處將全 trace 與 y 軸統一綁定至主 x 軸 ('x')，
            # 徹底打破層級藩籬，由頂至底一條導引線完全貫穿所有子圖，並同步聯動全指標 hover！
            fig.update_traces(xaxis="x")
            fig.update_yaxes(anchor="x")

            bottom_y = f"y{rows_cnt}"
            fig.layout.xaxis.anchor = bottom_y
            fig.layout.xaxis.matches = None
            fig.layout.xaxis.showticklabels = True
            fig.layout.xaxis.title = "公里數 (km)"

            fig.layout.xaxis.showspikes = True
            fig.layout.xaxis.spikemode = "across"
            fig.layout.xaxis.spikesnap = "cursor"
            fig.layout.xaxis.spikedash = "solid"
            fig.layout.xaxis.spikethickness = 1.8
            fig.layout.xaxis.spikecolor = "#f43f5e"

            # 圖表整體佈局：圖例靠左避開右側 Modebar 工具列，啟用跨層 hoversubplots 聯動
            fig.update_layout(
                template="plotly_dark",
                height=740 if rows_cnt == 3 else 530,
                hovermode="x",
                hoversubplots="axis",
                hoverlabel=dict(
                    bgcolor="rgba(15, 23, 42, 0.60)",      # 半透明霧透底色，透視後方折線
                    bordercolor="rgba(148, 163, 184, 0.35)", # 簡約質感邊框
                    font=dict(size=12, color="#ffffff"),
                    align="left"
                ),
                margin=dict(l=40, r=40, t=55, b=45),
                legend=dict(
                    orientation="h", 
                    yanchor="bottom", 
                    y=1.03, 
                    xanchor="left", 
                    x=0.0
                )
            )
            st.plotly_chart(fig, use_container_width=True)

        else:
            # 趨勢歸一化對照 (% Baseline)
            st.caption("💡 **歸一化解析說明**：將各項跑姿與生理數據除以全程平均值 (100% 基準線)，全指標放在同一比例尺直接對比，跑姿衰退與心率漂移一目了然！游標懸停將直接顯示每公里的真實物理數值。")
            fig_norm = go.Figure()
            fig_norm.add_hline(y=100, line_dash="solid", line_color="rgba(148, 163, 184, 0.4)", annotation_text="100% (全程平均基準)")

            if not p_valid.empty:
                norm_p = (p_valid.mean() / df['pace']) * 100
                p_text = [f"{p} /km" for p in df['pace_str']] if 'pace_str' in df.columns else [f"{p:.2f} /km" for p in df['pace']]
                fig_norm.add_trace(go.Scatter(
                    x=x_axis, y=norm_p,
                    name="⏱️ 配速",
                    mode="lines+markers",
                    line=dict(color="#3b82f6", width=2.5),
                    customdata=p_text,
                    hovertemplate="⏱️ 配速: <b>%{customdata}</b><extra></extra>"
                ))

            if not hr_valid.empty:
                norm_hr = (df['heart_rate'] / hr_valid.mean()) * 100
                hr_text = [f"{h:.0f} bpm" if pd.notna(h) else "-" for h in df['heart_rate']]
                fig_norm.add_trace(go.Scatter(
                    x=x_axis, y=norm_hr,
                    name="💓 心率",
                    mode="lines+markers",
                    line=dict(color="#f43f5e", width=2.5),
                    customdata=hr_text,
                    hovertemplate="💓 心率: <b>%{customdata}</b><extra></extra>"
                ))

            if 'step_length' in df.columns and df['step_length'].notna().any():
                norm_step = (df['step_length'] / df['step_length'].mean()) * 100
                step_text = [f"{s:.1f} cm" if pd.notna(s) else "-" for s in df['step_length']]
                fig_norm.add_trace(go.Scatter(
                    x=x_axis, y=norm_step,
                    name="👣 步幅 (cm)",
                    mode="lines+markers",
                    line=dict(color="#c084fc", width=2.2),
                    customdata=step_text,
                    hovertemplate="👣 步幅: <b>%{customdata}</b><extra></extra>"
                ))

            if 'gct' in df.columns and df['gct'].notna().any():
                norm_gct = (df['gct'] / df['gct'].mean()) * 100
                gct_text = [f"{g:.0f} ms" if pd.notna(g) else "-" for g in df['gct']]
                fig_norm.add_trace(go.Scatter(
                    x=x_axis, y=norm_gct,
                    name="⚡ 觸地時間 (ms)",
                    mode="lines+markers",
                    line=dict(color="#34d399", width=2.0, dash="dot"),
                    customdata=gct_text,
                    hovertemplate="⚡ 觸地時間: <b>%{customdata}</b><extra></extra>"
                ))

            if 'vertical_osc' in df.columns and df['vertical_osc'].notna().any():
                norm_vo = (df['vertical_osc'] / df['vertical_osc'].mean()) * 100
                vo_text = [f"{v:.1f} cm" if pd.notna(v) else "-" for v in df['vertical_osc']]
                fig_norm.add_trace(go.Scatter(
                    x=x_axis, y=norm_vo,
                    name="📐 垂直振幅 (cm)",
                    mode="lines+markers",
                    line=dict(color="#f59e0b", width=2.0),
                    customdata=vo_text,
                    hovertemplate="📐 垂直振幅: <b>%{customdata}</b><extra></extra>"
                ))

            if 'vertical_ratio' in df.columns and df['vertical_ratio'].notna().any():
                norm_vr = (df['vertical_ratio'] / df['vertical_ratio'].mean()) * 100
                vr_text = [f"{v:.1f}%" if pd.notna(v) else "-" for v in df['vertical_ratio']]
                fig_norm.add_trace(go.Scatter(
                    x=x_axis, y=norm_vr,
                    name="🎯 垂直比 (%)",
                    mode="lines+markers",
                    line=dict(color="#ec4899", width=2.0, dash="dot"),
                    customdata=vr_text,
                    hovertemplate="🎯 垂直比: <b>%{customdata}</b><extra></extra>"
                ))

            if 'power' in df.columns and df['power'].notna().any():
                norm_pwr = (df['power'] / df['power'].mean()) * 100
                pwr_text = [f"{p:.0f} W" if pd.notna(p) else "-" for p in df['power']]
                fig_norm.add_trace(go.Scatter(
                    x=x_axis, y=norm_pwr,
                    name="⚡ 跑步功率 (W)",
                    mode="lines+markers",
                    line=dict(color="#06b6d4", width=2.0),
                    customdata=pwr_text,
                    hovertemplate="⚡ 跑步功率: <b>%{customdata}</b><extra></extra>"
                ))

            if 'cadence' in df.columns and df['cadence'].notna().any():
                norm_cad = (df['cadence'] / df['cadence'].mean()) * 100
                cad_text = [f"{c:.0f} spm" if pd.notna(c) else "-" for c in df['cadence']]
                fig_norm.add_trace(go.Scatter(
                    x=x_axis, y=norm_cad,
                    name="👣 步頻 (SPM)",
                    mode="lines",
                    line=dict(color="#fbbf24", width=1.8, dash="dot"),
                    customdata=cad_text,
                    hovertemplate="👣 步頻: <b>%{customdata}</b><extra></extra>"
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
                template="plotly_dark",
                height=500,
                xaxis_title="公里數 (km)",
                yaxis_title="相對基準百分比 (%)",
                hovermode="x",
                hoverlabel=dict(
                    bgcolor="rgba(15, 23, 42, 0.60)",      # 半透明霧透底色，透視後方折線
                    bordercolor="rgba(148, 163, 184, 0.35)", # 簡約質感邊框
                    font=dict(size=12, color="#ffffff"),
                    align="left"
                ),
                margin=dict(l=40, r=40, t=55, b=45),
                legend=dict(
                    orientation="h", 
                    yanchor="bottom", 
                    y=1.03, 
                    xanchor="left", 
                    x=0.0
                )
            )
            st.plotly_chart(fig_norm, use_container_width=True)

        # ========================================================
        # 4. 步態生物力學五維雷達天平 & 雙教練臨床會診
        # ========================================================
        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
        col_radar_left, col_radar_right = st.columns([0.45, 0.55])
        
        with col_radar_left:
            st.markdown("#### 🕸️ 步態力學五維雷達天平")
            radar_categories = ["步頻節奏", "觸地剛性", "推蹬步幅", "垂直效率", "心血管能效"]
            
            # 單次活動指標取值
            cad_val = float(avg_cad) if avg_cad else 180.0
            gct_val = float(avg_gct) if avg_gct else 237.0
            step_val = float(avg_step) if avg_step else 100.0
            vr_val = float(avg_vr) if avg_vr else 7.5
            ef_val = float((1000.0 / avg_pace_val) / avg_hr) if (avg_pace_val and avg_hr and avg_pace_val > 0 and avg_hr > 0) else 1.0
            
            # 運動科學標準化評分 (校準至 50~100 分)
            score_cad = float(np.clip(70.0 + (cad_val - 160.0) * 1.0, 50, 100))
            score_gct = float(np.clip(100.0 - (gct_val - 220.0) * 0.5, 50, 100))
            score_str = float(np.clip(step_val * 0.95, 50, 100))
            score_vr = float(np.clip(100.0 - (vr_val - 6.0) * 7.5, 50, 100))
            score_ef = float(np.clip(ef_val * 95.0, 50, 100))
            
            # 個人最佳基準 (PB 台北馬: 183.1spm, 237ms, 103cm, 7.8%, EF 1.01)
            score_cad_pb = 93.1
            score_gct_pb = 91.5
            score_str_pb = 97.9
            score_vr_pb = 86.5
            score_ef_pb = 96.0
            
            hover_curr = [
                f"步頻: {cad_val:.1f} spm (得分: {score_cad:.1f})",
                f"觸地: {gct_val:.0f} ms (得分: {score_gct:.1f})",
                f"步幅: {step_val:.1f} cm (得分: {score_str:.1f})",
                f"垂直比: {vr_val:.1f}% (得分: {score_vr:.1f})",
                f"能效比: {ef_val:.2f} (得分: {score_ef:.1f})"
            ]
            hover_curr.append(hover_curr[0])
            
            hover_pb = [
                "基準步頻: 183.1 spm (得分: 93.1)",
                "基準觸地: 237 ms (得分: 91.5)",
                "基準步幅: 103.0 cm (得分: 97.9)",
                "基準垂直比: 7.8% (得分: 86.5)",
                "基準能效比: 1.01 (得分: 96.0)"
            ]
            hover_pb.append(hover_pb[0])
            
            fig_r = go.Figure()
            # 基準線 (PB 最佳戰力邊界)
            fig_r.add_trace(go.Scatterpolar(
                r=[score_cad_pb, score_gct_pb, score_str_pb, score_vr_pb, score_ef_pb, score_cad_pb],
                theta=radar_categories + [radar_categories[0]],
                fill='toself',
                name="🔘 個人最佳基準 (PB 台北馬)",
                line=dict(color='rgba(148, 163, 184, 0.6)', width=1.5, dash='dash'),
                fillcolor='rgba(148, 163, 184, 0.08)',
                text=hover_pb,
                hovertemplate="🔘 %{text}<extra></extra>"
            ))
            # 當前活動實跑
            disp_name = curr_name[:14] if curr_name else "當前活動實跑"
            fig_r.add_trace(go.Scatterpolar(
                r=[score_cad, score_gct, score_str, score_vr, score_ef, score_cad],
                theta=radar_categories + [radar_categories[0]],
                fill='toself',
                name=f"🔵 {disp_name}",
                line=dict(color='#38bdf8', width=2.5),
                fillcolor='rgba(56, 189, 248, 0.25)',
                text=hover_curr,
                hovertemplate="🔵 %{text}<extra></extra>"
            ))
            fig_r.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[55, 102], showticklabels=False)
                ),
                template="plotly_dark",
                height=360,
                margin=dict(l=30, r=30, t=30, b=30),
                legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1)
            )
            st.plotly_chart(fig_r, use_container_width=True)

        with col_radar_right:
            st.markdown("#### 🩺 雙教練臨床會診：成因解剖與科學定論")
            
            cur_lthr_val = st.session_state.get('active_lthr', 181)
            cur_z2_min_val = st.session_state.get('active_z2_min', 144)
            cur_z2_max_val = st.session_state.get('active_z2_max', 159)
            
            if avg_hr and avg_hr > cur_lthr_val:
                hr_diag = f"平均心率 <code>{avg_hr:.0f} bpm</code> 已衝破乳酸閾值 (LTHR {cur_lthr_val})，屬於高強度競賽級負荷，乳酸耐受引擎高度活化！"
            elif avg_hr and cur_z2_min_val <= avg_hr <= cur_z2_max_val:
                hr_diag = f"平均心率 <code>{avg_hr:.0f} bpm</code> 完美錨定在神聖 Zone 2 ({cur_z2_min_val}–{cur_z2_max_val} bpm)，粒線體增生與脂肪氧化能效達到最佳狀態！"
            elif avg_hr:
                hr_diag = f"平均心率 <code>{avg_hr:.0f} bpm</code> 落於節奏巡航區間，有效強化馬拉松配速 (MP) 下的心血管耐久性。"
            else:
                hr_diag = "未偵測到連續心率數據，無法進行生化代謝深度判讀。"

            ef_diag = f"跑姿心血管能效 EF 達到 <code>{ef_val:.2f}</code> (每心跳推進 {ef_val:.2f}m)，高溫與長距離下維持心肺做功穩定度。"
            
            # 步態力學診斷
            gct_str_diag = f"觸地時間 <code>{gct_val:.0f} ms</code>"
            if gct_val <= 240:
                gct_diag = f"{gct_str_diag} 展現出頂級菁英跑者的下肢彈性剛性，地面反作用力垂直能量回收率極高！"
            else:
                gct_diag = f"{gct_str_diag} 稍有制動，建議加強腳踝提腿速度，減少支撐時間。"
                
            stride_gap = max(0.0, 103.0 - step_val)
            if stride_gap > 3.0:
                stride_diag = f"平均步幅 <code>{step_val:.1f} cm</code> (相距台北馬 103cm 基準尚少 {stride_gap:.1f} cm)；步頻穩於 <code>{cad_val:.1f} spm</code>，速度瓶頸在於推蹬推進力，建議持續加強短坡推蹬！"
            else:
                stride_diag = f"平均步幅 <code>{step_val:.1f} cm</code> 與步頻 <code>{cad_val:.1f} spm</code> 搭配高度協調，成功找回向後推蹬的位移滑行感！"

            rec_hours = int(min(48, max(12, tot_km * 1.5 + (4 if (avg_hr and avg_hr > 175) else 0))))

            st.markdown(f"""
            <div style="background: rgba(30, 58, 138, 0.25); border-left: 4px solid #3b82f6; padding: 14px; border-radius: 8px; margin-bottom: 12px;">
                <div style="font-weight: 700; color: #60a5fa; font-size: 1rem; margin-bottom: 6px;">
                    🧬 路格教練 (Coach Luger) 生化生理與心血管審查
                </div>
                <ul style="margin: 0; padding-left: 18px; color: #e2e8f0; font-size: 0.88rem; line-height: 1.55;">
                    <li><strong>心肺做功定論：</strong> {hr_diag}</li>
                    <li><strong>能量轉化能效：</strong> {ef_diag}</li>
                </ul>
            </div>

            <div style="background: rgba(6, 78, 59, 0.25); border-left: 4px solid #10b981; padding: 14px; border-radius: 8px;">
                <div style="font-weight: 700; color: #34d399; font-size: 1rem; margin-bottom: 6px;">
                    🏃‍♀️ 佩絲教練 (Coach Pace) 步態力學與身心恢復診斷
                </div>
                <ul style="margin: 0; padding-left: 18px; color: #e2e8f0; font-size: 0.88rem; line-height: 1.55;">
                    <li><strong>下肢彈性剛性：</strong> {gct_diag}</li>
                    <li><strong>推蹬步幅診斷：</strong> {stride_diag}</li>
                    <li><strong>修復指引：</strong> 建議安排 <strong>{rec_hours} 小時</strong> 主動修復，重點滾筒放鬆小腿阿基里斯腱與臀大肌。</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        st.markdown("### 📋 每公里完整感測器數據明細 (Lap by Lap)")
        st.caption("完整記錄每 1 公里的配速、心率分區判定、步頻、步幅、觸地時間、垂直振幅與移動效率。支援即時搜尋與欄位排序。")
        
        act_z2_min = st.session_state.get('active_z2_min', 144)
        act_z2_max = st.session_state.get('active_z2_max', 159)
        act_lthr = st.session_state.get('active_lthr', 181)
        z3_max = int(act_z2_max + (act_lthr - act_z2_max) * 0.6)

        def tag_zone(hr):
            if pd.isna(hr) or hr <= 0: return ""
            if hr < act_z2_min: return "Zone 1 (動態恢復)"
            elif hr <= act_z2_max: return "Zone 2 (神聖有氧)"
            elif hr <= z3_max: return "Zone 3 (有氧節奏)"
            elif hr <= act_lthr: return "Zone 4 (乳酸閾值)"
            else: return "Zone 5 (無氧極限)"
            
        display_df = df.copy()
        if 'heart_rate' in display_df.columns:
            display_df['心率分區'] = display_df['heart_rate'].apply(tag_zone)
            
        col_order = [
            'lap', 'dist_km', 'pace_str', 'heart_rate', '心率分區', 
            'cadence', 'step_length', 'gct', 'vertical_osc', 
            'vertical_ratio', 'gct_balance', 'power', 'ascent'
        ]
        col_exist = [c for c in col_order if c in display_df.columns]
        
        rename_map = {
            'lap': '公里數 (Km)',
            'dist_km': '單段距離 (km)',
            'pace_str': '平均配速 (/km)',
            'heart_rate': '平均心率 (bpm)',
            'cadence': '步頻 (SPM)',
            'step_length': '步幅 (cm)',
            'gct': '觸地時間 (ms)',
            'vertical_osc': '垂直振幅 (cm)',
            'vertical_ratio': '移動效率比 (%)',
            'gct_balance': '左腳平衡 (%)',
            'power': '功率 (W)',
            'ascent': '爬升 (m)',
        }
        
        styled_df = display_df[col_exist].rename(columns=rename_map)
        st.dataframe(styled_df, use_container_width=True, height=520)
        
        # 匯出 CSV 按鈕
        csv_data = styled_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="💾 下載每公里數據 CSV",
            data=csv_data,
            file_name=f"{st.session_state.get('pending_file_name', 'run_data')}_splits.csv",
            mime="text/csv"
        )
    else:
        st.info("👋 尚未載入活動數據。請從左側側邊欄選取 **「Garmin 雲端跑步活動」** 或 **「🏆 歷年大賽實績庫」**。")


# ==========================================
# TAB 4: 雙教練配速模擬與賽事沙盤推演 (旗艦全能版)
# ==========================================
with tab_sim:
    st.markdown("### 🎛️ 雙教練配速模擬與賽事沙盤推演 (旗艦全能版)")
    st.caption("支援在畫面上切換「間歇跑」、「節奏跑」、「LSD」與「大賽推演」，整合天氣補償、4大科學配速策略與防水配速手環下載！")
    
    html_card_path = "templates/coach_dashboard_interactive.html"
    if not os.path.exists(html_card_path):
        for p in [
            "assets/coach_dashboard_interactive.html",
            ".agents/skills/running-coach-duo/templates/coach_dashboard_interactive.html",
            "C:/Users/Edward/.gemini/antigravity/brain/0af66755-b010-43fb-835b-4354be4d4588/coach_dashboard_interactive.html"
        ]:
            if os.path.exists(p):
                html_card_path = p
                break
        
    if os.path.exists(html_card_path):
        with open(html_card_path, "r", encoding="utf-8") as hf:
            html_code = hf.read()
            
        # 動態連動當前生理基線至課表模擬器與大賽沙盤推演
        act_max = st.session_state.get('active_max_hr', 197)
        act_rest = st.session_state.get('active_rest_hr', 57)
        act_lthr = st.session_state.get('active_lthr', 181)
        act_z2_min = st.session_state.get('active_z2_min', 144)
        act_z2_max = st.session_state.get('active_z2_max', 159)
        act_mode = st.session_state.get('active_base_mode', 'Garmin')

        import re
        u_prof = st.session_state.get("user_profile", {})
        u_p_name = u_prof.get("name", user_name)
        u_f_min = u_prof.get("pb_full_min", 271.0)
        u_h_min = u_prof.get("pb_half_min", 112.55)
        u_f_lbl = u_prof.get("pb_full_label", "全馬 4:31:00")
        u_h_lbl = u_prof.get("pb_half_label", "半馬 1:52:33")

        # 1. 替換 JS 中的 BASELINE 常數 (注入動態 runnerName)
        dyn_baseline_js = f"""const BASELINE = {{
      runnerName: "{u_p_name}",
      maxHR: {act_max},
      restHR: {act_rest},
      lthr: {act_lthr},
      z2_min: {act_z2_min},
      z2_max: {act_z2_max},
      vdot_base: 35.0,
      marathon_time_min: {u_f_min},
      half_marathon_time_min: {u_h_min}
    }};"""
        html_code = re.sub(r"const BASELINE = \{[\s\S]*?\};", dyn_baseline_js, html_code, count=1)

        # 2. 替換副標題說明文字與跑者名稱
        mode_label = "Garmin 手錶動態" if "Garmin" in act_mode else "個人自訂"
        sub_str = f"跑者：{u_p_name} | Max HR {act_max} | Rest HR {act_rest} | LTHR {act_lthr} | Zone 2: {act_z2_min}-{act_z2_max} bpm ({mode_label})"
        html_code = re.sub(r"<p[^>]*>跑者：[\s\S]*?bpm[^<]*</p>", f"<p class='text-xs text-slate-300 mt-0.5'>{sub_str}</p>", html_code)
        html_code = html_code.replace("全馬 4:31:00 (2024台北馬) / 半馬 1:52:33", f"{u_f_lbl} / {u_h_lbl}")

        # 3. 替換手環 Canvas 上的 LTHR 防線標註
        html_code = html_code.replace("LTHR 193 bpm 防線", f"LTHR {act_lthr} bpm 防線")
        html_code = html_code.replace("193 bpm LTHR", f"{act_lthr} bpm LTHR")

        components.html(html_code, height=830, scrolling=False)
    else:
        st.warning("⚠️ 尚未找到微調模擬器 HTML 模板文件。")

# ==========================================
# TAB 5: 雙場對決比較 (Head-to-Head)
# ==========================================
with tab_compare:
    render_compare_tab()
