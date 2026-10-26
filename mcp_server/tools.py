# d:\ai-coach\mcp_server\tools.py
"""
AI Coach 核心運動科學計算與資料處理工具庫。
專為 Edward (Max HR 210, Rest HR 53, LTHR 193) 精密校準。
"""

import os
import sys
import json
import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional

# 將專案根目錄加入 sys.path 以便重用 data_processor
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import data_processor
import garmin_local

# --- Edward 專屬生理基線常數 ---
EDWARD_MAX_HR = 210
EDWARD_REST_HR = 53
EDWARD_LTHR = 193

EDWARD_HR_ZONES = {
    "Zone 1 (恢復區)": {"min": 132, "max": 147, "desc": "暖身、主動恢復、神經肌肉活化"},
    "Zone 2 (基礎有氧 - 路格嚴選)": {"min": 148, "max": 163, "desc": "心肌肥厚、粒線體擴增、脂肪燃燒效率最高區間 (路格神聖防線)"},
    "Zone 3 (節奏有氧)": {"min": 164, "max": 179, "desc": "中高有氧、有氧閾值上限、長距離比賽配速"},
    "Zone 4 (乳酸閾值)": {"min": 180, "max": 194, "desc": "乳酸堆積平衡臨界點、耐乳酸訓練"},
    "Zone 5 (無氧極限 / VO2Max)": {"min": 195, "max": 210, "desc": "最大攝氧量衝擊、神經肌肉爆發、心肺極限"}
}

def get_zone_for_hr(hr: float) -> str:
    """根據 Edward 專屬 210/53 心率標準判定區間"""
    if not hr or hr <= 0 or math.isnan(hr):
        return "N/A"
    if hr < 132:
        return "< Zone 1"
    elif hr <= 147:
        return "Zone 1"
    elif hr <= 163:
        return "Zone 2"
    elif hr <= 179:
        return "Zone 3"
    elif hr <= 194:
        return "Zone 4"
    else:
        return "Zone 5"

def parse_activity_data(file_path: str) -> Dict[str, Any]:
    """
    完整解析跑步活動資料 (.fit 或 .csv)。
    包含圈數明細、跑姿指標、心率分區統計與自動標籤。
    """
    if not os.path.exists(file_path):
        # 嘗試相對專案路徑
        alt_path = os.path.join(PROJECT_ROOT, file_path)
        if os.path.exists(alt_path):
            file_path = alt_path
        else:
            return {"error": f"找不到活動檔案：{file_path}"}

    df, summary_text, metrics, tags = data_processor.process_data(file_path)
    if df.empty:
        return {"error": f"檔案解析失敗或無資料：{summary_text}"}

    # 統計全體數據
    total_dist = float(df['dist_km'].sum()) if 'dist_km' in df.columns else 0.0
    avg_hr = float(df['heart_rate'].mean()) if 'heart_rate' in df.columns and df['heart_rate'].notna().any() else None
    max_hr = float(df['heart_rate'].max()) if 'heart_rate' in df.columns and df['heart_rate'].notna().any() else None
    avg_cadence = float(df['cadence'].mean()) if 'cadence' in df.columns and df['cadence'].notna().any() else None
    avg_gct = float(df['gct'].mean()) if 'gct' in df.columns and df['gct'].notna().any() else None
    avg_vo = float(df['vertical_osc'].mean()) if 'vertical_osc' in df.columns and df['vertical_osc'].notna().any() else None

    # 配速計算
    avg_pace_val = float(df['pace'].mean()) if 'pace' in df.columns and df['pace'].notna().any() else None
    avg_pace_str = f"{int(avg_pace_val)}:{int((avg_pace_val % 1)*60):02d}" if avg_pace_val and not math.isnan(avg_pace_val) else "N/A"

    # 心率區間佔比分析 (以每圈為單位估算)
    zone_counts = {"Zone 1": 0, "Zone 2": 0, "Zone 3": 0, "Zone 4": 0, "Zone 5": 0, "Other": 0}
    if 'heart_rate' in df.columns:
        for hr in df['heart_rate'].dropna():
            z = get_zone_for_hr(hr)
            if z in zone_counts:
                zone_counts[z] += 1
            else:
                zone_counts["Other"] += 1

    total_pts = sum(zone_counts.values()) or 1
    zone_percentages = {z: round((cnt / total_pts) * 100, 1) for z, cnt in zone_counts.items()}

    # 各圈 Lap 明細精華
    laps_detail = []
    for _, row in df.iterrows():
        lap_num = int(row.get('lap', len(laps_detail) + 1))
        p_str = str(row.get('pace_str', 'N/A'))
        hr_val = float(row.get('heart_rate')) if pd.notna(row.get('heart_rate')) else None
        cad_val = float(row.get('cadence')) if pd.notna(row.get('cadence')) else None
        gct_val = float(row.get('gct')) if pd.notna(row.get('gct')) else None
        vo_val = float(row.get('vertical_osc')) if pd.notna(row.get('vertical_osc')) else None
        dist_val = float(row.get('dist_km')) if pd.notna(row.get('dist_km')) else None

        laps_detail.append({
            "lap": lap_num,
            "distance_km": round(dist_val, 2) if dist_val else None,
            "pace": p_str,
            "heart_rate": round(hr_val, 0) if hr_val else None,
            "hr_zone": get_zone_for_hr(hr_val) if hr_val else "",
            "cadence_spm": round(cad_val, 0) if cad_val else None,
            "gct_ms": round(gct_val, 0) if gct_val else None,
            "vertical_osc_cm": round(vo_val, 1) if vo_val else None
        })

    # 路格數據評分 (Form Efficiency & Pacing Stability)
    cadence_grade = "良好 (≥180)" if avg_cadence and avg_cadence >= 180 else "偏低 (建議提步頻至 180+)"
    gct_grade = "菁英/優秀 (<220ms)" if avg_gct and avg_gct < 220 else ("正常 (220-250ms)" if avg_gct and avg_gct <= 250 else "偏長 (觸地過久)")

    return {
        "status": "success",
        "file_name": os.path.basename(file_path),
        "total_distance_km": round(total_dist, 2),
        "average_pace": avg_pace_str,
        "average_heart_rate": round(avg_hr, 0) if avg_hr else None,
        "max_heart_rate": round(max_hr, 0) if max_hr else None,
        "average_cadence_spm": round(avg_cadence, 0) if avg_cadence else None,
        "average_gct_ms": round(avg_gct, 0) if avg_gct else None,
        "average_vertical_osc_cm": round(avg_vo, 1) if avg_vo else None,
        "cadence_assessment": cadence_grade,
        "gct_assessment": gct_grade,
        "zone_distribution_pct": zone_percentages,
        "tags": tags,
        "total_laps": len(laps_detail),
        "laps": laps_detail,
        "raw_summary": summary_text
    }

def simulate_interval_plan(
    target_pace_str: str,
    intervals_count: int,
    interval_distance_m: int,
    rest_seconds: int,
    current_rpe: int = 5,
    weekly_mileage_km: float = 40.0
) -> Dict[str, Any]:
    """
    微調與預估間歇訓練計畫：
    根據 Edward 的生理參數與當前疲勞度，即時計算預估心率、TRIMP 負荷、
    心率漂移趨勢與路格/佩絲雙視角評定。
    """
    # 解析目標配速 (如 "4:30" -> 4.5 min/km)
    try:
        if ":" in str(target_pace_str):
            m, s = map(float, target_pace_str.split(":"))
            pace_num = m + s / 60.0
        else:
            pace_num = float(target_pace_str)
    except:
        pace_num = 5.0
        target_pace_str = "5:00"

    speed_kmh = 60.0 / pace_num if pace_num > 0 else 12.0
    interval_time_sec = (interval_distance_m / 1000.0) / speed_kmh * 3600.0
    total_work_dist_km = (intervals_count * interval_distance_m) / 1000.0
    total_session_time_min = (intervals_count * interval_time_sec + (intervals_count - 1) * rest_seconds) / 60.0

    # 預估心率攀升 (基于 Edward 210/53 基線)
    # 配速越快，起始心率基線越高；趟數越多，心率漂移 (Cardiac Drift) 越大
    # 5:00 配速約對應 Zone 3 高 (175 bpm)，4:30 約對應 Zone 4 (185 bpm)，4:00 約對應 Zone 5 (198 bpm)
    base_hr = 160 + (5.5 - pace_num) * 22
    base_hr = max(145.0, min(198.0, base_hr))

    # 計算各趟預估心率與漂移
    projected_laps = []
    hr_drift_per_lap = 1.8 + (current_rpe - 5) * 0.4 + (1.0 if rest_seconds < 90 else 0.0)
    
    zone_times_sec = {"Zone 1": 0.0, "Zone 2": 0.0, "Zone 3": 0.0, "Zone 4": 0.0, "Zone 5": 0.0}

    for i in range(1, intervals_count + 1):
        peak_hr = base_hr + (i - 1) * hr_drift_per_lap
        peak_hr = min(EDWARD_MAX_HR, peak_hr)
        avg_lap_hr = peak_hr - 5.0
        lap_zone = get_zone_for_hr(avg_lap_hr)

        # 累積區間時間
        if lap_zone in zone_times_sec:
            zone_times_sec[lap_zone] += interval_time_sec

        projected_laps.append({
            "interval": i,
            "target_pace": target_pace_str,
            "projected_avg_hr": round(avg_lap_hr, 1),
            "projected_peak_hr": round(peak_hr, 1),
            "expected_zone": lap_zone,
            "fatigue_index": round(min(10.0, current_rpe + (i / intervals_count) * 3.5), 1)
        })

    # TRIMP 負荷計算 (Banister Training Impulse)
    # TRIMP = D * (HR_ratio) * 0.64 * e^(1.92 * HR_ratio)
    mean_projected_hr = sum(l['projected_avg_hr'] for l in projected_laps) / intervals_count
    hr_ratio = (mean_projected_hr - EDWARD_REST_HR) / (EDWARD_MAX_HR - EDWARD_REST_HR)
    hr_ratio = max(0.1, min(0.99, hr_ratio))
    trimp = (total_work_dist_km * 6.0) * hr_ratio * 0.64 * math.exp(1.92 * hr_ratio)

    # 路格 (Luger) 量化診斷與警報
    max_projected_hr = max(l['projected_peak_hr'] for l in projected_laps)
    zone5_time_sec = zone_times_sec.get("Zone 5", 0.0)
    
    if max_projected_hr > 202 or zone5_time_sec > 480 or current_rpe >= 8:
        luger_alert = "🔴 紅燈警告：極度高負荷！心率預估衝破 202 bpm，乳酸將大量堆積引發姿勢代償，強烈反對加趟。"
        luger_recommendation = f"建議縮減為 {max(3, intervals_count - 2)} 趟，或將配速放寬 15 秒/公里。"
    elif max_projected_hr > 190 or trimp > 160:
        luger_alert = "🟡 黃燈提醒：強度偏高，已進入 LTHR (193 bpm) 臨界消耗區，需嚴格監控第 4 趟後之步頻維持度。"
        luger_recommendation = f"趟數可維持 {intervals_count} 趟，但建議休息秒數由 {rest_seconds}s 延長至 {rest_seconds + 30}s。"
    else:
        luger_alert = "🟢 綠燈通行：刺激適中，有助於提高有氧峰值與速耐力，心率漂移在安全控管範圍內。"
        luger_recommendation = f"維持 {intervals_count} 趟 x {interval_distance_m}m，目標配速 {target_pace_str} 執行。"

    # 佩絲 (Pace) 體感與恢復建議
    pace_recovery_hours = int(24 + (trimp / 10.0) * 1.8 + (current_rpe - 5) * 6)
    pace_recovery_hours = max(24, min(72, pace_recovery_hours))
    
    pace_advice = f"Edward，這份課表跑完後大約需要充足休息 {pace_recovery_hours} 小時。"
    if current_rpe >= 7:
        pace_advice += " 考量你最近體感較疲累，請注意補充電解質與充足睡眠；若開跑前熱身第 2 趟心率降不下來，請允許自己隨時喊停降速，不逞強才是頂級跑者的心態！"
    else:
        pace_advice += " 你的心理狀態很穩定！放鬆肩膀，把專注力放在呼吸節奏與重心前傾，享受加速時風吹過臉龐的快感吧！"

    return {
        "status": "success",
        "plan_summary": {
            "intervals_count": intervals_count,
            "interval_distance_m": interval_distance_m,
            "target_pace": target_pace_str,
            "rest_seconds": rest_seconds,
            "total_distance_km": round(total_work_dist_km, 2),
            "estimated_session_time_min": round(total_session_time_min, 1)
        },
        "load_metrics": {
            "trimp_score": round(trimp, 1),
            "projected_avg_hr": round(mean_projected_hr, 1),
            "projected_max_hr": round(max_projected_hr, 1),
            "zone_breakdown_minutes": {z: round(sec / 60.0, 1) for z, sec in zone_times_sec.items() if sec > 0}
        },
        "luger_assessment": {
            "alert": luger_alert,
            "recommendation": luger_recommendation
        },
        "pace_assessment": {
            "recovery_hours_needed": pace_recovery_hours,
            "psychological_advice": pace_advice
        },
        "chart_data": {
            "intervals": [l["interval"] for l in projected_laps],
            "projected_avg_hrs": [l["projected_avg_hr"] for l in projected_laps],
            "projected_peak_hrs": [l["projected_peak_hr"] for l in projected_laps],
            "fatigue_indexes": [l["fatigue_index"] for l in projected_laps]
        }
    }

def get_edward_full_profile() -> Dict[str, Any]:
    """獲取 Edward 專屬生理基線、跑姿標準與裝備知識"""
    manifest_path = os.path.join(PROJECT_ROOT, "data", "eddie_pioneer_manifest.json")
    manifest_data = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
        except:
            pass

    return {
        "runner_name": "Edward (艾迪的跑者夥伴)",
        "physiological_zones": {
            "max_heart_rate": EDWARD_MAX_HR,
            "rest_heart_rate": EDWARD_REST_HR,
            "lactate_threshold_heart_rate": EDWARD_LTHR,
            "zones_definition": EDWARD_HR_ZONES
        },
        "core_rules": [
            "FIT 檔案必須優先讀取 lap message，避免 record message 累積距離誤差",
            "Garmin 步頻半頻資料必須一律乘以 2 呈現為 SPM",
            "Zone 2 (148-163 bpm) 為路格神聖防線，嚴格禁止非計畫性心率飄移進入 Zone 3"
        ],
        "training_manifest": manifest_data
    }

def search_race_vault(query: str = "") -> List[Dict[str, Any]]:
    """檢索 data/knowledge 中的歷年大賽與歷史訓練檔案"""
    knowledge_dir = os.path.join(PROJECT_ROOT, "data", "knowledge")
    if not os.path.exists(knowledge_dir):
        return []

    files = os.listdir(knowledge_dir)
    results = []
    q_lower = query.lower()

    for f in sorted(files):
        if f.endswith(('.fit', '.xlsx', '.pdf', '.jpg')):
            if not query or q_lower in f.lower():
                full_p = os.path.join(knowledge_dir, f)
                sz = os.path.getsize(full_p)
                results.append({
                    "filename": f,
                    "size_bytes": sz,
                    "type": f.split('.')[-1].upper(),
                    "path": full_p
                })
    return results
