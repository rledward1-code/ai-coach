# history_manager.py
import json
import os
from datetime import datetime

HISTORY_FILE = "coach_history.json"
CHAT_LOG_FILE = "chat_log.json"
MAX_CHAT_MESSAGES = 100  # 設定保留最近 100 則訊息 (約 30-50 輪對話)

def save_run_to_history(summary_text, tags=None, rpe=None, feeling=None, plan=None):
    """將每次解析完的跑步摘要存入歷史紀錄，最多保留最近 20 筆"""
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

def get_history_snapshot():
    """將歷史紀錄轉換為教練可閱讀的簡短文字摘要 (前 5 筆)"""
    history = load_history()
    if not history:
        return "尚無過去跑步紀錄。"
    
    lines = ["以下是跑者過去幾次的訓練摘要："]
    # 取最近 5 筆給 AI 參考，避免過多資訊干擾
    for h in history[-5:]:
        # 擷取摘要中的關鍵行 (例如 總距離, 總時間)
        first_lines = [line for line in h["summary"].split("\n")][:5]
        tag_str = f" [{', '.join(h.get('tags', []))}]" if h.get('tags') else ""
        
        # 加入體感與計畫描述
        rpe = h.get('rpe', 'N/A')
        plan = h.get('plan', '未記錄')
        lines.append(f"📅 {h['timestamp']}: {' | '.join(first_lines)}{tag_str} (RPE: {rpe}, 計畫: {plan})")
        
    return "\n".join(lines)

# --- 聊天日誌持久化功能 ---
def save_chat_log(messages):
    """將對話訊息儲存為 JSON，並限制長度防止膨脹"""
    # 僅儲存最近 N 則
    trimmed_messages = messages[-MAX_CHAT_MESSAGES:]
    with open(CHAT_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed_messages, f, ensure_ascii=False, indent=4)

def load_chat_log():
    """啟動時載入上次的對話歷史"""
    if os.path.exists(CHAT_LOG_FILE):
        try:
            with open(CHAT_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []
