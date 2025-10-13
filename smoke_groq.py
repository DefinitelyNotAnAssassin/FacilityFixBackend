from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()
key = os.getenv("GROQ_API_KEY")
model = os.getenv("GROQ_MODEL", "llama3-70b-8192")

print("Key present:", bool(key), "Model:", model)

client = Groq(api_key=key)
resp = client.chat.completions.create(
    model=model,
    messages=[
        {"role":"system","content":"Translate Tagalog to English. Return only English."},
        {"role":"user","content":"Tagalog: Sir, may tumutulo sa kisame sa CR. English:"}
    ],
    temperature=0.1,
    max_tokens=200
)
print("Output:", resp.choices[0].message.content.strip())
