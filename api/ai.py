import json
import os
from groq import Groq, APIError
from typing import List, Tuple, Dict
import re
from dotenv import load_dotenv


load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def _has_groq_key() -> bool:
  return bool(os.getenv("GROQ_API_KEY"))

def extract_tests_ai(text: str) -> Tuple[List[str], float]:
    """Use Groq API to extract tests, then validate against source text."""
    try:
        if not _has_groq_key():
            return [], 0.0

        
        prompt = (
            "You will be given raw medical report text. Extract only lab tests present in the text. "
            "Return strict JSON with key tests_raw as an array of human-readable strings matching the text, "
            "and confidence between 0 and 1. Do not invent tests. Examples: "
            "Hemoglobin 10.2 g/dL (Low), WBC 11200 /uL (High). "
            "JSON schema: {\"tests_raw\":[\"...\"],\"confidence\":0.0}. Return ONLY JSON."
        )

       
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            model="llama-3.3-70b-versatile"  
        )

        #
        resp_text = response.choices[0].message.content

        
        if resp_text.startswith("```"):
           
            resp_text = re.sub(r"^```(?:json)?\s*", "", resp_text)
            resp_text = re.sub(r"```$", "", resp_text)

        data = json.loads(resp_text or "{}")
        tests_raw = data.get("tests_raw") or []
        if not isinstance(tests_raw, list):
            return [], 0.0
        validated = _validate_tests_in_source(tests_raw, text)
        if not validated:
            return [], 0.0
        conf = float(data.get("confidence") or 0.0)
        conf = max(0.0, min(1.0, conf))
        return validated, conf

    except APIError as e:
        print("❌ Groq API error:", str(e))
        return [], 0.0
    except Exception as e:
        print("❌ Unexpected error in extract_tests_ai:", str(e))
        return [], 0.0


def summarize_with_ai(tests: List[Dict]) -> Dict:
    """Use Groq API to generate patient-friendly summary/explanations."""
    try:
        if not tests:
            return {"_used": False, "error": "no_tests"}
        if not _has_groq_key():
            return {"_used": False, "error": "missing_api_key"}

      
        compact = []
        for t in tests:
            name = t.get("name")
            value = t.get("value")
            unit = t.get("unit")
            status = t.get("status")
            ref = t.get("ref_range") or {}
            compact.append(
                f"{name}: {value} {unit} [{status}] ref({ref.get('low')}-{ref.get('high')})"
            )
        prompt = (
            "You will receive normalized lab tests. Create a concise patient-friendly summary that mentions all tests that are low/high, "
            "and provide 2-4 short, non-diagnostic explanations tailored to these tests (e.g., anemia for low hemoglobin). "
            "STRICT RULES: Never add any tests that are not in the list; never change values; do not diagnose. "
            "Return ONLY strict JSON: {\"summary\": string, \"explanations\": string[]}."
        )
        content = "\n".join(compact)

        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": content}
            ],
            model="llama-3.3-70b-versatile"
        )

        resp_text = response.choices[0].message.content
        if resp_text.startswith("```"):
            resp_text = re.sub(r"^```(?:json)?\s*", "", resp_text)
            resp_text = re.sub(r"```$", "", resp_text)

        data = json.loads(resp_text or "{}")
        out = {
            "summary": data.get("summary") or "",
            "explanations": data.get("explanations") or [],
            "_used": True,
        }
        if not isinstance(out["explanations"], list):
            out["explanations"] = []
        return out

    except APIError as e:
        return {"_used": False, "error": str(e)}
    except Exception as e:
        return {"_used": False, "error": str(e)}




