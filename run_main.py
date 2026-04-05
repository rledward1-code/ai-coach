import streamlit.web.cli as stcli
import sys
import os

def resolve_path(path):
    if getattr(sys, 'frozen', False):
        # 執行檔模式下的路徑
        application_path = sys._MEIPASS
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(application_path, path)

if __name__ == "__main__":
    # 將命令列參數替換成 streamlit 啟動指令
    sys.argv = [
        "streamlit",
        "run",
        resolve_path("app.py"),
        "--global.developmentMode=false",
    ]
    sys.exit(stcli.main())
