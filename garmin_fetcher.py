import zipfile
import io
import os
import json
from garminconnect import Garmin

def get_garmin_data(email, password):
    try:
        token_dir = "./garmin_session"
        client = Garmin(email, password)
        
        # 策略：嘗試使用舊憑證登入，略過 Cloudflare 嚴格的 SSO 防機器人檢查
        try:
            client.login(token_dir)
        except Exception:
            try:
                client.login()
                # 登入成功後儲存憑證 (只要嚴格的審查過關一次，以後均直接取用 Session)
                if not os.path.exists(token_dir):
                    os.makedirs(token_dir)
                client.garth.dump(token_dir)
            except Exception as e:
                if "429" in str(e):
                    return False, "遭到 Garmin 平台防爬蟲機制阻擋 (429 Too Many Requests)。\n\n👉 解法：這是因為 Garmin 對全新嘗試的防護較嚴，請不要狂點，放置約 15~30 分鐘後再重試！只要能登進去一次，程式就會永久儲存免死金牌 (Session)，之後就能秒速抓取了。", None
                return False, f"帳密登入失敗: {e}", None

        # 取得最近 10 筆活動，並找出最新的一筆「跑步」
        activities = client.get_activities(0, 10)
        latest_run = next((act for act in activities if act.get('activityType', {}).get('typeKey') == 'running'), None)
        
        if not latest_run:
            return False, "找不到最近的跑步紀錄", None
            
        activity_id = latest_run['activityId']
        
        # 1. 整理超級豐富的摘要資料 (作為給教練分析的神級數據)
        rich_summary = {
            "活動名稱": latest_run.get('activityName', '未命名'),
            "開始時間": latest_run.get('startTimeLocal'),
            "距離 (km)": round(latest_run.get('distance', 0) / 1000, 2),
            "總時間 (分)": round(latest_run.get('duration', 0) / 60, 2),
            "平均配速 (min/km)": round(16.6667 / latest_run.get('averageSpeed', 16.6667), 2) if latest_run.get('averageSpeed') else 0,
            "平均心率": latest_run.get('averageHR'),
            "最大心率": latest_run.get('maxHR'),
            "有氧訓練效果 (TE)": latest_run.get('aerobicTrainingEffect'),
            "無氧訓練效果 (TE)": latest_run.get('anaerobicTrainingEffect'),
            "訓練負荷": latest_run.get('trainingLoadPeak'),
            "預估 VO2Max": latest_run.get('vO2MaxValue'),
            "平均步頻": latest_run.get('averageRunningCadenceInStepsPerMinute'),
            "最大步頻": latest_run.get('maxRunningCadenceInStepsPerMinute'),
            "平均步幅 (cm)": latest_run.get('avgStrideLength'),
            "卡路里": latest_run.get('calories'),
        }
        
        # 轉換為文字格式，讓 LLM 更容易閱讀
        summary_text = "📍 [Garmin 官方數據總結]\n" + "\n".join([f"- {k}: {v}" for k, v in rich_summary.items() if v is not None])
        
        # 2. 下載原始 .fit 檔案 (供儀表板畫圖用)
        try:
            zip_data = client.download_activity(activity_id, dl_fmt=client.ActivityDownloadFormat.ORIGINAL)
            with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
                # 找出 zip 內的 fit 檔案
                fit_filename = next((name for name in z.namelist() if name.endswith('.fit')), None)
                if fit_filename:
                    fit_bytes = z.read(fit_filename)
                    with open("temp.fit", "wb") as f:
                        f.write(fit_bytes)
                else:
                    return False, "下載的壓縮檔內沒有 .fit 檔案", None
        except Exception as e:
            return False, f"下載 .fit 檔案失敗: {e}", None
            
        return True, "成功獲取資料", summary_text

    except Exception as e:
        return False, f"Garmin 抓取失敗: {e}", None

if __name__ == '__main__':
    # Simple test logic
    with open("keys.json", "r") as f:
        k = json.load(f)
    print("Test fetch...")
    # res, msg, summary = get_garmin_data(k.get("GARMIN_EMAIL"), k.get("GARMIN_PASSWORD"))
    # print(msg)
    # print(summary)
