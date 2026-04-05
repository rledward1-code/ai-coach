import requests
import json
import os
import time

KEYS_FILE = "keys.json"

def load_keys():
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_keys(keys_data):
    with open(KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(keys_data, f, indent=4)

def check_strava_ready():
    keys = load_keys()
    client_id = keys.get("STRAVA_CLIENT_ID")
    client_secret = keys.get("STRAVA_CLIENT_SECRET")
    return bool(client_id and client_secret)

def is_strava_authorized():
    keys = load_keys()
    return bool(keys.get("STRAVA_REFRESH_TOKEN"))

def get_strava_auth_url():
    keys = load_keys()
    client_id = keys.get("STRAVA_CLIENT_ID", "")
    return f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri=http://localhost:8501&approval_prompt=force&scope=read,activity:read_all"

def exchange_code_for_token(code):
    keys = load_keys()
    url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": keys.get("STRAVA_CLIENT_ID"),
        "client_secret": keys.get("STRAVA_CLIENT_SECRET"),
        "code": code,
        "grant_type": "authorization_code"
    }
    resp = requests.post(url, data=payload)
    if resp.status_code == 200:
        data = resp.json()
        keys["STRAVA_REFRESH_TOKEN"] = data.get("refresh_token")
        keys["STRAVA_ACCESS_TOKEN"] = data.get("access_token")
        keys["STRAVA_EXPIRES_AT"] = data.get("expires_at", 0)
        save_keys(keys)
        return True, "授權成功！"
    return False, f"授權失敗：{resp.text}"

def refresh_token_if_needed():
    keys = load_keys()
    expires_at = keys.get("STRAVA_EXPIRES_AT", 0)
    
    # 提早 300 秒刷新
    if time.time() > expires_at - 300:
        url = "https://www.strava.com/oauth/token"
        payload = {
            "client_id": keys.get("STRAVA_CLIENT_ID"),
            "client_secret": keys.get("STRAVA_CLIENT_SECRET"),
            "refresh_token": keys.get("STRAVA_REFRESH_TOKEN"),
            "grant_type": "refresh_token"
        }
        resp = requests.post(url, data=payload)
        if resp.status_code == 200:
            data = resp.json()
            keys["STRAVA_REFRESH_TOKEN"] = data.get("refresh_token")
            keys["STRAVA_ACCESS_TOKEN"] = data.get("access_token")
            keys["STRAVA_EXPIRES_AT"] = data.get("expires_at", 0)
            save_keys(keys)
            return keys["STRAVA_ACCESS_TOKEN"]
        else:
            return None
    return keys.get("STRAVA_ACCESS_TOKEN")

def fetch_latest_run():
    """透過 API 取得最近一次跑步紀錄並轉為摘要"""
    access_token = refresh_token_if_needed()
    if not access_token:
        return None, "無法獲取有效憑證，請重新授權", []
    
    url = "https://www.strava.com/api/v3/athlete/activities?per_page=5"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(url, headers=headers)
    
    if resp.status_code != 200:
        return None, f"獲取活動失敗: HTTP {resp.status_code}", []
    
    activities = resp.json()
    run_activities = [a for a in activities if a.get("type") == "Run"]
    if not run_activities:
        return None, "找不到近期的跑步紀錄", []
    
    latest_run = run_activities[0]
    
    # 轉換成系統看得懂的統計摘要
    name = latest_run.get("name", "未命名跑步")
    dist_km = latest_run.get("distance", 0) / 1000
    moving_time = latest_run.get("moving_time", 0) # 秒
    
    # 配速計算 (min/km)
    pace_seconds_per_km = moving_time / dist_km if dist_km > 0 else 0
    pace_min = int(pace_seconds_per_km // 60)
    pace_sec = int(pace_seconds_per_km % 60)
    pace_str = f"{pace_min}:{pace_sec:02d}"
    
    avg_hr = latest_run.get("average_heartrate", "無心率")
    max_hr = latest_run.get("max_heartrate", "無心率")
    cadence = latest_run.get("average_cadence", 0)
    if cadence > 0:
        cadence = cadence * 2  # Strava usually returns SPM for one leg
        
    elev_gain = latest_run.get("total_elevation_gain", 0)
    
    lines = [f"🚀 [Strava 雲端同步成功]"]
    lines.append(f"- 活動名稱: {name}")
    lines.append(f"- 訓練總距離: {dist_km:.2f} km")
    lines.append(f"- 總移動時間: {moving_time // 60} 分 {moving_time % 60} 秒")
    lines.append(f"- 平均配速: {pace_str} /km")
    if avg_hr != "無心率":
        lines.append(f"- 平均心率: {avg_hr:.0f} bpm (峰值: {max_hr:.0f})")
    if cadence > 0:
        lines.append(f"- 平均步頻: {cadence:.0f} spm")
    lines.append(f"- 總爬升: {elev_gain:.0f} m")
    
    # 讀取用戶個人心率設定
    user_profile_data = {}
    if os.path.exists("data/user_profile.json"):
        try:
            with open("data/user_profile.json", "r", encoding="utf-8") as fp:
                user_profile_data = json.load(fp)
        except Exception:
            pass

    u_max_hr = user_profile_data.get("max_hr", 190)
    u_rest_hr = user_profile_data.get("rest_hr", 60)
    u_threshold_hr = user_profile_data.get("threshold_hr", 175)
    hrr = u_max_hr - u_rest_hr  # Heart Rate Reserve

    # Karvonen Zone 邊界
    zone2_upper = u_rest_hr + hrr * 0.70  # Zone 2 上限 (約 70% HRR)
    zone4_lower = u_threshold_hr           # Zone 4 以上 = 高強度

    # 動態產生標籤
    tags = []
    if dist_km > 15: tags.append("#長跑")
    elif dist_km > 8: tags.append("#普通跑")
    else: tags.append("#短程")

    if isinstance(avg_hr, (int, float)):
        if avg_hr >= zone4_lower:
            tags.append("#高強度")
        elif avg_hr <= zone2_upper:
            tags.append("#恢復")
        else:
            tags.append("#中強度")

    summary_text = "\n".join(lines)
    file_placeholder = f"{name}.strava"

    return summary_text, file_placeholder, tags
