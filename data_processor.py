# data_processor.py
import pandas as pd
from fitparse import FitFile

def process_fit_data(file_path):
    fitfile = FitFile(file_path)
    records = []
    session_data = {}
    
    # 掃描檔案中所有的訊息區塊（一趟讀取完成）
    for msg in fitfile.get_messages():
        if msg.name == 'record':
            records.append(msg.get_values())
        elif msg.name == 'session':
            # session 區塊通常包含了手錶計算好的高階指標，例如 TE
            session_data = msg.get_values()
            
    df = pd.DataFrame(records)
    
    # 單位轉換與數值校正 (針對 Garmin Forerunner 對應)
    # 1. 配速轉換 (m/s 轉成 min/km)
    if 'enhanced_speed' in df: 
        df['pace'] = 16.6667 / df['enhanced_speed']
    elif 'speed' in df:
        df['pace'] = 16.6667 / df['speed']
        
    # 2. 距離轉換 (m 轉 km)
    if 'distance' in df: 
        df['dist_km'] = df['distance'] / 1000
        
    # 3. 步頻修正 (Garmin 原生 FIT 中的 cadence 常為 rpm(單腳)，需乘 2 變雙腳 spm)
    if 'cadence' in df:
        # 防呆機制：如果平均步頻小於 120，肯定是單腳資料
        if df['cadence'].mean() < 120:
            df['cadence'] = df['cadence'] * 2
            # 同步修正 session 總結裡的高階步頻
            if 'avg_running_cadence' in session_data:
                session_data['avg_running_cadence'] = session_data['avg_running_cadence'] * 2
            if 'max_running_cadence' in session_data:
                session_data['max_running_cadence'] = session_data['max_running_cadence'] * 2
                
    # 4. 垂直振幅 (Vertical Oscillation): 原生通常為 mm，但通常查看習慣是以 cm 為單位
    if 'vertical_oscillation' in df:
        # 防呆：如果數值平均超過 30，代表單位是 mm，我們將它除以 10 轉為 cm 以對齊儀表板
        if df['vertical_oscillation'].mean() > 30:
            df['vertical_oscillation'] = df['vertical_oscillation'] / 10

    # 定義顯示清單 (給 UI 畫圖用)
    friendly_names = {
        'heart_rate': '心率 (bpm)',
        'power': '功率 (W)',
        'pace': '配速 (min/km)',
        'cadence': '步頻 (spm)',
        'stance_time': '觸地時間 (ms)',
        'vertical_oscillation': '垂直振幅 (cm)',
        'altitude': '高度 (m)'
    }
    available_metrics = {k: v for k, v in friendly_names.items() if k in df.columns}
    
    # --- 提煉神級分析摘要給 AI 教練 ---
    summary_lines = []
    
    # 1. 如果有挖到隱藏的 session 數據，優先使用它 (這與 Garmin Connect 上的報告一致)
    if session_data:
        summary_lines.append("📍 [本機 .fit 內建高階總結]")
        s_dist = session_data.get('total_distance', 0) / 1000
        summary_lines.append(f"- 總距離: {s_dist:.2f} km")
        s_time = session_data.get('total_elapsed_time', 0) / 60
        summary_lines.append(f"- 總時間: {s_time:.2f} 分")
        if session_data.get('avg_heart_rate'):
            summary_lines.append(f"- 平均心率: {session_data['avg_heart_rate']} bpm (最高: {session_data.get('max_heart_rate', 'N/A')})")
        if session_data.get('total_training_effect') is not None:
            summary_lines.append(f"- 有氧訓練效果 (TE): {session_data['total_training_effect']}")
        if session_data.get('total_anaerobic_training_effect') is not None:
            summary_lines.append(f"- 無氧訓練效果 (TE): {session_data['total_anaerobic_training_effect']}")
        if session_data.get('avg_running_cadence'):
            summary_lines.append(f"- 平均步頻: {session_data['avg_running_cadence']} spm")
        if session_data.get('total_calories'):
            summary_lines.append(f"- 消耗卡路里: {session_data['total_calories']} kcal")
            
        # 2. 結合秒級資料 (df) 算出的進階跑步動態指標
        summary_lines.append("\n📍 [進階跑步動態 (平均值)]")
        if 'step_length' in df.columns and not df['step_length'].isna().all():
            summary_lines.append(f"- 平均步幅: {df['step_length'].mean():.1f} mm")
        if 'vertical_oscillation' in df.columns and not df['vertical_oscillation'].isna().all():
            summary_lines.append(f"- 平均垂直振幅: {df['vertical_oscillation'].mean():.2f} cm")
        if 'stance_time' in df.columns and not df['stance_time'].isna().all():
            summary_lines.append(f"- 平均觸地時間: {df['stance_time'].mean():.1f} ms")
        if 'power' in df.columns and not df['power'].isna().all():
            summary_lines.append(f"- 平均跑步功率: {df['power'].mean():.0f} W")
            
        # 3. 自動生成每公里分段資料 (Auto-Splits)
        if 'dist_km' in df.columns and 'pace' in df.columns:
            summary_lines.append("\n📊 [每公里分段摘要 (Auto-Splits)]")
            df['km_bin'] = (df['dist_km'] // 1.0).astype(int) + 1
            splits = df.groupby('km_bin').agg({
                'pace': 'mean',
                'heart_rate': 'mean',
                'cadence': 'mean'
            })
            
            for km, row in splits.iterrows():
                # 簡單過濾掉最後一小段不足 100 公尺的零碎數據 (避免配速失真)
                if km > df['dist_km'].max() + 0.1: continue
                
                # --- 關鍵修正：防禦無限大 (inf) 或 非數值 (nan) 導致的 int 崩潰 ---
                import numpy as np
                pace_val = row['pace']
                if not np.isfinite(pace_val) or np.isnan(pace_val):
                    p_min, p_sec = 0, 0
                else:
                    p_min = int(pace_val)
                    p_sec = int((pace_val - p_min) * 60)
                
                hr = int(row['heart_rate']) if not pd.isna(row['heart_rate']) and np.isfinite(row['heart_rate']) else "N/A"
                cad = int(row['cadence']) if not pd.isna(row['cadence']) and np.isfinite(row['cadence']) else "N/A"
                summary_lines.append(f"- 第 {km} km: {p_min}'{p_sec:02d}\", 心率: {hr}, 步頻: {cad}")

        summary = "\n".join(summary_lines)
    else:
        # 2. 如果該檔案舊版或缺乏 session，降級使用 DataFrame 窮舉計算
        summary = f"平均心率: {df['heart_rate'].mean():.0f} bpm, 總里程: {df['dist_km'].max():.2f} km (未包含進階 TE 數據)"
        
    return df, summary, available_metrics