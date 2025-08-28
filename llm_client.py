import os
import json
import re
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BA_MODEL = os.getenv("BA_MODEL", "gemini-1.5-flash")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def extract_json_from_text(text):
    """Extract JSON array from text, fallback safe parse."""
    match = re.search(r"(\[.*\])", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return []
    return []


def extract_modules(requirement_text: str):
    """Step 1: Extract modules/features from the requirement text."""
    prompt = f"""
You are a Business Analyst assistant.  
Extract a **list of modules/features** from the requirement text.  

Output JSON strictly in this format:
[
  {{ "module": "Login", "features": ["Login with email", "Login with OTP"] }},
  {{ "module": "Dashboard", "features": ["View metrics", "Export reports"] }}
]

Requirement:
{requirement_text}
"""
    model = genai.GenerativeModel(BA_MODEL)
    response = model.generate_content(prompt)
    text = response.text.strip()
    try:
        return json.loads(text)
    except:
        return extract_json_from_text(text)


def load_prompt():
    with open("prompts/ba_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()

def generate_stories(requirement_text: str, module_name: str, batch_size: int, custom_instruction: str = ""):
    base_prompt = load_prompt()
    prompt = f"""{base_prompt}

Generate exactly {batch_size} unique user stories for the module: "{module_name}".

Requirement Text:
{requirement_text}

Additional Instruction:
{custom_instruction}
"""
    model = genai.GenerativeModel(BA_MODEL)
    response = model.generate_content(prompt)
    text = response.text.strip()
    try:
        return json.loads(text)
    except:
        return extract_json_from_text(text)
