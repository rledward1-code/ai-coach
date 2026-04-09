import google.generativeai as genai
from openai import OpenAI
import prompts
import random
import requests
import json

def _get_gemini_model(api_key):
    genai.configure(api_key=api_key.strip())
    available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    target = "models/gemini-1.5-flash"
    if target not in available:
        gemini_models = [m for m in available if "gemini" in m]
        target = gemini_models[0] if gemini_models else "models/gemini-pro"
    return genai.GenerativeModel(target)

def _call_ollama_utility(model_name, prompt):
    """使用 requests 直連 Ollama API (減少中間層延遲)"""
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 50,
            "top_k": 1,
            "top_p": 0.1
        },
        "keep_alive": "10m"
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            return resp.json().get("message", {}).get("content", "").strip()
        return ""
    except Exception as e:
        print(f"Ollama Utility Error: {e}")
        return ""

def determine_rounds(api_key, user_input, ai_engine="Cloud", ollama_model="gemma"):
    """使用 AI 判斷本輪對話應該幾輪討論 (1-3)"""
    prompt = prompts.ROUND_JUDGE_PROMPT.format(user_input=user_input)
    
    if ai_engine == "Local":
        result = _call_ollama_utility(ollama_model, prompt)
        try:
            rounds = int(result[0])
            return max(1, min(3, rounds))
        except: return 1

    try:
        model = _get_gemini_model(api_key)
        resp = model.generate_content(prompt)
        rounds = int(resp.text.strip()[0])
        return max(1, min(3, rounds))
    except:
        return 1

def determine_intent(api_key, user_input, has_data=False, ai_engine="Cloud", ollama_model="gemma"):
    """判斷使用者的意圖：CHAT / DATA / HISTORY"""
    prompt = prompts.INTENT_JUDGE_PROMPT.format(
        user_input=user_input, 
        has_data="是" if has_data else "否"
    )

    if ai_engine == "Local":
        result = _call_ollama_utility(ollama_model, prompt).upper()
        if "CHAT" in result: return "CHAT"
        if "HISTORY" in result: return "HISTORY"
        return "DATA"

    try:
        model = _get_gemini_model(api_key)
        resp = model.generate_content(prompt)
        text = resp.text.strip().upper()
        if "CHAT" in text: return "CHAT"
        if "HISTORY" in text: return "HISTORY"
        return "DATA"
    except:
        return "DATA" if has_data else "CHAT"

def determine_speakers(api_key, user_input, has_data=False, ai_engine="Cloud", ollama_model="gemma"):
    """判斷誰應該回應這條訊息。"""
    prompt = prompts.SPEAKER_JUDGE_PROMPT.format(
        user_input=user_input,
        has_data="是" if has_data else "否"
    )

    if ai_engine == "Local":
        result = _call_ollama_utility(ollama_model, prompt).lower()
        if "luger" in result and "both" not in result: return ["luger"]
        if "pace" in result and "both" not in result: return ["pace"]
        if "both_luger_first" in result: return ["luger", "pace"]
        return ["pace", "luger"]

    try:
        model = _get_gemini_model(api_key)
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

def determine_logic_combined(api_key, user_input, has_data=False, ai_engine="Cloud", ollama_model="gemma"):
    """
    合併判斷：一次決定意圖與發言者。這對於 4090 本機模式非常重要，可以減少一倍的預熱時間。
    """
    import json
    prompt = prompts.COMBINED_JUDGE_PROMPT.format(
        user_input=user_input,
        has_data="是" if has_data else "否"
    )

    if ai_engine == "Local":
        result_text = _call_ollama_utility(ollama_model, prompt)
        try:
            # 嘗試解析 JSON
            # 有時候模型會吐出 ```json ... ```，先清理一下
            if "```" in result_text:
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"): result_text = result_text[4:]
            
            data = json.loads(result_text.strip())
            intent = data.get("intent", "CHAT").upper()
            speaker_raw = data.get("speaker", "both_pace_first")
            
            if speaker_raw == "luger": speaker_order = ["luger"]
            elif speaker_raw == "pace": speaker_order = ["pace"]
            elif speaker_raw == "both_luger_first": speaker_order = ["luger", "pace"]
            else: speaker_order = ["pace", "luger"]
            
            return intent, speaker_order
        except:
            # 萬一 JSON 解析失敗，回傳保守預設值
            return "DATA" if has_data else "CHAT", ["pace", "luger"]

    # 雲端模式下，目前仍維持分開呼叫或在此也實作合併（為了同步優化）
    # 這裡為了簡單先用原本的邏輯合併
    intent = determine_intent(api_key, user_input, has_data)
    speaker_order = determine_speakers(api_key, user_input, has_data)
    return intent, speaker_order

def _stream_ollama(model_name, system_prompt, user_input, history=None):
    """使用 requests 直連 Ollama 串流 API"""
    url = "http://localhost:11434/api/chat"
    
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for msg in history:
            role = "assistant" if msg["role"] in ["model", "assistant"] else "user"
            messages.append({"role": role, "content": msg["content"]})
    
    messages.append({"role": "user", "content": user_input})
    
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": True,
        "keep_alive": "10m"
    }
    
    try:
        resp = requests.post(url, json=payload, stream=True, timeout=60)
        for line in resp.iter_lines():
            if line:
                chunk = json.loads(line)
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
                if chunk.get("done"):
                    break
    except Exception as e:
        yield f"Ollama 串流失敗: {str(e)}"

def stream_luger(api_key, history, user_profile, current_summary, global_history, user_input, prev_pace_response="", ai_engine="Cloud", ollama_model="gemma"):
    """路格回應。"""
    # 這裡進行大幅度精簡：從 30,000 降到 6,000，這對 Ollama 速度提升很大
    clean_summary = str(current_summary)[:6000] if current_summary else "目前無本次任務數據"
    gh_summary = str(global_history)[:6000] if global_history else "目前無長期歷史數據"

    system_prompt = prompts.LUGER_SYSTEM_PROMPT.format(
        user_profile=user_profile,
        global_history=gh_summary,
        clean_summary=clean_summary
    )

    if ai_engine == "Local":
        yield from _stream_ollama(ollama_model, system_prompt, user_input, history=history)
        return

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
            current_input += f"\n\n（你的同行教練佩絲剛才說：{prev_pace_response}  ——[系統強制指令]：這代表佩絲已經回答過了。請你不要再像鸚鵡一樣確認收到檔案或重述一次相同的數據結論！請直接給出截然不同的教練切入方向或反駁她。）"

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

def stream_pace(api_key, user_profile, luger_analysis, current_summary, global_history, user_input="", prev_luger_response="", history=None, ai_engine="Cloud", ollama_model="gemma"):
    """佩絲回應。"""
    # 同步精簡佩絲的數據負擔
    clean_summary = str(current_summary)[:6000] if current_summary else "目前無本次任務數據"
    gh_summary = str(global_history)[:6000] if global_history else "目前無長期歷史數據"

    system_content = prompts.PACE_SYSTEM_PROMPT.format(
        user_profile=user_profile,
        global_history=gh_summary,
        clean_summary=clean_summary
    )

    if ai_engine == "Local":
        # 組合當前上下文給佩絲
        full_input = user_input
        if luger_analysis:
            full_input = f"（路格剛才說：）{luger_analysis}\n\n{full_input}"
        
        yield from _stream_ollama(ollama_model, system_content, full_input, history=history)
        return

    try:
        client = OpenAI(api_key=api_key.strip())
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
            "content": f"[重要：跑者基本資訊 - {user_profile}]\n\nEdward 說：{user_input}\n\n[系統強制指令]：如果路格剛才已經講過（或確認收到數據、分析過某些數據），你絕對不要再說一次「我收到了」或是重複結論！請直接給予感性支持或不同的切入點來接續話題。"
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
