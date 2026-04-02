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
            return pd.DataFrame(), f"不支援的檔案格式: {ext}", {}, []
    except Exception as e:
        return pd.DataFrame(), f"解析檔案時發生異常: {str(e)}", {}, []

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
        return pd.DataFrame(), "CSV 檔案為空", {}, []

    # 找數據起點
    mask = raw_df[0].astype(str).str.strip().str.replace('"', '', regex=False) == "1"
    start_indices = raw_df.index[mask].tolist()
    if not start_indices:
        return pd.DataFrame(), "無法在 CSV 中找到計圈數據起點（找不到第 1 圈）", {}, []
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
        return df, "解析後數據為空", {}, []

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
    lines = ["📊 [數據解析成功：計圈跑姿數據]"]
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

    # --- 自動標籤邏輯 ---
    tags = []
    if 'dist_km' in df.columns:
        total_dist = df['dist_km'].sum()
        if total_dist > 15: tags.append("#長距離")
        elif total_dist > 8: tags.append("#普通跑")
        else: tags.append("#短程訓練")
    
    # 判斷間歇: 若圈數 > 3 且配速波動大
    if len(df) > 3 and 'pace' in df.columns:
        pace_std = df['pace'].std()
        if pace_std > 0.5: # 0.5 min/km = 30s/km fluctuation
            tags.append("#間歇跑")
    
    # 判斷強度: 若平均心率 > 160
    if 'heart_rate' in df.columns and df['heart_rate'].mean() > 160:
        tags.append("#高強度")
    elif 'heart_rate' in df.columns and df['heart_rate'].mean() < 130:
        tags.append("#恢復跑")

    summary = "\n".join(lines)
    metrics = {
        'heart_rate': '心率', 'pace': '配速',
        'cadence': '步頻', 'gct': '觸地時間',
        'vertical_osc': '垂直震幅', 'grade': '坡度'
    }
    return df, summary, metrics, tags

def process_history_summary(file_path):
    """處理 Garmin 匯出的活動清單總表 (每列一個活動)"""
    try:
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
        except:
            df = pd.read_csv(file_path, encoding='big5')

        if df.empty:
            return "檔案內容為空"

        # 欄位標準化 (Garmin 常用)
        mapping = {
            'Activity Type': 'type', '活動類型': 'type',
            'Date': 'date', '日期': 'date',
            'Distance': 'dist', '距離': 'dist',
            'Calories': 'cal', '卡路里': 'cal',
            'Time': 'time', '時間': 'time',
            'Avg HR': 'hr', '平均心率': 'hr',
            'Avg Pace': 'pace', '平均配速': 'pace',
            'Elev Gain': 'elev', '高度增加': 'elev'
        }
        df = df.rename(columns=mapping)
        
        # 只取跑步 (包含 Run, Street Running, Trail Running 等)
        run_keywords = ['run', '跑', '跑步']
        if 'type' in df.columns:
            df = df[df['type'].astype(str).str.lower().str.contains('|'.join(run_keywords), na=False)]

        if df.empty:
            return "在總表中找不到任何跑步活動"

        # 轉換距離與日期
        df['dist'] = pd.to_numeric(df['dist'], errors='coerce')
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date', 'dist'])
        df = df.sort_values('date', ascending=False)

        # 計算統計資訊
        total_runs = len(df)
        total_dist = df['dist'].sum()
        
        last_30_days = df[df['date'] > (pd.Timestamp.now() - pd.Timedelta(days=30))]
        monthly_dist = last_30_days['dist'].sum()
        avg_hr = df['hr'].astype(str).str.replace('--', '0').replace('', '0').astype(float, errors='ignore')
        avg_hr = pd.to_numeric(avg_hr, errors='coerce').mean()
        
        # 額外提取：最近 5 次跑步明細
        recent_list = []
        for _, row in df.head(5).iterrows():
            d_str = row['date'].strftime('%m/%d')
            recent_list.append(f"{d_str}: {row['dist']}km (配速: {row.get('pace','?')})")
        recent_str = "\n  ".join(recent_list)

        # 額外提取：跑者成就
        max_dist = df['dist'].max()
        best_pace = "N/A"
        if 'pace' in df.columns:
            # 這裡簡單取最快的一筆 (需注意格式)
            best_pace = df['pace'].sort_values().iloc[0]

        summary_text = f"""
【跑者長期訓練總表 - 深度分析檔案】
- 數據涵蓋期間: {df['date'].min().strftime('%Y/%m/%d')} ~ {df['date'].max().strftime('%Y/%m/%d')}
- 歷史總跑步: {total_runs} 次 / 總里程: {total_dist:.1f} km
- 最近 30 天訓練量: {monthly_dist:.1f} km
- 歷史平均心率: {avg_hr:.0f} bpm
- 歷史單次最長距離: {max_dist:.1f} km
- 最佳配速參考: {best_pace}
- 最近 5 次練跑紀錄:
  {recent_str}
        """
        return summary_text
    except Exception as e:
        return f"解析總表失敗: {str(e)}"