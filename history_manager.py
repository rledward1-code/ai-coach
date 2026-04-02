# history_manager.py
import json
import os
from datetime import datetime

HISTORY_FILE = "coach_history.json"
CHAT_LOG_FILE = "chat_log.json"
GLOBAL_HISTORY_FILE = "global_history_summary.txt"
USER_PROFILE_FILE = "user_profile.json"
MAX_CHAT_MESSAGES = 100  # 設定保留最近 100 則訊息 (約 30-50 輪對話)

def save_run_to_history(summary_text, tags=None, rpe=None, feeling=None, plan=None):
    """將單次訓練摘要存入歷史，最多保留最近 20 筆"""
    history = load_history()
    
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary_text,
        "tags": tags or [],
        "rpe": rpe,
        "feeling": feeling,
        "plan": plan
    }
    
    # 避免重複存入同一筆 (簡單比對摘要內容)
    if history and history[-1]["summary"] == summary_text:
        return
        
    history.append(entry)
    
    # 只保留最近 20 筆，避免 Prompt 爆炸
    if len(history) > 20:
        history = history[-20:]
        
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

def load_history():
    """讀取歷史紀錄"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_global_history(summary_text):
    """保存長期總表摘要"""
    with open(GLOBAL_HISTORY_FILE, "w", encoding="utf-8") as f:
        f.write(summary_text)

def load_global_history():
    """讀取長期總表摘要"""
    if os.path.exists(GLOBAL_HISTORY_FILE):
        try:
            with open(GLOBAL_HISTORY_FILE, "r", encoding="utf-8") as f:
                return f.read()
        except:
            return ""
    return ""

def get_history_snapshot():
    """將歷史紀錄概覽換為可供 AI 快速閱讀的簡單摘要 (最近 5 筆)"""
    history = load_history()
    global_stat = load_global_history()
    
    lines = []
    if global_stat:
        lines.append("【跑者長期訓練總表 - 概覽】")
        lines.append(global_stat)
        lines.append("-" * 20)

    if not history:
        lines.append("目前尚無單次訓練歷史紀錄。")
    else:
        lines.append("以下是跑者最近幾次的單次訓練表現：")
        for h in history[-5:]:
            first_lines = [line for line in h["summary"].split("\n")][:5]
            tag_str = f" [{', '.join(h.get('tags', []))}]" if h.get('tags') else ""
            rpe = h.get('rpe', 'N/A')
            plan = h.get('plan', '尚未備註')
            lines.append(f"🕒 {h['timestamp']}: {' | '.join(first_lines)}{tag_str} (RPE: {rpe}, 備註: {plan})")
        
    return "\n".join(lines)

def save_chat_log(messages):
    """將對話紀錄儲存為 JSON"""
    trimmed_messages = messages[-MAX_CHAT_MESSAGES:]
    with open(CHAT_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed_messages, f, ensure_ascii=False, indent=4)

def load_chat_log():
    """讀取對話歷史"""
    if os.path.exists(CHAT_LOG_FILE):
        try:
            with open(CHAT_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_user_profile(profile_data):
    """儲存個人檔案到 JSON"""
    with open(USER_PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile_data, f, ensure_ascii=False, indent=2)

def load_user_profile():
    """載入個人檔案"""
    if os.path.exists(USER_PROFILE_FILE):
        try:
            with open(USER_PROFILE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {
        "name": "Edward",
        "age": 56,
        "gender": "男",
        "max_hr": 210,
        "rest_hr": 56,
        "threshold_hr": 193
    }
