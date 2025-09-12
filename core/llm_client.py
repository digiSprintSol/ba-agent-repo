import os
import json
import re
import google.generativeai as genai
from dotenv import load_dotenv
import json5 

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BA_MODEL = os.getenv("BA_MODEL", "gemini-2.0-flash")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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

# core/llm_client.py
import json, re

# Matches ```json ... ``` OR any [ ... ] block
_JSON_ARRAY_RE = re.compile(r"```json\s*(\[[\s\S]*?\])\s*```|(\[[\s\S]*\])", re.IGNORECASE)

def get_text(resp) -> str:
    """Safely extract text from Gemini response."""
    try:
        return (resp.text or "").strip()
    except Exception:
        # Older SDKs sometimes structure content differently
        try:
            return resp.candidates[0].content.parts[0].text.strip()
        except Exception:
            return ""


def extract_json_from_text(text: str):
    """
    Extracts a JSON object or array from a string that may contain
    extra text, markdown fences, or other non-JSON content.
    """
    if not text:
        return None

    # Use a regex to find the content between the first [ and last ]
    # or the first { and last }. This handles markdown fences and extra text.
    match = re.search(r'\[.*\]|\{.*\}', text, re.DOTALL)
    if not match:
        return None
    
    json_string = match.group(0)

    try:
        # Some models escape inner quotes, so we need to unescape them
        json_string = json_string.replace("\\'", "'").replace('\\"', '"')
        
        # Now, try to parse the cleaned string
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        # This will be triggered if the JSON is still invalid
        # The calling function will handle this failure
        return None

def get_text(response):
    # This function remains the same as it was
    try:
        return response.text
    except Exception:
        return ""

# The rest of your llm_client.py file
# (BA_MODEL, genai imports, etc., remain the same)