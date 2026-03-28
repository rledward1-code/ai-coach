# data_processor.py
import pandas as pd
from fitparse import FitFile
import os
import numpy as np

def process_fit_data(file_path):
    """
    處理跑步數據文件 (.fit 或 .csv)
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if ext == ".fit":
            return _process_fit(file_path)
        elif ext == ".csv":
            return _process_csv(file_path)
        else:
            return pd.DataFrame(), f"不支援的檔案格式: {ext}", {}
    except Exception as e:
        return pd.DataFrame(), f"解析檔案時發生錯誤: {str(e)}", {}

def _process_fit(file_path):
    fitfile = FitFile(file_path)
    records = []
    session_data = {}
    
    for msg in fitfile.get_messages():
        if msg.name == 'record':
            records.append(msg.get_values())
        elif msg.name == 'session':
            session_data = msg.get_values()
            
    df = pd.DataFrame(records)
    return _apply_standard_processing(df, session_data)

def _process_csv(file_path):
    """
    處理 CSV 文件。嘗試解析常見的跑步數據列名。
    """
    try:
        # 嘗試不同的編碼
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
        except:
            df = pd.read_csv(file_path, encoding='big5') # 針對台灣常見編碼
    except:
        df = pd.read_csv(file_path) # 最後嘗試預設

    # 嘗試將常見列名映射到內部標準
    column_map = {
        'Heart Rate': 'heart_rate', 'HR': 'heart_rate', '心率': 'heart_rate', '平均心率': 'heart_rate',
        'Speed': 'speed', 'Velocity': 'speed', '速度': 'speed',
        'Pace': 'pace', '配速': 'pace', '平均配速': 'pace',
        'Cadence': 'cadence', 'Step Rate': 'cadence', '步頻': 'cadence', '平均步頻': 'cadence',
        'Distance': 'distance', 'Dist': 'distance', '里程': 'distance', '距離': 'distance', '總距離': 'distance',
        'Altitude': 'altitude', 'Elevation': 'altitude', '高度': 'altitude', '海拔': 'altitude',
        'Stance Time': 'stance_time', 'GCT': 'stance_time', '觸地時間': 'stance_time',
        'Vertical Oscillation': 'vertical_oscillation', 'VO': 'vertical_oscillation', '垂直振幅': 'vertical_oscillation',
        'Power': 'power', 'Watts': 'power', '功率': 'power'
    }
    
    # 執行重命名 (不區分大小寫且移除空白)
    rename_dict = {}
    for col in df.columns:
        clean_col = str(col).strip()
        for key, val in column_map.items():
            if key.lower() == clean_col.lower():
                rename_dict[col] = val
                break
    df.rename(columns=rename_dict, inplace=True)
    
    # 如果 CSV 已經有 pace 列且格式為 5:30，轉換為十進制 min/km
    if 'pace' in df.columns:
        def pace_to_decimal(p):
            try:
                if isinstance(p, str) and ':' in p:
                    parts = p.split(':')
                    if len(parts) == 2:
                        m, s = map(int, parts)
                        return m + s/60.0
                return float(p)
            except:
                return np.nan
        df['pace'] = df['pace'].apply(pace_to_decimal)
            
    return _apply_standard_processing(df, {})

def _apply_standard_processing(df, session_data):
    if df.empty:
        return df, "檔案內容為空，無法讀取數據。", {}

    # 1. 配速與速度處理
    if 'enhanced_speed' in df: 
        df['pace'] = 16.6667 / df['enhanced_speed']
    elif 'speed' in df and 'pace' not in df:
        # 防止除以 0
        df['pace'] = df['speed'].apply(lambda x: 16.6667/x if x > 0 else 0)
        
    # 2. 距離轉換 (m 轉 km)
    if 'distance' in df: 
        if df['distance'].max() > 500: 
            df['dist_km'] = df['distance'] / 1000
        else:
            df['dist_km'] = df['distance']
            
    # 3. 步頻修正
    if 'cadence' in df:
        if df['cadence'].mean() < 120:
            df['cadence'] = df['cadence'] * 2
            if 'avg_running_cadence' in session_data:
                session_data['avg_running_cadence'] = session_data['avg_running_cadence'] * 2
                
    # 4. 垂直振幅
    if 'vertical_oscillation' in df:
        if df['vertical_oscillation'].mean() > 30:
            df['vertical_oscillation'] = df['vertical_oscillation'] / 10

    friendly_names = {
        'heart_rate': '心率 (bpm)', 'power': '功率 (W)', 'pace': '配速 (min/km)',
        'cadence': '步頻 (spm)', 'stance_time': '觸地時間 (ms)',
        'vertical_oscillation': '垂直振幅 (cm)', 'altitude': '高度 (m)'
    }
    available_metrics = {k: v for k, v in friendly_names.items() if k in df.columns}
    
    summary_lines = []
    
    if session_data:
        summary_lines.append("📍 [數據總結]")
        s_dist = session_data.get('total_distance', 0) / 1000
        summary_lines.append(f"- 總距離: {s_dist:.2f} km")
        s_time = session_data.get('total_elapsed_time', 0) / 60
        summary_lines.append(f"- 總時間: {s_time:.2f} 分")
        if session_data.get('avg_heart_rate'):
            summary_lines.append(f"- 平均心率: {session_data['avg_heart_rate']} bpm")
        if session_data.get('total_training_effect') is not None:
            summary_lines.append(f"- 有氧訓練效果 (TE): {session_data['total_training_effect']}")
    else:
        summary_lines.append("📍 [基礎數據統計]")
        if 'heart_rate' in df.columns:
            summary_lines.append(f"- 平均心率: {df['heart_rate'].mean():.0f} bpm")
        if 'dist_km' in df.columns:
            summary_lines.append(f"- 總距離: {df['dist_km'].max():.2f} km")
        if 'pace' in df.columns:
            # 過濾掉異常配速
            valid_pace = df['pace'][df['pace'] > 0]
            if not valid_pace.empty:
                summary_lines.append(f"- 平均配速: {valid_pace.mean():.2f} min/km")

    # 每公里分段
    if 'dist_km' in df.columns and 'pace' in df.columns:
        summary_lines.append("\n📊 [每公里分段摘要]")
        df['km_bin'] = (df['dist_km'] // 1.0).astype(int) + 1
        
        # 準備聚合
        agg_dict = {'pace': 'mean'}
        if 'heart_rate' in df.columns: agg_dict['heart_rate'] = 'mean'
        if 'cadence' in df.columns: agg_dict['cadence'] = 'mean'
        
        splits = df.groupby('km_bin').agg(agg_dict)
        
        for km, row in splits.iterrows():
            if km > df['dist_km'].max() + 0.1: continue
            pace_val = row['pace']
            if not np.isfinite(pace_val) or np.isnan(pace_val) or pace_val == 0:
                p_text = "N/A"
            else:
                p_min = int(pace_val)
                p_sec = int((pace_val - p_min) * 60)
                p_text = f"{p_min}'{p_sec:02d}\""
            
            hr_text = f", 心率: {int(row['heart_rate'])}" if 'heart_rate' in df.columns else ""
            summary_lines.append(f"- 第 {km} km: {p_text}{hr_text}")

    if len(summary_lines) <= 1: # 只有標題
        summary_lines.append("(警告：未能辨識出關鍵數據，請檢查 CSV 標題列名是否包含里程、心率等關鍵字)")

    return df, "\n".join(summary_lines), available_metrics