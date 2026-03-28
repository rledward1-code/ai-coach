import google.generativeai as genai
from openai import OpenAI
import prompts
import random

def _get_gemini_model(api_key):
    genai.configure(api_key=api_key.strip())
    available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = "models/gemini-1.5-flash"
    if target not in available:
        gemini_models = [m for m in available if "gemini" in m]
        target = gemini_models[0] if gemini_models else "models/gemini-pro"
    return genai.GenerativeModel(target)

def determine_rounds(api_key, user_input):
    """使用 Gemini 判斷本輪對話應該幾輪討論 (1-3)，失敗則用隨機備案"""
    try:
        model = _get_gemini_model(api_key)
        prompt = prompts.ROUND_JUDGE_PROMPT.format(user_input=user_input)
        resp = model.generate_content(prompt)
        rounds = int(resp.text.strip()[0])
        return max(1, min(3, rounds))
    except:
        if len(user_input) > 50:
            return random.choice([2, 3])
        return 1

def determine_speakers(api_key, user_input, has_data=False):
    """
    判斷誰應該回應這條訊息。
    返回 speaker order list，例如 ["luger", "pace"] 或 ["pace"] 或 ["luger"]
    """
    try:
        model = _get_gemini_model(api_key)
        prompt = prompts.SPEAKER_JUDGE_PROMPT.format(
            user_input=user_input,
            has_data="是" if has_data else "否"
        )
        resp = model.generate_content(prompt)
        result = resp.text.strip().lower().split()[0]
        
        if result == "luger":
            return ["luger"]
        elif result == "pace":
            return ["pace"]
        elif result == "both_luger_first":
            return ["luger", "pace"]
        else:  # both_pace_first or unknown
            return ["pace", "luger"]
    except:
        # 備案：有數據就路格先，否則佩絲先
        if has_data:
            return ["luger", "pace"]
        return ["pace", "luger"]

def stream_luger(api_key, history, user_profile, summary, user_input, prev_pace_response=""):
    """
    路格回應。prev_pace_response 是佩絲上一輪說的話（多輪對話使用）。
    """
    try:
        model = _get_gemini_model(api_key)
        clean_summary = str(summary)[:2000] if summary else "目前無數據"
        
        system_prompt = prompts.LUGER_SYSTEM_PROMPT.format(
            user_profile=user_profile,
            clean_summary=clean_summary
        )
        
        messages = [{"role": "user", "parts": [system_prompt]}]
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            messages.append({"role": role, "parts": [msg["content"]]})
        
        # 建構本輪的問題（可能包含佩絲上一輪的話）
        # 無論對話多長，永遠在最後提醒核心跑者資訊，避免 Gemini 在長對話後失憶
        profile_reminder = f"[重要：跑者基本資訊 - {user_profile}]"
        current_input = f"{profile_reminder}\n\n問題：{user_input}"
        if prev_pace_response:
            current_input += f"\n\n（佩絲剛才說：{prev_pace_response}  ——你有什麼要補充或反駁的嗎？）"
        messages.append({"role": "user", "parts": [current_input]})
        
        response = model.generate_content(messages, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text
                
    except Exception as e:
        yield f"路格診斷發生錯誤: {str(e)}"

def stream_pace(api_key, user_profile, luger_analysis, summary, user_input="", prev_luger_response=""):
    """
    佩絲回應。luger_analysis 是路格這輪說的話，prev_luger_response 是路格前幾輪說的（多輪使用）。
    """
    try:
        client = OpenAI(api_key=api_key.strip())
        clean_summary = str(summary)[:2000] if summary else "目前無數據"
        
        system_content = prompts.PACE_SYSTEM_PROMPT.format(
            user_profile=user_profile,
            clean_summary=clean_summary
        )
        
        # 建構對話訊息
        chat_messages = [{"role": "system", "content": system_content}]
        
        if prev_luger_response:
            chat_messages.append({"role": "assistant", "content": f"（路格之前說的）{prev_luger_response}"})
        
        chat_messages.append({"role": "assistant", "content": f"路格剛才說：{luger_analysis}"})
        chat_messages.append({"role": "user", "content": f"[重要：跑者基本資訊 - {user_profile}]\n\nEdward 說：{user_input}\n\n請根據對話自然地接話。"})
        
        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=chat_messages,
            stream=True
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"佩絲補充失敗: {str(e)}"
