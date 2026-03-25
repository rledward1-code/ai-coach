from openai import OpenAI

# 建議將 API Key 放在環境變數，但測試時先這樣是可以的
client = OpenAI(api_key="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")

response = client.chat.completions.create(
  model="gpt-4o",  # 改成這個
  messages=[
    {"role": "user", "content": "寫一首關於馬拉松 17K 撞牆期的三行詩"}
  ]
)

print(response.choices[0].message.content)