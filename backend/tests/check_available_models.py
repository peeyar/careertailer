import os
import google.generativeai as genai
from dotenv import load_dotenv

# 1. Load the environment variables
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ No API Key found in .env")
    exit()

# 2. Configure the SDK
genai.configure(api_key=api_key)

print(f"--- Available Models for your Key ---")

try:
    # 3. List models
    for m in genai.list_models():
        # We only care about models that can generate content (Chat models)
        if 'generateContent' in m.supported_generation_methods:
            print(f"Name: {m.name}")
            print(f"  - Display Name: {m.display_name}")
            print(f"  - Version: {m.version}")
            print("---")

except Exception as e:
    print(f"Error listing models: {e}")