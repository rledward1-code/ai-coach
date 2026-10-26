# setup_autostart.py
"""
一鍵設定開機自動啟動 AI Coach 服務並打開網頁
"""

import os
import sys
import subprocess

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def setup():
    startup_dir = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
    desktop_dir = os.path.expandvars(r"%USERPROFILE%\OneDrive\Desktop")
    if not os.path.exists(desktop_dir):
        desktop_dir = os.path.expandvars(r"%USERPROFILE%\Desktop")

    workspace = r"d:\ai-coach"
    pythonw = os.path.join(workspace, "venv_EDWARD-ALIENWAR", "Scripts", "pythonw.exe")
    launcher = os.path.join(workspace, "launcher.py")

    targets = [
        ("開機自啟 (Startup)", os.path.join(startup_dir, "AI Coach Dashboard.lnk")),
        ("桌面捷徑 (Desktop)", os.path.join(desktop_dir, "AI Coach 戰情儀表板.lnk"))
    ]

    for label, lnk_path in targets:
        ps_cmd = f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut("{lnk_path}")
$s.TargetPath = "{pythonw}"
$s.Arguments = '"{launcher}"'
$s.WorkingDirectory = "{workspace}"
$s.Description = "AI Coach Dashboard"
$s.Save()
"""
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
        if proc.returncode == 0 and os.path.exists(lnk_path):
            print(f"[SUCCESS] {label} -> {lnk_path}")
        else:
            print(f"[FAILED] {label}")
            if proc.stderr:
                print("   Error:", proc.stderr.strip())

def remove():
    startup_dir = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
    desktop_dir = os.path.expandvars(r"%USERPROFILE%\OneDrive\Desktop")
    if not os.path.exists(desktop_dir):
        desktop_dir = os.path.expandvars(r"%USERPROFILE%\Desktop")

    targets = [
        os.path.join(startup_dir, "AI Coach Dashboard.lnk"),
        os.path.join(desktop_dir, "AI Coach 戰情儀表板.lnk")
    ]
    for p in targets:
        if os.path.exists(p):
            os.remove(p)
            print(f"[REMOVED] {p}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "remove":
        remove()
    else:
        setup()
