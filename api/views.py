from typing import Dict, List, Tuple
import re
from django.http import JsonResponse, HttpRequest
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .ai import extract_tests_ai, summarize_with_ai


def health(request: HttpRequest):
    return JsonResponse({"status": "ok","hello": "world"})


def _simple_ocr_text_cleanup(text: str) -> str:
    if not text:
        return ""
    fixes = {
        r"\bHemglobin\b": "Hemoglobin",
        r"\bHgh\b": "High",
        r"\bHg\b": "High",
        r"\bWBC\b": "WBC",
        r"\bCBC\b": "CBC",
        r"\b/uL\b": "/uL",
    }
    cleaned = text
    for pattern, repl in fixes.items():
        cleaned = re.sub(pattern, repl, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r",?\s*\(Low\)|,?\s*\(High\)|,?\s*\(Normal\)", lambda m: f" ({m.group(0).strip(' ,()')})", cleaned, flags=re.IGNORECASE)
    # Do not collapse newlines here; preserve structure for line parsing
    cleaned = re.sub(r"[\t\r]+", " ", cleaned)
    return cleaned


def _extract_tests_raw(text: str) -> Tuple[List[str], float]:
    if not text:
        return [], 0.0
    cleaned = _simple_ocr_text_cleanup(text)
    flat = re.sub(r"\s+", " ", cleaned).strip()

    candidates: List[str] = []
    patterns = [
        # Hemoglobin with optional colon
        r"Hemoglobin\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*g/?dL(?:\s*\((Low|High|Normal)\))?",
        # WBC or WBC Count with optional colon
        r"WBC(?:\s*Count)?\s*:?\s*([0-9,]+)\s*/?uL(?:\s*\((Low|High|Normal)\))?",
        # RBC Count in million/uL
        r"RBC(?:\s*Count)?\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:million)?\s*/?uL(?:\s*\((Low|High|Normal)\))?",
        # Platelet Count
        r"Platelet(?:\s*Count)?\s*:?\s*([0-9,]+)\s*/?uL(?:\s*\((Low|High|Normal)\))?",
        # Hematocrit %
        r"Hematocrit\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*%(?:\s*\((Low|High|Normal)\))?",
        # MCV fL
        r"MCV\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*fL(?:\s*\((Low|High|Normal)\))?",
        # MCH pg
        r"MCH\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*pg(?:\s*\((Low|High|Normal)\))?",
        # MCHC g/dL
        r"MCHC\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*g/?dL(?:\s*\((Low|High|Normal)\))?",
    ]
    for pat in patterns:
        for m in re.finditer(pat, flat, flags=re.IGNORECASE):
            start, end = m.span()
            snippet = flat[start:end]
            snippet = re.sub(r"\s+/uL", " /uL", snippet)
            if re.search(r"\b(WBC|Platelet)\b", snippet, flags=re.IGNORECASE):
                snippet = re.sub(r",", "", snippet)
            snippet = re.sub(r"\(low\)", "(Low)", snippet, flags=re.IGNORECASE)
            snippet = re.sub(r"\(high\)", "(High)", snippet, flags=re.IGNORECASE)
            snippet = re.sub(r"\(normal\)", "(Normal)", snippet, flags=re.IGNORECASE)
            candidates.append(snippet)

    # Line-based fallback for list items like "- Hemoglobin: 10.2 g/dL (Low)"
    if not candidates:
        for line in cleaned.split('\n'):
            s = line.strip(" -•\t")
            if not s:
                continue
            m = re.search(r"Hemoglobin\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*g/?dL(?:\s*\((Low|High|Normal)\))?", s, flags=re.IGNORECASE)
            if m:
                val = m.group(1)
                status_match = re.search(r"\((Low|High|Normal)\)", s, flags=re.IGNORECASE)
                status = f" ({status_match.group(1).capitalize()})" if status_match else ""
                candidates.append(f"Hemoglobin {val} g/dL{status}")
            m2 = re.search(r"WBC(?:\s*Count)?\s*:?\s*([0-9,]+)\s*/?uL(?:\s*\((Low|High|Normal)\))?", s, flags=re.IGNORECASE)
            if m2:
                val = m2.group(1).replace(',', '')
                status_match = re.search(r"\((Low|High|Normal)\)", s, flags=re.IGNORECASE)
                status = f" ({status_match.group(1).capitalize()})" if status_match else ""
                candidates.append(f"WBC {val} /uL{status}")
            m3 = re.search(r"RBC(?:\s*Count)?\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:million)?\s*/?uL(?:\s*\((Low|High|Normal)\))?", s, flags=re.IGNORECASE)
            if m3:
                val = m3.group(1)
                status_match = re.search(r"\((Low|High|Normal)\)", s, flags=re.IGNORECASE)
                status = f" ({status_match.group(1).capitalize()})" if status_match else ""
                candidates.append(f"RBC {val} million/uL{status}")
            m4 = re.search(r"Platelet(?:\s*Count)?\s*:?\s*([0-9,]+)\s*/?uL(?:\s*\((Low|High|Normal)\))?", s, flags=re.IGNORECASE)
            if m4:
                val = m4.group(1).replace(',', '')
                status_match = re.search(r"\((Low|High|Normal)\)", s, flags=re.IGNORECASE)
                status = f" ({status_match.group(1).capitalize()})" if status_match else ""
                candidates.append(f"Platelet {val} /uL{status}")
            m5 = re.search(r"Hematocrit\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*%(?:\s*\((Low|High|Normal)\))?", s, flags=re.IGNORECASE)
            if m5:
                val = m5.group(1)
                status_match = re.search(r"\((Low|High|Normal)\)", s, flags=re.IGNORECASE)
                status = f" ({status_match.group(1).capitalize()})" if status_match else ""
                candidates.append(f"Hematocrit {val} %{status}")
            m6 = re.search(r"MCV\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*fL(?:\s*\((Low|High|Normal)\))?", s, flags=re.IGNORECASE)
            if m6:
                val = m6.group(1)
                status_match = re.search(r"\((Low|High|Normal)\)", s, flags=re.IGNORECASE)
                status = f" ({status_match.group(1).capitalize()})" if status_match else ""
                candidates.append(f"MCV {val} fL{status}")
            m7 = re.search(r"MCH\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*pg(?:\s*\((Low|High|Normal)\))?", s, flags=re.IGNORECASE)
            if m7:
                val = m7.group(1)
                status_match = re.search(r"\((Low|High|Normal)\)", s, flags=re.IGNORECASE)
                status = f" ({status_match.group(1).capitalize()})" if status_match else ""
                candidates.append(f"MCH {val} pg{status}")
            m8 = re.search(r"MCHC\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*g/?dL(?:\s*\((Low|High|Normal)\))?", s, flags=re.IGNORECASE)
            if m8:
                val = m8.group(1)
                status_match = re.search(r"\((Low|High|Normal)\)", s, flags=re.IGNORECASE)
                status = f" ({status_match.group(1).capitalize()})" if status_match else ""
                candidates.append(f"MCHC {val} g/dL{status}")

    candidates = list(dict.fromkeys(candidates))
    confidence = 0.8 if candidates else 0.0
    return candidates, confidence


@csrf_exempt
def extract(request: HttpRequest):
    try:
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)

        # 1) Multipart with file upload: key 'image'
        if getattr(request, 'FILES', None) and request.FILES.get('image'):
            uploaded = request.FILES['image']
            try:
                # Lazy import so the app works without OCR deps
                from PIL import Image
                import pytesseract
                image = Image.open(uploaded)
                ocr_text = pytesseract.image_to_string(image)
                tests_raw, confidence = _extract_tests_raw(ocr_text)
                return JsonResponse({
                    "tests_raw": tests_raw,
                    "confidence": round(confidence, 2),
                    "source": "image_ocr"
                })
            except Exception as e:
                return JsonResponse({"error": "ocr_failed", "detail": str(e)}, status=400)

        # 2) JSON body with text or image_text strings
        payload = getattr(request, "body", b"") or b""
        try:
            import json
            data = json.loads(payload or b"{}")
        except Exception:
            data = {}

        text = (data.get("text") or "").strip()
        image_text = (data.get("image_text") or "").strip()
        # Always enable AI extraction merge (still guarded/validated against source text)
        use_ai = True
        source = text or image_text

        tests_raw, confidence = _extract_tests_raw(source)
        if use_ai:
            ai_raw, ai_conf = extract_tests_ai(source)
            if ai_raw:
                # Merge and dedupe
                merged = list(dict.fromkeys([*tests_raw, *ai_raw]))
                tests_raw = merged
                confidence = max(confidence, ai_conf)
        return JsonResponse({"tests_raw": tests_raw, "confidence": round(confidence, 2)})
    except Exception as e:
        return JsonResponse({"error": "server_error", "detail": str(e)}, status=500)


def _normalize_tests(tests_raw: List[str]) -> Tuple[List[Dict,], float]:
    normalized: List[Dict] = []
    for item in tests_raw:
        s = item.strip()

        m_hb = re.search(r"Hemoglobin\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*g/dL(?:\s*\((Low|High|Normal)\))?", s, flags=re.IGNORECASE)
        if m_hb:
            value = float(m_hb.group(1))
            status_match = re.search(r"\((Low|High|Normal)\)", s, flags=re.IGNORECASE)
            status = status_match.group(1).lower() if status_match else ("low" if value < 12.0 else ("high" if value > 15.0 else "normal"))
            normalized.append({
                "name": "Hemoglobin",
                "value": value,
                "unit": "g/dL",
                "status": status,
                "ref_range": {"low": 12.0, "high": 15.0},
            })
            continue

        m_wbc = re.search(r"WBC(?:\s*Count)?\s*:?\s*([0-9,]+)\s*/uL(?:\s*\((Low|High|Normal)\))?", s, flags=re.IGNORECASE)
        if m_wbc:
            value = float(m_wbc.group(1).replace(",", ""))
            status_match = re.search(r"\((Low|High|Normal)\)", s, flags=re.IGNORECASE)
            status = status_match.group(1).lower() if status_match else ("low" if value < 4000 else ("high" if value > 11000 else "normal"))
            normalized.append({
                "name": "WBC",
                "value": value,
                "unit": "/uL",
                "status": status,
                "ref_range": {"low": 4000, "high": 11000},
            })
            continue

        m_rbc = re.search(r"RBC(?:\s*Count)?\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:million)?\s*/uL(?:\s*\((Low|High|Normal)\))?", s, flags=re.IGNORECASE)
        if m_rbc:
            value_million = float(m_rbc.group(1))
            # Normalize to million/uL unit
            status_match = re.search(r"\((Low|High|Normal)\)", s, flags=re.IGNORECASE)
            status = status_match.group(1).lower() if status_match else ("low" if value_million < 4.5 else ("high" if value_million > 5.9 else "normal"))
            normalized.append({
                "name": "RBC",
                "value": value_million,
                "unit": "million/uL",
                "status": status,
                "ref_range": {"low": 4.5, "high": 5.9},
            })
            continue

        m_platelet = re.search(r"Platelet(?:\s*Count)?\s*:?\s*([0-9,]+)\s*/uL(?:\s*\((Low|High|Normal)\))?", s, flags=re.IGNORECASE)
        if m_platelet:
            value = float(m_platelet.group(1).replace(",", ""))
            status_match = re.search(r"\((Low|High|Normal)\)", s, flags=re.IGNORECASE)
            status = status_match.group(1).lower() if status_match else ("low" if value < 150000 else ("high" if value > 450000 else "normal"))
            normalized.append({
                "name": "Platelet Count",
                "value": value,
                "unit": "/uL",
                "status": status,
                "ref_range": {"low": 150000, "high": 450000},
            })
            continue

        m_hct = re.search(r"Hematocrit\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*%(?:\s*\((Low|High|Normal)\))?", s, flags=re.IGNORECASE)
        if m_hct:
            value = float(m_hct.group(1))
            status_match = re.search(r"\((Low|High|Normal)\)", s, flags=re.IGNORECASE)
            status = status_match.group(1).lower() if status_match else ("low" if value < 36 else ("high" if value > 46 else "normal"))
            normalized.append({
                "name": "Hematocrit",
                "value": value,
                "unit": "%",
                "status": status,
                "ref_range": {"low": 36, "high": 46},
            })
            continue

        m_mcv = re.search(r"MCV\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*fL(?:\s*\((Low|High|Normal)\))?", s, flags=re.IGNORECASE)
        if m_mcv:
            value = float(m_mcv.group(1))
            status_match = re.search(r"\((Low|High|Normal)\)", s, flags=re.IGNORECASE)
            status = status_match.group(1).lower() if status_match else ("low" if value < 80 else ("high" if value > 100 else "normal"))
            normalized.append({
                "name": "MCV",
                "value": value,
                "unit": "fL",
                "status": status,
                "ref_range": {"low": 80, "high": 100},
            })
            continue

        m_mch = re.search(r"MCH\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*pg(?:\s*\((Low|High|Normal)\))?", s, flags=re.IGNORECASE)
        if m_mch:
            value = float(m_mch.group(1))
            status_match = re.search(r"\((Low|High|Normal)\)", s, flags=re.IGNORECASE)
            status = status_match.group(1).lower() if status_match else ("low" if value < 27 else ("high" if value > 33 else "normal"))
            normalized.append({
                "name": "MCH",
                "value": value,
                "unit": "pg",
                "status": status,
                "ref_range": {"low": 27, "high": 33},
            })
            continue

        m_mchc = re.search(r"MCHC\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*g/dL(?:\s*\((Low|High|Normal)\))?", s, flags=re.IGNORECASE)
        if m_mchc:
            value = float(m_mchc.group(1))
            status_match = re.search(r"\((Low|High|Normal)\)", s, flags=re.IGNORECASE)
            status = status_match.group(1).lower() if status_match else ("low" if value < 32 else ("high" if value > 36 else "normal"))
            normalized.append({
                "name": "MCHC",
                "value": value,
                "unit": "g/dL",
                "status": status,
                "ref_range": {"low": 32, "high": 36},
            })
            continue

        # Generic fallback: pass through any validated test string as a generic item
        # Pattern: Name: value unit (Status)
        m_generic = re.search(
            r"^\s*([A-Za-z][A-Za-z \-\/]+?)\s*:?\s*([0-9]+(?:\.[0-9]+)?)\s*([%A-Za-z\/µ]+)?(?:\s*\((Low|High|Normal)\))?\s*$",
            s,
            flags=re.IGNORECASE,
        )
        if m_generic:
            name = m_generic.group(1).strip()
            try:
                value = float(m_generic.group(2))
            except Exception:
                value = None
            unit = (m_generic.group(3) or "").strip()
            status = (m_generic.group(4) or "unknown").lower()
            if value is not None:
                normalized.append({
                    "name": name,
                    "value": value,
                    "unit": unit,
                    "status": status,
                })
                continue

    confidence = 0.84 if normalized else 0.0
    return normalized, confidence


@csrf_exempt
def normalize(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        import json
        data = json.loads(request.body or b"{}")
    except Exception:
        data = {}
    tests_raw = data.get("tests_raw") or []
    if not isinstance(tests_raw, list):
        return JsonResponse({"error": "tests_raw must be a list"}, status=400)

    tests, conf = _normalize_tests(tests_raw)
    return JsonResponse({"tests": tests, "normalization_confidence": round(conf, 2)})


def _summarize_tests(tests: List[Dict]) -> Dict:
    highlights = []
    for t in tests:
        name = (t.get("name") or "").strip()
        status = (t.get("status") or "").strip().lower()
        if status in ("low", "high") and name:
            highlights.append(f"{status} {name.lower()}")

    if highlights:
        summary = ", ".join([h.capitalize() for h in highlights]) + "."
    else:
        summary = "No significant abnormalities detected."

    # Keep minimal rule-based explanations; AI may enrich later
    explanations: List[str] = []
    for t in tests:
        if t.get("name") == "Hemoglobin" and (t.get("status") == "low"):
            explanations.append("Low hemoglobin may relate to anemia.")
        if t.get("name") == "WBC" and (t.get("status") == "high"):
            explanations.append("High WBC can occur with infections.")

    return {"summary": summary, "explanations": explanations}


@csrf_exempt
def process(request: HttpRequest):
    try:
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)

        print("enetr process")    

        # Allow multipart image uploads too
        if getattr(request, 'FILES', None) and request.FILES.get('image'):
            uploaded = request.FILES['image']
            try:
                from PIL import Image
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
                print("tesseract_cmd", pytesseract.pytesseract.tesseract_cmd)
                print("entered here")
                image = Image.open(uploaded)
                ocr_text = pytesseract.image_to_string(image)
                print("ocr_text", ocr_text)
            except Exception as e:
                return JsonResponse({"status": "unprocessed", "reason": "ocr_failed", "detail": str(e)}, status=400)

            tests_raw, conf_extract = _extract_tests_raw(ocr_text)
            tests, conf_norm = _normalize_tests(tests_raw)
            if not tests:
                return JsonResponse({"status": "unprocessed", "reason": "no tests found"}, status=200)
            # Base summary from rules
            summ = _summarize_tests(tests)
            # Optional AI explanations that do not modify tests
            ai_out = summarize_with_ai(tests)
            if ai_out.get("_used") and ai_out.get("summary"):
                summ["summary"] = ai_out["summary"]
            if ai_out.get("_used") and ai_out.get("explanations"):
                summ["explanations"] = ai_out["explanations"]
            return JsonResponse({
                "tests": tests,
                "summary": summ.get("summary"),
                "explanations": summ.get("explanations"),
                "status": "ok",
                "meta": {
                    "confidence": round(conf_extract, 2),
                    "normalization_confidence": round(conf_norm, 2),
                    "ai_summary_used": bool(ai_out.get("_used")),
                    "ai_summary_error": ai_out.get("error")
                }
            })

        # JSON body workflow
        try:
            import json
            data = json.loads(request.body or b"{}")
        except Exception:
            data = {}

        text = (data.get("text") or "").strip()
        image_text = (data.get("image_text") or "").strip()
        # Always enable AI extraction merge (still guarded/validated against source text)
        use_ai = True
        source = text or image_text
        print("source", source)
        tests_raw, conf_extract = _extract_tests_raw(source)
        ai_extract_used = False
        if use_ai:
            print("use_ai", use_ai)
            print("entered use AI")
            ai_raw, ai_conf = extract_tests_ai(source)
            print("ai_raw", ai_raw)
            print("ai_conf", ai_conf)
            if ai_raw:
                tests_raw = list(dict.fromkeys([*tests_raw, *ai_raw]))
                conf_extract = max(conf_extract, ai_conf)
                ai_extract_used = True
        print("tests_raw", tests_raw)
        provided_tests_raw = data.get("tests_raw")
        if isinstance(provided_tests_raw, list) and provided_tests_raw:
            seen = set(tests_raw)
            for item in provided_tests_raw:
                if isinstance(item, str) and item.strip():
                    if item.strip() not in seen:
                        tests_raw.append(item.strip())
                        seen.add(item.strip())

        tests, conf_norm = _normalize_tests(tests_raw)
        print("tests", tests)
        if not tests:
            if provided_tests_raw:
                return JsonResponse({"status": "unprocessed", "reason": "hallucinated tests not present in input"}, status=400)
            return JsonResponse({"status": "unprocessed", "reason": "no tests found"}, status=200)

        summ = _summarize_tests(tests)
        ai_out = summarize_with_ai(tests)
        print("ai_out", ai_out)
        if ai_out.get("_used") and ai_out.get("summary"):
            summ["summary"] = ai_out["summary"]
        if ai_out.get("_used") and ai_out.get("explanations"):
            summ["explanations"] = ai_out["explanations"]

        return JsonResponse({
            "tests": tests,
            "summary": summ.get("summary"),
            "explanations": summ.get("explanations"),
            "status": "ok",
            "meta": {
                "confidence": round(conf_extract, 2),
                "normalization_confidence": round(conf_norm, 2),
                "ai_extract_used": ai_extract_used,
                "ai_summary_used": bool(ai_out.get("_used")),
                "ai_summary_error": ai_out.get("error")
            }
        })
    except Exception as e:
        return JsonResponse({"error": "server_error", "detail": str(e)}, status=500)


def ui(request: HttpRequest):
    return render(request, "api/index.html")
