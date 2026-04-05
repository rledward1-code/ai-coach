# garmin_local.py
"""
兩種本機自動取得最新 .fit 的方式：
1. USB 掃描：掃描所有磁碟代號，找 \GARMIN\Activity\
2. Watch folder：使用者指定的本地資料夾（如 Garmin Express 同步目標）
"""
import os
import shutil
import string
from pathlib import Path

GARMIN_ACTIVITY_SUBPATH = os.path.join("GARMIN", "Activity")
TEMP_FIT_PATH = "temp.fit"


def _latest_fit_in_dir(directory: str) -> str | None:
    """回傳資料夾內最新的 .fit 檔完整路徑，若無則 None"""
    try:
        fits = [
            os.path.join(directory, f)
            for f in os.listdir(directory)
            if f.lower().endswith(".fit")
        ]
        if not fits:
            return None
        return max(fits, key=os.path.getmtime)
    except PermissionError:
        return None
    except Exception:
        return None


def scan_garmin_usb() -> tuple[str | None, str]:
    """
    掃描 A~Z 所有磁碟代號，找第一個包含 GARMIN\\Activity 的磁碟。
    回傳 (最新.fit路徑 | None, 狀態訊息)
    """
    found_drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        activity_dir = os.path.join(drive, GARMIN_ACTIVITY_SUBPATH)
        if os.path.isdir(activity_dir):
            found_drives.append((letter, activity_dir))

    if not found_drives:
        return None, "未偵測到 Garmin 裝置（找不到任何磁碟的 \\GARMIN\\Activity\\）"

    # 若找到多個（罕見），取最近修改的那個磁碟
    best_fit = None
    best_mtime = 0
    best_drive_letter = ""
    for letter, activity_dir in found_drives:
        fit = _latest_fit_in_dir(activity_dir)
        if fit:
            mt = os.path.getmtime(fit)
            if mt > best_mtime:
                best_mtime = mt
                best_fit = fit
                best_drive_letter = letter

    if not best_fit:
        drive_list = ", ".join(f"{l}:" for l, _ in found_drives)
        return None, f"找到 Garmin 磁碟 ({drive_list}) 但 Activity 資料夾內沒有 .fit 檔"

    return best_fit, f"Garmin 手錶 ({best_drive_letter}:) ✅ 找到最新活動"


def scan_watch_folder(folder_path: str) -> tuple[str | None, str]:
    """
    在指定的 watch folder 中找最新 .fit。
    回傳 (最新.fit路徑 | None, 狀態訊息)
    """
    if not folder_path or not folder_path.strip():
        return None, "Watch folder 路徑未設定"

    folder_path = folder_path.strip()
    if not os.path.isdir(folder_path):
        return None, f"資料夾不存在：{folder_path}"

    fit = _latest_fit_in_dir(folder_path)
    if not fit:
        return None, f"資料夾內找不到 .fit 檔：{folder_path}"

    return fit, f"Watch folder ✅ 找到最新活動"


def get_latest_fit(watch_folder: str = "") -> tuple[str | None, str]:
    """
    主入口：優先掃 USB → fallback watch folder。
    成功時把檔案複製到 temp.fit（避免跨磁碟鎖定），回傳 (temp.fit路徑, 訊息)
    """
    # 1. 嘗試 USB
    fit_path, msg = scan_garmin_usb()

    # 2. fallback watch folder
    if fit_path is None and watch_folder:
        fit_path, msg = scan_watch_folder(watch_folder)

    if fit_path is None:
        return None, msg

    # 複製到工作目錄，避免跨磁碟 / 裝置鎖定問題
    try:
        shutil.copy2(fit_path, TEMP_FIT_PATH)
        filename = os.path.basename(fit_path)
        return TEMP_FIT_PATH, f"{msg}\n📄 {filename}"
    except Exception as e:
        return None, f"複製 .fit 檔失敗：{e}"
