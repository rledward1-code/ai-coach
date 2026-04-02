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
    """使用 Gemini 判斷本輪對話應該幾輪討論 (1-3)，失敗一律返回 1"""
    try:
        model = _get_gemini_model(api_key)
        prompt = prompts.ROUND_JUDGE_PROMPT.format(user_input=user_input)
        resp = model.generate_content(prompt)
        rounds = int(resp.text.strip()[0])
        return max(1, min(3, rounds))
    except:
        return 1  # 失敗時保守返回 1 輪，避免重複

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

def stream_luger(api_key, history, user_profile, current_summary, global_history, user_input, prev_pace_response=""):
    """路格回應。"""
    try:
        genai.configure(api_key=api_key.strip())
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = "models/gemini-1.5-flash"
        if target not in available:
            gemini_models = [m for m in available if "gemini" in m]
            target = gemini_models[0] if gemini_models else "models/gemini-pro"

        # 設定安全過濾門檻為最低，避免跑步數據誤觸
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        clean_summary = str(current_summary)[:2000] if current_summary else "目前無本次任務數據"
        gh_summary = str(global_history)[:2000] if global_history else "目前無長期歷史數據"

        system_prompt = prompts.LUGER_SYSTEM_PROMPT.format(
            user_profile=user_profile,
            global_history=gh_summary,
            clean_summary=clean_summary
        )

        # 使用 system_instruction 避免 Gemini 的 user/model 交替限制
        model = genai.GenerativeModel(
            target, 
            system_instruction=system_prompt,
            safety_settings=safety_settings
        )

        # 確保 history 嚴格交替 user/model，避免 InvalidArgument
        messages = []
        last_role = None
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            if role == last_role:
                # 合併相鄰同角色的訊息
                messages[-1]["parts"][0] += "\n\n" + msg["content"]
            else:
                messages.append({"role": role, "parts": [msg["content"]]})
                last_role = role

        profile_reminder = f"[重要：跑者基本資訊 - {user_profile}]"
        current_input = f"{profile_reminder}\n\n問題：{user_input}"
        if prev_pace_response:
            current_input += f"\n\n（佩絲剛才說：{prev_pace_response}  ——你有什麼要補充或反駁的嗎？）"

        # 如果 history 最後是 user，合併進去；否則新增一條
        # 這樣可以防止連續 user 訊息（round 2+ 時 history 最後常是 user）
        if messages and messages[-1]["role"] == "user":
            messages[-1]["parts"][0] += "\n\n" + current_input
        else:
            messages.append({"role": "user", "parts": [current_input]})

        response = model.generate_content(messages, stream=True)
        for chunk in response:
            try:
                # 檢查是否有被安全擋住
                if chunk.candidates[0].finish_reason == 3: # SAFETY
                    yield "⚠️ [路格提示：此段對話內容因安全機制被攔截，請嘗試調整問題詞彙]"
                    break
                if chunk.text:
                    yield chunk.text
            except Exception:
                # 如果快取存取失敗（例如 finish_reason=1/3），跳過此次輸出
                continue

    except Exception as e:
        yield f"路格診斷發生錯誤: {str(e)}"

def stream_pace(api_key, user_profile, luger_analysis, current_summary, global_history, user_input="", prev_luger_response="", history=None):
    """佩絲回應。"""
    try:
        client = OpenAI(api_key=api_key.strip())
        clean_summary = str(current_summary)[:2000] if current_summary else "目前無本次任務數據"
        gh_summary = str(global_history)[:2000] if global_history else "目前無長期歷史數據"

        system_content = prompts.PACE_SYSTEM_PROMPT.format(
            user_profile=user_profile,
            global_history=gh_summary,
            clean_summary=clean_summary
        )

        chat_messages = [{"role": "system", "content": system_content}]

        # 注入過去對話記錄
        # 關鍵：路格的回應必須用 user 角色包裝，而非 assistant！
        # OpenAI 的 assistant 角色 = 佩絲自己說的話，若用 assistant 注入路格的話，
        # GPT 會以為那些都是「佩絲說的」，進而開始扮演路格（雙重人格）
        if history:
            for msg in history:
                chat_messages.append({"role": msg["role"], "content": msg["content"]})

        # 本輪當前訊息
        if luger_analysis:
            chat_messages.append({"role": "user", "content": f"（路格剛才說：）{luger_analysis}"})

        chat_messages.append({
            "role": "user",
            "content": f"[重要：跑者基本資訊 - {user_profile}]\n\nEdward 說：{user_input}\n\n請根據對話自然地接話。"
        })

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
