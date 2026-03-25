import google.generativeai as genai
import time

# 設定你的 Key
genai.configure(api_key="AIzaSyAz4zvoZpfqRYPTgfYlaqBkR4dl23NPu54")

try:
    print("🚀 啟動 Luger 3.0 深度掃描模式...")
    
    # 1. 將 MIME type 改為 text/plain 進行偽裝
    myfile = genai.upload_file(
        path="activity.fit",
        mime_type="text/plain" 
    )
    print(f"✅ 數據已封包，ID: {myfile.name}")

    # 2. 檢查狀態
    while myfile.state.name == "PROCESSING":
        print("⚡", end="", flush=True)
        time.sleep(2)
        myfile = genai.get_file(myfile.name)

    print("\n🧠 Luger 3.0 正在暴力破解數據結構...")

    # 3. 呼叫模型
    model = genai.GenerativeModel("gemini-3-flash-preview")
    
    # 在提示詞中加入更多引導
    prompt = """
    你現在是數據教練 Luger。
    附件是一個 Garmin 跑錶產出的 .fit 數據。
    請直接解析二進位內容，找出這場比賽第 17 公里的區段數據：
    1. 平均功率 (Average Power)
    2. 觸地時間 (Ground Contact Time)
    3. 步幅 (Stride Length)
    
    最後請以 Luger 的口吻，對 17K 數據的衰退給出一句極其嚴厲的分析。
    """
    
    response = model.generate_content([myfile, prompt])

    print("\n--- 🏁 Luger 診斷結果 ---")
    print(response.text)

except Exception as e:
    print(f"\n❌ 解析失敗: {e}")