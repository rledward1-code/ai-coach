# data_processor.py
import pandas as pd
from fitparse import FitFile
import os
import numpy as np

def process_data(file_path):
    """處理跑步數據文件 (.fit 或 .csv)"""
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

# Garmin CSV 欄位名稱 → 內部欄位名稱（含中英文版本）
COLUMN_ALIASES = {
    'lap':          ['lap', '計圈', 'laps', '圈'],
    'time_str':     ['time', '時間', 'duration', '持續時間', 'lap time'],
    'distance':     ['distance', '距離', 'dist'],
    'pace_str':     ['avg pace', '平均配速', 'pace', '配速'],
    'heart_rate':   ['avg hr', '平均心率', 'heart rate', 'avg heart rate', '心率'],
    'cadence':      ['avg run cadence', 'avg cadence', '平均跑步步頻', '步頻', 'cadence', 'run cadence'],
    'grade':        ['avg grade', 'grade', '坡度', '平均坡度', 'incline'],
    'elevation':    ['min elevation', 'max elevation', 'elevation', '海拔', '高度'],
    'gct':          ['avg ground contact time', 'ground contact time', '平均觸地時間', '觸地時間', 'gct', 'contact time'],
    'vertical_osc': ['avg vertical oscillation', 'vertical oscillation', '平均垂直震幅', '垂直震幅', 'vertical ratio'],
}

def _find_col(header_series, aliases):
    """在 header 中找到第一個匹配 alias 的欄位 index"""
    normalized = [str(h).strip().strip('"').lower() for h in header_series]
    for alias in aliases:
        for i, h in enumerate(normalized):
            if alias.lower() in h:
                return i
    return None

def _process_csv(file_path):
    """
    動態解析 Garmin 計圈 CSV：
    1. 找到數據起點（第一欄為 "1" 的行）
    2. 向前搜尋 header 行（非數字的最後一行）
    3. 用欄位名稱動態 mapping，不依賴固定 index
    """
    try:
        raw_df = pd.read_csv(file_path, header=None, encoding='utf-8', on_bad_lines='skip')
    except:
        raw_df = pd.read_csv(file_path, header=None, encoding='big5', on_bad_lines='skip')

    if raw_df.empty:
        return pd.DataFrame(), "CSV 檔案為空", {}

    # 找數據起點
    mask = raw_df[0].astype(str).str.strip().str.replace('"', '', regex=False) == "1"
    start_indices = raw_df.index[mask].tolist()
    if not start_indices:
        return pd.DataFrame(), "無法在 CSV 中找到計圈數據起點（找不到第 1 圈）", {}
    start_row = start_indices[0]

    # 向前找 header 行：從 start_row-1 往上，取最近的非空、非數字行
    header_row_idx = None
    for i in range(start_row - 1, max(start_row - 5, -1), -1):
        cell = str(raw_df.iloc[i, 0]).strip().strip('"').lower()
        if cell and not cell.lstrip('-').replace('.', '', 1).isdigit():
            header_row_idx = i
            break

    # 切出數據部分
    data_df = raw_df.iloc[start_row:].copy().reset_index(drop=True)

    if header_row_idx is not None:
        # 動態 mapping：用欄位名稱找 index
        header_series = raw_df.iloc[header_row_idx]
        col_map = {}
        for field, aliases in COLUMN_ALIASES.items():
            idx = _find_col(header_series, aliases)
            if idx is not None and idx < len(data_df.columns):
                col_map[idx] = field
    else:
        # 找不到 header 就用保守的固定 mapping（舊方法備案）
        col_map = {0: 'lap', 1: 'time_str', 3: 'distance', 4: 'pace_str',
                   6: 'heart_rate', 10: 'cadence', 11: 'grade', 12: 'elevation'}

    data_df = data_df.rename(columns=col_map)
    data_df = data_df[[c for c in data_df.columns if isinstance(c, str)]]

    # 清掉非數字的 lap 行（摘要行）
    if 'lap' in data_df.columns:
        data_df = data_df[data_df['lap'].astype(str).str.strip().str.replace('"', '', regex=False).str.isdigit()]

    return _apply_standard_processing(data_df, {})

def _apply_standard_processing(df, session_data):
    if df.empty:
        return df, "解析後數據為空", {}

    def clean_val(x):
        if pd.isna(x): return x
        return str(x).replace('"', '').replace(',', '').strip()

    for col in df.columns:
        df[col] = df[col].apply(clean_val)

    # 距離校正
    if 'distance' in df.columns:
        df['distance'] = pd.to_numeric(df['distance'], errors='coerce')
        df['dist_km'] = df['distance'] / 1000 if df['distance'].max() > 500 else df['distance']

    # 心率
    if 'heart_rate' in df.columns:
        df['heart_rate'] = pd.to_numeric(df['heart_rate'], errors='coerce')

    # 配速 5:30 → 5.5
    if 'pace_str' in df.columns:
        def p_to_f(p):
            try:
                if ':' in str(p):
                    m, s = map(int, str(p).split(':'))
                    return m + s / 60.0
                return float(p)
            except:
                return np.nan
        df['pace'] = df['pace_str'].apply(p_to_f)

    # 數值欄位轉型
    for col in ['cadence', 'grade', 'elevation', 'gct', 'vertical_osc']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 生成摘要文字
    lines = ["📊 [CSV 解析成功：計圈跑姿數據]"]
    if 'dist_km' in df.columns:
        lines.append(f"- 訓練總距離: {df['dist_km'].sum():.2f} km")

    # 整體平均（有跑姿數據才顯示）
    avg_parts = []
    if 'cadence' in df.columns and df['cadence'].notna().any():
        avg_parts.append(f"平均步頻 {df['cadence'].mean():.0f} spm")
    if 'gct' in df.columns and df['gct'].notna().any():
        avg_parts.append(f"平均觸地時間 {df['gct'].mean():.0f} ms")
    if 'vertical_osc' in df.columns and df['vertical_osc'].notna().any():
        avg_parts.append(f"平均垂直震幅 {df['vertical_osc'].mean():.1f} cm")
    if avg_parts:
        lines.append("- 整體平均跑姿: " + ", ".join(avg_parts))

    lines.append("")  # 空行分隔

    for _, row in df.iterrows():
        lap = row.get('lap', '?')
        p   = row.get('pace_str', 'N/A')
        hr  = row.get('heart_rate', 'N/A')
        cad = row.get('cadence', None)
        gct = row.get('gct', None)
        vo  = row.get('vertical_osc', None)
        gr  = row.get('grade', None)

        parts = [f"配速 {p}", f"心率 {hr} bpm"]
        if pd.notna(cad) if cad is not None else False:
            parts.append(f"步頻 {cad:.0f}")
        if pd.notna(gct) if gct is not None else False:
            parts.append(f"觸地 {gct:.0f}ms")
        if pd.notna(vo) if vo is not None else False:
            parts.append(f"垂直振幅 {vo:.1f}cm")
        if pd.notna(gr) if gr is not None else False:
            parts.append(f"坡度 {gr:.1f}%")

        lines.append(f"- 第 {lap} 圈: " + ", ".join(parts))

    summary = "\n".join(lines)
    metrics = {
        'heart_rate': '心率', 'pace': '配速',
        'cadence': '步頻', 'gct': '觸地時間',
        'vertical_osc': '垂直震幅', 'grade': '坡度'
    }
    return df, summary, metrics