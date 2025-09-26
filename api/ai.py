import json
import os
from groq import Groq, APIError
from typing import List, Tuple, Dict
import re
from dotenv import load_dotenv
# Create a global client, so you reuse HTTP sessions etc.

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
print("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))
# print("DEBUG: GOOGLE_API_KEY =", os.getenv("GOOGLE_API_KEY"))
# print("DEBUG: GEMINI_MODEL =", os.getenv("GEMINI_MODEL"))
# import os
print("CWD:", os.getcwd())
print("Looking for .env at:", os.path.abspath(".env"))

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def _has_groq_key() -> bool:
    print("entered _has_groq_key")
    print("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))
    print("entered here")
    return bool(os.getenv("GROQ_API_KEY"))

def extract_tests_ai(text: str) -> Tuple[List[str], float]:
    """Use Groq API to extract tests, then validate against source text."""
    try:
        if not _has_groq_key():
            return [], 0.0

        # Construct prompt
        prompt = (
            "You will be given raw medical report text. Extract only lab tests present in the text. "
            "Return strict JSON with key tests_raw as an array of human-readable strings matching the text, "
            "and confidence between 0 and 1. Do not invent tests. Examples: "
            "Hemoglobin 10.2 g/dL (Low), WBC 11200 /uL (High). "
            "JSON schema: {\"tests_raw\":[\"...\"],\"confidence\":0.0}. Return ONLY JSON."
        )

        # For Groq, we use its chat completion interface
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            model="llama-3.3-70b-versatile"  # or whichever Groq model you prefer
        )

        # The response structure depends on the SDK. For example:
        resp_text = response.choices[0].message.content

        # Clean possible code fences
        if resp_text.startswith("```"):
            # remove triple backticks and optional "json"
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

        # Build compact representation
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


# import json
# import os
# import re
# from typing import List, Tuple, Dict
# from dotenv import load_dotenv
# import google.generativeai as genai
# import os

# load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
# print("DEBUG: GOOGLE_API_KEY =", os.getenv("GOOGLE_API_KEY"))
# print("DEBUG: GEMINI_MODEL =", os.getenv("GEMINI_MODEL"))
# import os
# print("CWD:", os.getcwd())
# print("Looking for .env at:", os.path.abspath(".env"))
# models = genai.list_models()

# print("Available models and their capabilities:")
# # for m in models:
# #     # Name of the model
# #     print(f"Name: {m.name}")
    
# #     # List the supported generation methods (chat, content, etc.)
# #     print(f"Supported generation methods: {m.supported_generation_methods}")
    
# #     # Optional description (if exists)
# #     description = getattr(m, "description", "No description")
# #     print(f"Description: {description}")
    
# #     print("-" * 40)
# # try:
# #     models = genai.list_models()
# #     if not models:
# #         print("No models found. Make sure your project has access to Generative AI models.")
# #     else:
# #         for m in models:
# #             print(m["name"], m.get("capabilities", []))
# # except Exception as e:
# #     print("Error calling ListModels:", e)

# def _has_api_key() -> bool:
#     print("entered _has_api_key")
#     print("GOOGLE_API_KEY", os.environ.get("GOOGLE_API_KEY"))
#     print("entere here")
#     return bool(os.environ.get("GOOGLE_API_KEY"))
# # def _get_gemini_model():
#     import google.generativeai as genai
#     genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
#     # Honor explicit env override first
#     preferred = os.environ.get("GEMINI_MODEL")
#     # First, discover accessible models that support generateContent
#     try:
#         models = genai.list_models()
#         usable = [
#             m for m in models
#             if getattr(m, "name", "").startswith("models/gemini-")
#             and "generateContent" in getattr(m, "supported_generation_methods", [])
#         ]
#     except Exception:
#         usable = []

#     # Build candidate IDs by preference
#     candidates: List[str] = []
#     if preferred:
#         candidates.append(preferred)
#     # Favor 1.5 flash/pro if present
#     for key in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.5-flash-latest", "gemini-1.5-pro-latest", "gemini-1.0-pro"]:
#         candidates.append(key)
#     # Finally append any discovered names stripped of the 'models/' prefix
#     for m in usable:
#         name = getattr(m, "name", "")
#         if name.startswith("models/"):
#             candidates.append(name.split("/", 1)[1])

#     # Try in order and return the first that works
#     seen: set = set()
#     last_err = None
#     for mid in candidates:
#         if not mid or mid in seen:
#             continue
#         seen.add(mid)
#         try:
#             return genai.GenerativeModel(mid)
#         except Exception as e:
#             last_err = e
#             continue
#     raise last_err if last_err else RuntimeError("No Gemini model available for generateContent")

# # def _get_gemini_model():
# #     print("entered _get_gemini_model")
# #     import google.generativeai as genai
# #     genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
# #     model_id = os.environ.get("GEMINI_MODEL", "gemini-1.5")
# #     print("model_id", model_id)
# #     print("genai.GenerativeModel(model_id)", genai.GenerativeModel(model_id))
# #     return genai.GenerativeModel(model_id)/
# def _get_gemini_model():
#     models = genai.list_models()

#     # Pick the first model whose name contains 'gemini' and supports 'generateContent'
#     selected_model = next(
#         (m for m in models 
#          if "generateContent" in m.supported_generation_methods and "gemini" in m.name),
#         None
#     )

#     if not selected_model:
#         raise ValueError("No model available that supports generateContent")

#     print("Selected model:", selected_model.name)
#     return genai.GenerativeModel(selected_model.name)

# def _clean_source(text: str) -> str:
#     cleaned = re.sub(r"\s+", " ", text or "").strip()
#     return cleaned


# def _validate_tests_in_source(tests_raw: List[str], source: str) -> List[str]:
#     if not source:
#         return []
#     canon = _clean_source(source).lower()
#     valid: List[str] = []
#     for t in tests_raw or []:
#         s = _clean_source(str(t))
#         # Accept if exact or name token appears with a number pattern in source
#         # Basic heuristic to avoid hallucinations
#         name_match = re.match(r"([A-Za-z ]+)", s)
#         has_number = bool(re.search(r"\d", s))
#         name = name_match.group(1).strip().lower() if name_match else ""
#         if has_number and (s.lower() in canon or (name and name in canon)):
#             valid.append(s)
#     # de-duplicate preserving order
#     seen = set()
#     result = []
#     for it in valid:
#         if it not in seen:
#             seen.add(it)
#             result.append(it)
#     return result


# def extract_tests_ai(text: str) -> Tuple[List[str], float]:
#     """Attempt to extract tests via Gemini, then validate strictly against source text.
#     Returns (tests_raw, confidence). On failure or missing API key, returns ([], 0.0).
#     """
#     try:
#         print("entered extract_tests_ai")
#         if not _has_api_key():
#             print("No API key found")
#             return [], 0.0

#         model = _get_gemini_model()
#         prompt = (
#             "You will be given raw medical report text. Extract only lab tests present in the text. "
#             "Return strict JSON with key tests_raw as an array of human-readable strings matching the text, "
#             "and confidence between 0 and 1. Do not invent tests. Examples: "
#             "Hemoglobin 10.2 g/dL (Low), WBC 11200 /uL (High). "
#             "JSON schema: {\"tests_raw\":[\"...\"],\"confidence\":0.0}. Return ONLY JSON."
#         )
#         content = f"REPORT:\n{text}"
#         resp = model.generate_content([prompt, content])
#         raw = resp.text or "{}"
#         data = json.loads(raw)
#         tests_raw = data.get("tests_raw") or []
#         if not isinstance(tests_raw, list):
#             return [], 0.0
#         validated = _validate_tests_in_source(tests_raw, text)
#         if not validated:
#             return [], 0.0
#         conf = float(data.get("confidence") or 0.0)
#         conf = max(0.0, min(1.0, conf))
#         return validated, conf
#     except Exception as e:
#         # print("error in extract_tests_ai")
#         # return [], 0.0
#         print("❌ Gemini API error:", str(e))
#         import traceback; traceback.print_exc()


# def summarize_with_ai(tests: List[Dict]) -> Dict:
#     """Generate patient-friendly summary/explanations from already-normalized tests.
#     Never invent new tests; only describe what is present.
#     Returns {summary: str, explanations: [str]} or {} if API missing/fails.
#     """
#     try:
#         if not tests:
#             return {"_used": False, "error": "no_tests"}
#         if not _has_api_key():
#             return {"_used": False, "error": "missing_api_key"}

#         model = _get_gemini_model()

#         compact = []
#         for t in tests:
#             name = t.get("name")
#             value = t.get("value")
#             unit = t.get("unit")
#             status = t.get("status")
#             ref = t.get("ref_range") or {}
#             compact.append(f"{name}: {value} {unit} [{status}] ref({ref.get('low')}-{ref.get('high')})")

#         prompt = (
#             "You will receive normalized lab tests. Create a concise patient-friendly summary that mentions all tests that are low/high, "
#             "and provide 2-4 short, non-diagnostic explanations tailored to these tests (e.g., anemia for low hemoglobin). "
#             "STRICT RULES: Never add any tests that are not in the list; never change values; do not diagnose. "
#             "Return ONLY strict JSON: {\"summary\": string, \"explanations\": string[]}."
#         )
#         content = "\n".join(compact)
#         resp = model.generate_content([prompt, content])
#         raw = resp.text or "{}"
#         data = json.loads(raw)
#         out = {
#             "summary": data.get("summary") or "",
#             "explanations": data.get("explanations") or [],
#             "_used": True,
#         }
#         if not isinstance(out["explanations"], list):
#             out["explanations"] = []
#         return out
#     except Exception as e:
#         return {"_used": False, "error": str(e)}

# # import json
# # import os
# # from typing import List, Dict, Any
# # import google.generativeai as genai

# # REFERENCE_PATH = os.path.join(os.path.dirname(__file__), "reference_ranges.json")
# # with open(REFERENCE_PATH, "r") as f:
# #     REFERENCE_DB = json.load(f)

# # def _get_gemini_model():
# #     genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
# #     for name in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro", "gemini-1.0-pro-001"]:
# #         try:
# #             return genai.GenerativeModel(name)
# #         except Exception:
# #             continue
# #     return None

# # def normalize_test_names(tests_raw: List[str]) -> List[Dict[str, Any]]:
# #     """Use AI to normalize test names (Hb -> Hemoglobin, etc.)."""
# #     model = _get_gemini_model()
# #     if not model:
# #         return [{"raw": t, "standard": t} for t in tests_raw]

# #     prompt = f"""
# #     Map the following medical test strings into standard medical names.
# #     Respond strictly in JSON with format:
# #     [{{"raw": "Hb", "standard": "Hemoglobin"}}, ...]

# #     Input: {tests_raw}
# #     """
# #     try:
# #         resp = model.generate_content(prompt)
# #         return json.loads(resp.text)
# #     except Exception:
# #         return [{"raw": t, "standard": t} for t in tests_raw]

# # def summarize_with_ai(tests: List[Dict[str, Any]]) -> Dict[str, Any]:
# #     model = _get_gemini_model()
# #     if not model:
# #         return {"summary": None, "explanations": []}

# #     prompt = f"""
# #     Given the following lab test results:
# #     {tests}

# #     Create a short patient-friendly summary highlighting abnormal values.
# #     Also provide 2–4 simple explanations in bullet points.
# #     Return valid JSON like:
# #     {{
# #       "summary": "Low hemoglobin and high WBC observed.",
# #       "explanations": [
# #         "Low hemoglobin may suggest anemia.",
# #         "High WBC can indicate infection."
# #       ]
# #     }}
# #     """
# #     try:
# #         resp = model.generate_content(prompt)
# #         return json.loads(resp.text)
# #     except Exception:
# #         return {"summary": None, "explanations": []}

