import google.generativeai as genai
from openai import OpenAI
import prompts  # 匯入獨立的人格檔案

def stream_luger(api_key, history, user_profile, summary, user_input):
    try:
        clean_key = api_key.strip()
        genai.configure(api_key=clean_key)
        
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target_model = "models/gemini-1.5-flash"
        if target_model not in available:
            gemini_models = [m for m in available if "gemini" in m]
            target_model = gemini_models[0] if gemini_models else "models/gemini-pro"
        
        model = genai.GenerativeModel(target_model)
        clean_summary = str(summary)[:600]
        
        # 關鍵修正點：變數名稱改為 system_prompt 並從 prompts 讀取
        system_prompt = prompts.LUGER_SYSTEM_PROMPT.format(
            user_profile=user_profile, 
            clean_summary=clean_summary
        )
        
        messages = [{"role": "user", "parts": [system_prompt]}]
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            messages.append({"role": role, "parts": [msg["content"]]})
        
        messages.append({"role": "user", "parts": [f"問題：{user_input}"]})
        
        response = model.generate_content(messages, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text
                
    except Exception as e:
        # 這裡會噴出具體的錯誤訊息，如 'system_prompt' is not defined
        yield f"路格診斷發生錯誤: {str(e)}"

def stream_pace(api_key, user_profile, luger_analysis, summary): # 增加 summary 參數
    try:
        client = OpenAI(api_key=api_key.strip())
        
        # 數據精簡：同樣只取前 600 字，確保精準度與速度
        clean_summary = str(summary)[:600]
        
        # 從 prompts.py 讀取內容，並注入數據
        system_content = prompts.PACE_SYSTEM_PROMPT.format(
            user_profile=user_profile,
            clean_summary=clean_summary  # 讓佩絲也能看到數據摘要
        )
        
        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "assistant", "content": f"路格分析結論: {luger_analysis}"},
                {"role": "user", "content": "請根據跑步數據與路格的觀點，給予人性化的挑戰與建議。"}
            ],
            stream=True
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"佩絲補充失敗: {str(e)}"
        
