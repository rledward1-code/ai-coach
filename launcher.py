# launcher.py
"""
AI Coach 戰情儀表板 - 靜默啟動與瀏覽器自啟腳本
功能：
1. 檢測 Streamlit 服務是否已經在 http://localhost:8501 運行。
2. 若未運行，以無黑視窗背景模式 (CREATE_NO_WINDOW) 啟動 Streamlit。
3. 服務就緒後，自動喚起預設瀏覽器打開戰情看板。
4. 若已在運行，直接打開瀏覽器，不重複佔用資源。
"""

import os
import sys
import time
import urllib.request
import webbrowser
import subprocess

URL = "http://localhost:8501"
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXE = sys.executable
for _cand in [
    os.path.join(WORKSPACE_DIR, ".venv", "Scripts", "python.exe"),
    os.path.join(WORKSPACE_DIR, "venv", "Scripts", "python.exe"),
]:
    if os.path.exists(_cand):
        PYTHON_EXE = _cand
        break
else:
    for _e in os.listdir(WORKSPACE_DIR):
        if _e.startswith("venv") and os.path.isdir(os.path.join(WORKSPACE_DIR, _e)):
            _cand = os.path.join(WORKSPACE_DIR, _e, "Scripts", "python.exe")
            if os.path.exists(_cand):
                PYTHON_EXE = _cand
                break

def is_running():
    try:
        req = urllib.request.Request(URL)
        with urllib.request.urlopen(req, timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False

def main():
    if not is_running():
        # Windows CREATE_NO_WINDOW = 0x08000000 確保零黑視窗跳出
        creation_flags = 0x08000000 if sys.platform == "win32" else 0
        cmd = [
            PYTHON_EXE,
            "-m", "streamlit", "run", "app.py",
            "--server.port", "8501",
            "--server.headless", "true"
        ]
        try:
            subprocess.Popen(
                cmd,
                cwd=WORKSPACE_DIR,
                creationflags=creation_flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            # Fallback
            subprocess.Popen(cmd, cwd=WORKSPACE_DIR)

        # 最多等待 20 秒直到服務啟動
        for _ in range(40):
            time.sleep(0.5)
            if is_running():
                break

    # 喚起預設瀏覽器打開戰情看板
    try:
        webbrowser.open(URL)
    except Exception:
        pass

if __name__ == "__main__":
    main()
