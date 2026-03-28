# data_processor.py
import pandas as pd
from fitparse import FitFile
import os
import numpy as np

def process_data(file_path):
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
        return pd.DataFrame(), f"解析檔案時發生異常: {str(e)}", {}

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
    針對 Garmin 網頁導出的 CSV 進行硬核解析。
    特徵：前 20-30 行可能是碎片標題，數據始於第一個第一欄為 "1" 的行。
    """
    # 讀取全文
    try:
        raw_df = pd.read_csv(file_path, header=None, encoding='utf-8', on_bad_lines='skip')
    except:
        raw_df = pd.read_csv(file_path, header=None, encoding='big5', on_bad_lines='skip')

    if raw_df.empty:
        return pd.DataFrame(), "CSV 檔案為空", {}

    # 尋找數據起點：第一欄內容為 "1" (字串或數字)
    # 考慮到引號，使用正則或簡單包含判斷
    mask = raw_df[0].astype(str).str.strip().replace('"', '', regex=False) == "1"
    start_indices = raw_df.index[mask].tolist()

    if not start_indices:
        return pd.DataFrame(), "無法在 CSV 中找到計圈數據起點（找不到第 1 圈）", {}

    start_row = start_indices[0]
    
    # 重新切分 DataFrame
    data_df = raw_df.iloc[start_row:].copy()
    
    # Garmin 網頁計圈 CSV 典型列順序 (繁體/簡體/英文通用標記)：
    # 0: Lap, 1: Time, 2: Cumulative Time, 3: Distance, 4: Avg Pace, 6: Avg HR...
    # 我們根據位置強制命名，因為標題列太碎了
    cols_to_use = {
        0: 'lap',
        1: 'time_str',
        3: 'distance',
        4: 'pace_str',
        6: 'heart_rate',
        10: 'cadence',
        11: 'grade',        # 平均坡度 (%)
        12: 'elevation'     # 最小/最大海拔 (m)
    }
    
    # 重新命名可用的列
    data_df = data_df.rename(columns=cols_to_use)
    # 僅保留我們命名的列
    data_df = data_df[[c for c in data_df.columns if isinstance(c, str)]]
    
    # 清理掉「摘要」或空的行 (Lap 必須是數字)
    data_df = data_df[data_df['lap'].astype(str).str.strip().replace('"', '', regex=False).str.isdigit()]

    return _apply_standard_processing(data_df, {})

def _apply_standard_processing(df, session_data):
    if df.empty:
        return df, "解析後數據為空", {}

    # 1. 數值轉換 (移除引號與逗號)
    def clean_val(x):
        if pd.isna(x): return x
        return str(x).replace('"', '').replace(',', '').strip()

    for col in df.columns:
        df[col] = df[col].apply(clean_val)

    # 2. 距離校正 (公里)
    if 'distance' in df.columns:
        df['distance'] = pd.to_numeric(df['distance'], errors='coerce')
        if df['distance'].max() > 500: # 可能是公尺
            df['dist_km'] = df['distance'] / 1000
        else:
            df['dist_km'] = df['distance']
            
    # 3. 心率校正
    if 'heart_rate' in df.columns:
        df['heart_rate'] = pd.to_numeric(df['heart_rate'], errors='coerce')
        
    # 4. 配速校正 (5:30 -> 5.5)
    if 'pace_str' in df.columns:
        def p_to_f(p):
            try:
                if ':' in str(p):
                    m, s = map(int, str(p).split(':'))
                    return m + s/60.0
                return float(p)
            except: return np.nan
        df['pace'] = df['pace_str'].apply(p_to_f)

    # 5. 坡度與海拔
    if 'grade' in df.columns:
        df['grade'] = pd.to_numeric(df['grade'], errors='coerce')
    if 'elevation' in df.columns:
        df['elevation'] = pd.to_numeric(df['elevation'], errors='coerce')

    # 6. 生成摘要文字
    lines = ["📊 [CSV 解析成功：計圈數據詳情]"]
    if 'dist_km' in df.columns:
        lines.append(f"- 訓練總距離: {df['dist_km'].sum():.2f} km (計圈累計)")
    
    for _, row in df.iterrows():
        lap = row['lap']
        p = row.get('pace_str', 'N/A')
        hr = row.get('heart_rate', 'N/A')
        grade = row.get('grade', None)
        elev = row.get('elevation', None)
        lap_str = f"- 第 {lap} 圈: 配速 {p}, 心率 {hr} bpm"
        if pd.notna(grade) if grade is not None else False:
            lap_str += f", 坡度 {grade:.1f}%"
        if pd.notna(elev) if elev is not None else False:
            lap_str += f", 海拔 {elev:.0f}m"
        lines.append(lap_str)

    summary = "\n".join(lines)
    metrics = {'heart_rate': '心率', 'pace': '配速', 'grade': '坡度', 'elevation': '海拔'}
    
    return df, summary, metrics