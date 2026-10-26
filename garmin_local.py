# garmin_local.py
"""
極速本機掃描最新 .fit 檔案模組：
1. USB 可移除磁碟極速掃描 (使用 Windows 底層 API 過濾網路磁碟，避免卡頓)
2. Garmin Express 本機同步緩存目錄掃描
3. Watch folder：指定的本機資料夾 (如 Downloads)
"""
import os
import shutil
import string
import ctypes
from pathlib import Path

GARMIN_ACTIVITY_SUBPATH = os.path.join("GARMIN", "Activity")
TEMP_FIT_PATH = "temp.fit"

def _latest_fit_in_dir(directory: str) -> str | None:
    """回傳資料夾內最新的 .fit 檔完整路徑，若無則 None"""
    try:
        if not os.path.isdir(directory):
            return None
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
    極速掃描實體 USB 可移除磁區與 Garmin Express 本機目錄。
    徹底解決因檢查網路磁碟代號 (如 I:, K: 等) 導致的卡死與等待問題。
    """
    DRIVE_REMOVABLE = 2
    found_dirs = []

    # 1. 0.001 秒快速過濾實體 USB 隨身碟模式掛載
    try:
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i, letter in enumerate(string.ascii_uppercase):
            if bitmask & (1 << i):
                root = f"{letter}:\\"
                dtype = ctypes.windll.kernel32.GetDriveTypeW(root)
                # 嚴格僅檢查可移除裝置 (隨身碟模式)，直接跳過網路磁區與主硬碟
                if dtype == DRIVE_REMOVABLE:
                    act_dir = os.path.join(root, GARMIN_ACTIVITY_SUBPATH)
                    if os.path.isdir(act_dir):
                        found_dirs.append((f"Garmin 手錶 ({letter}:)", act_dir))
    except Exception:
        pass

    # 2. 自動掃描 Garmin Express 本機同歩活動緩存
    garmin_core_dirs = [
        "C:\\ProgramData\\Garmin\\CoreService\\Devices",
        os.path.expandvars("%APPDATA%\\Garmin\\Devices")
    ]
    for g_base in garmin_core_dirs:
        if os.path.isdir(g_base):
            try:
                for dev in os.listdir(g_base):
                    dev_p = os.path.join(g_base, dev)
                    # 搜尋常見的快取目錄
                    for cand_sub in ["Sync", "Activities", "Activity"]:
                        sub_p = os.path.join(dev_p, cand_sub)
                        if os.path.isdir(sub_p):
                            found_dirs.append((f"Garmin Express 快取 ({dev})", sub_p))
                            # 亦搜尋子目錄
                            try:
                                for s in os.listdir(sub_p):
                                    sp = os.path.join(sub_p, s)
                                    if os.path.isdir(sp):
                                        found_dirs.append((f"Garmin Express ({dev}/{s})", sp))
                            except Exception:
                                pass
            except Exception:
                pass

    if not found_dirs:
        return None, "未偵測到隨身碟模式的 Garmin 手錶。\n提示：若使用充電線插入，請確認該線材具備資料傳輸功能，且手錶螢幕若跳出提示請點選「進入大容量儲存/連線」；亦可開啟桌面上的 Garmin Express 進行同步。"

    # 尋找最新修改的 .fit 檔案
    best_fit = None
    best_mtime = 0
    best_source_name = ""
    for src_name, act_dir in found_dirs:
        fit = _latest_fit_in_dir(act_dir)
        if fit:
            try:
                mt = os.path.getmtime(fit)
                if mt > best_mtime:
                    best_mtime = mt
                    best_fit = fit
                    best_source_name = src_name
            except Exception:
                pass

    if not best_fit:
        return None, "已檢測到 Garmin 裝置路徑，但目前沒有找到跑步活動 .fit 檔。"

    return best_fit, f"{best_source_name} ✅ 找到最新活動"

def scan_watch_folder(folder_path: str) -> tuple[str | None, str]:
    """在使用者指定的本地資料夾 (如 Downloads) 中尋找最新 .fit"""
    if not folder_path or not folder_path.strip():
        return None, "Watch folder 路徑未設定"

    folder_path = folder_path.strip()
    if not os.path.isdir(folder_path):
        return None, f"資料夾不存在：{folder_path}"

    fit = _latest_fit_in_dir(folder_path)
    if not fit:
        return None, f"資料夾內找不到 .fit 檔：{folder_path}"

    return fit, f"本地資料夾 ✅ 找到最新活動"

def get_latest_fit(watch_folder: str = "") -> tuple[str | None, str]:
    """主入口：極速檢查 USB / Express 緩存 → fallback 本地目錄"""
    fit_path, msg = scan_garmin_usb()

    if fit_path is None and watch_folder:
        f_path, f_msg = scan_watch_folder(watch_folder)
        if f_path:
            fit_path, msg = f_path, f_msg

    if fit_path is None:
        return None, msg

    try:
        shutil.copy2(fit_path, TEMP_FIT_PATH)
        filename = os.path.basename(fit_path)
        return TEMP_FIT_PATH, f"{msg}\n📄 {filename}"
    except Exception as e:
        return None, f"複製 .fit 檔失敗：{e}"
