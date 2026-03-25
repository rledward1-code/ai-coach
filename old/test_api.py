import google.generativeai as genai
# 請在這裡填入您的 Key
genai.configure(api_key="你的_GEMINI_API_KEY")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)