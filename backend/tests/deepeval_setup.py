import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from deepeval.models.base_model import DeepEvalBaseLLM
from langchain_google_genai import ChatGoogleGenerativeAI

# --- THE FIX ---
# 1. Get the folder where THIS file lives (backend/tests)
current_dir = Path(__file__).resolve().parent

# 2. Go up one level to the backend root (backend/)
backend_root = current_dir.parent

# 3. Point explicitly to the .env file
env_path = backend_root / ".env"

print(f"DEBUG: Looking for .env at: {env_path}")

# 4. Load it!
load_dotenv(dotenv_path=env_path)
# ----------------

# DEBUGGING
google_key = os.getenv("GOOGLE_API_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")
final_key = google_key or gemini_key

print(f"DEBUG: GOOGLE_API_KEY found? {'Yes' if google_key else 'No'}")
print(f"DEBUG: GEMINI_API_KEY found? {'Yes' if gemini_key else 'No'}")

if not final_key:
    print("❌ CRITICAL ERROR: Still no API Key.")
    print(f"   PLEASE VERIFY: Does a file exist at {env_path}?")
    print("   Run 'ls -a' in your terminal to be sure.")
    sys.exit(1)

class GeminiJudge(DeepEvalBaseLLM):
    def __init__(self):
        self.model = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
            google_api_key=final_key,
            temperature=0
        )

    def load_model(self):
        return self.model

    def generate(self, prompt: str) -> str:
        return self.model.invoke(prompt).content

    async def a_generate(self, prompt: str) -> str:
        response = await self.model.ainvoke(prompt)
        return response.content

    def get_model_name(self):
        return "gemini-2.5-pro"