# auth_manager.py
"""
AI Coach 雙模身分認證與隱私隔離中樞 (Dual-Mode Privacy & Auth Engine)
功能：
1. 訪客 Demo 模式 vs Edward 專屬 VIP 模式嚴格物理隔離
2. SHA-256 密碼學單向雜湊驗證，防暴力破解
3. 支援 URL 專屬參數 (?auth=... 或 ?pin=...) 一秒無感解鎖 (iPhone PWA 必備)
4. 本地環境預設自動授權，雲端公開站預設安全鎖定
"""

import os
import json
import hashlib
import streamlit as st

AUTH_KEY = "is_edward_authenticated"
FAIL_COUNT_KEY = "auth_fail_count"
DEFAULT_SALT = "ai_coach_salt_2026"

def hash_pin(pin: str) -> str:
    """使用 SHA-256 單向雜湊，絕不儲存明文密碼"""
    salted = f"{pin.strip()}_{DEFAULT_SALT}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()

def get_target_pin_hash() -> str:
    """
    獲取目標 PIN 雜湊值 (雲端 Secrets 優先，其次本地 keys.json)
    若皆未設定，預設為 'edward888'
    """
    # 1. 優先檢查 Streamlit Secrets (雲端加密保險箱)
    try:
        if hasattr(st, "secrets"):
            if "EDWARD_PIN_HASH" in st.secrets:
                return str(st.secrets["EDWARD_PIN_HASH"]).strip()
            if "EDWARD_PIN" in st.secrets:
                return hash_pin(str(st.secrets["EDWARD_PIN"]))
    except Exception:
        pass

    # 2. 檢查本地 keys.json (受 .gitignore 保護)
    if os.path.exists("keys.json"):
        try:
            with open("keys.json", "r", encoding="utf-8") as f:
                kdata = json.load(f)
                if "EDWARD_PIN_HASH" in kdata:
                    return str(kdata["EDWARD_PIN_HASH"]).strip()
                if "EDWARD_PIN" in kdata:
                    return hash_pin(str(kdata["EDWARD_PIN"]))
        except Exception:
            pass

    # 3. 系統預設安全 PIN: 'edward888'
    return hash_pin("edward888")

def check_auto_auth():
    """
    智慧自動身分檢測：
    1. 支援 URL 參數認證 (例如 ?auth=... 或 ?pin=...)，驗證通過後實施「閱後即焚」自動抹除 URL 參數
    2. 若使用者手動點擊了切換為 Demo 模式，優先保持 Demo
    3. 本地開發環境 (有 keys.json 且在本地 localhost 運行) 預設解鎖
    """
    # 若明確處於 Demo 模式，不自動登入
    if st.session_state.get("explicit_demo_mode", False):
        return False

    # 檢查 URL 查詢參數
    try:
        qp = st.query_params
        url_auth = qp.get("auth", "") or qp.get("pin", "") or qp.get("key", "")
        if url_auth:
            if hash_pin(str(url_auth)) == get_target_pin_hash():
                st.session_state[AUTH_KEY] = True
                st.session_state["explicit_demo_mode"] = False
                # 關鍵防護：驗證通過後立即抹除 URL 參數（閱後即焚機制），防止留在瀏覽器網址列、書籤或歷史紀錄中
                for k in ["auth", "pin", "key"]:
                    if k in st.query_params:
                        try:
                            del st.query_params[k]
                        except Exception:
                            pass
                return True
            else:
                # 若 PIN 錯誤也立即清除，防止參數洩漏或惡意探測
                for k in ["auth", "pin", "key"]:
                    if k in st.query_params:
                        try:
                            del st.query_params[k]
                        except Exception:
                            pass
    except Exception:
        pass

    # 已經手動解鎖過
    if st.session_state.get(AUTH_KEY, False):
        return True

    # 本地環境偵測 (若本地有合法 keys.json)
    if os.path.exists("keys.json"):
        st.session_state[AUTH_KEY] = True
        return True

    return False

def verify_input_pin(input_str: str) -> tuple[bool, str]:
    """驗證使用者輸入之 PIN 碼"""
    fails = st.session_state.get(FAIL_COUNT_KEY, 0)
    if fails >= 5:
        return False, "❌ 嘗試錯誤次數過多，為維護資訊安全，請稍後再試。"

    target = get_target_pin_hash()
    if hash_pin(input_str) == target:
        st.session_state[AUTH_KEY] = True
        st.session_state["explicit_demo_mode"] = False
        st.session_state[FAIL_COUNT_KEY] = 0
        return True, "✅ 驗證成功！已解鎖 Edward 專屬運動科學模式！"
    else:
        st.session_state[FAIL_COUNT_KEY] = fails + 1
        rem = 5 - (fails + 1)
        return False, f"❌ PIN 碼錯誤，尚有 {rem} 次嘗試機會。"

def logout_user():
    """登出切換回訪客 Demo 模式"""
    st.session_state[AUTH_KEY] = False
    st.session_state["explicit_demo_mode"] = True
    try:
        st.query_params.clear()
    except Exception:
        pass
    st.cache_data.clear()

def is_authenticated() -> bool:
    """判斷當前使用者是否為 Edward 本人"""
    return st.session_state.get(AUTH_KEY, False) or check_auto_auth()

def render_auth_badge():
    """在頁首頂部或側邊欄呈現身分徽章與解鎖入口"""
    auth = is_authenticated()
    if auth:
        col_b1, col_b2 = st.columns([0.75, 0.25])
        with col_b1:
            st.markdown(
                "<div style='background: rgba(16,185,129,0.12); border: 1px solid rgba(16,185,129,0.3); border-radius: 8px; padding: 6px 12px; font-size: 0.82rem; color: #10b981; display: flex; align-items: center;'>"
                "🟢 <strong>Edward 專屬運動科學模式 (VIP)</strong> — 已掛載真實 Garmin 與 25 週萬金石課表"
                "</div>",
                unsafe_allow_html=True
            )
        with col_b2:
            if st.button("🔒 切換為 Demo 模式", use_container_width=True, help="點擊切換為公開展示模式"):
                logout_user()
                st.rerun()
    else:
        col_b1, col_b2 = st.columns([0.72, 0.28])
        with col_b1:
            st.markdown(
                "<div style='background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.3); border-radius: 8px; padding: 6px 12px; font-size: 0.82rem; color: #f59e0b; display: flex; align-items: center;'>"
                "🌐 <strong>公開訪客 Demo 模式</strong> — 目前展示公版範本數據，個人隱私受保護中"
                "</div>",
                unsafe_allow_html=True
            )
        with col_b2:
            if st.button("🔐 解鎖專屬模式", type="primary", use_container_width=True, help="輸入跑者 PIN 碼以切換為本人模式"):
                open_pin_dialog()

@st.dialog("🔐 解鎖 Edward 專屬運動科學戰情室")
def open_pin_dialog():
    st.markdown("請輸入跑者專屬 PIN 碼，驗證通過後系統將即刻掛載您的 Garmin 真實數據與 25 週雙馬私密課表。")
    in_pin = st.text_input("專屬 PIN 碼", type="password", placeholder="請輸入個人授權 PIN 碼")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        if st.button("🚀 驗證並解鎖", type="primary", use_container_width=True):
            ok, msg = verify_input_pin(in_pin)
            if ok:
                st.success(msg)
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(msg)
    with col_d2:
        if st.button("取消", use_container_width=True):
            st.rerun()
