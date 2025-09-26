# AI-Powered Medical Report Simplifier (Backend)

## Setup

```bash
# Windows PowerShell
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Optional OCR for images requires Tesseract installed system-wide. If you only pass recognized `image_text`, you can skip it.

## Endpoints

- `GET /api/health` → `{ "status": "ok" }`
- `POST /api/extract` → Input: `{ text?: string, image_text?: string }` → Output: `{ tests_raw: string[], confidence: number }`
  - Optional: `{ use_ai: true }` to enable Gemini fallback extraction.
- `POST /api/normalize` → Input: `{ tests_raw: string[] }` → Output: `{ tests: [...], normalization_confidence: number }`
- `POST /api/process` → Input: `{ text?: string, image_text?: string, tests_raw?: string[] }` → Output: combined final JSON with guardrails
  - Optional: `{ use_ai: true }` to enable Gemini fallback extraction.
  - If `GOOGLE_API_KEY` is set, the server will automatically try AI summarization for explanations/summary only (tests are never modified).

## Sample Requests

```bash
# Step 1 (text)
curl -s -X POST http://localhost:8000/api/extract -H "Content-Type: application/json" -d '{
  "text": "CBC: Hemoglobin 10.2 g/dL (Low), WBC 11,200 /uL (High)"
}' | jq

# Step 1 (ocr-sample)
curl -s -X POST http://localhost:8000/api/extract -H "Content-Type: application/json" -d '{
  "image_text": "CBC: Hemglobin 10.2 g/dL (Low) WBC 11200 /uL (Hgh)"
}' | jq

# Step 2
curl -s -X POST http://localhost:8000/api/normalize -H "Content-Type: application/json" -d '{
  "tests_raw": ["Hemoglobin 10.2 g/dL (Low)", "WBC 11200 /uL (High)"]
}' | jq

# Step 3+4
curl -s -X POST http://localhost:8000/api/process -H "Content-Type: application/json" -d '{
  "text": "CBC: Hemglobin 10.2 g/dL (Low) WBC 11200 /uL (Hgh)"
}' | jq
```

### Upload an image (multipart/form-data)

```bash
curl -s -X POST http://localhost:8000/api/extract \
  -F "image=@/absolute/path/to/report.jpg"
```

If Tesseract is installed, the backend will OCR the image and extract tests. Otherwise, install Tesseract or pre-run OCR and send `image_text` in JSON.

### Use AI fallback (Gemini)

Set `GOOGLE_API_KEY` in your environment, then pass `use_ai: true` in the JSON body. The backend validates AI results strictly against the original text and will return `status: unprocessed` if AI extracts tests not present in the source.

PowerShell example:

```powershell
$env:GOOGLE_API_KEY = "YOUR_KEY"
$body = @{ text = "CBC: Hemglobin 10.2 g/dL (Low) WBC 11200 /uL (Hgh)"; use_ai = $true } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:8000/api/process -Method Post -ContentType "application/json" -Body $body
```

## Notes

- Guardrail returns:
  - `{ "status": "unprocessed", "reason": "hallucinated tests not present in input" }` when tests are only in user overrides and not in the source.
  - `{ "status": "unprocessed", "reason": "no tests found" }` when nothing is extractable.

- This demo focuses on CBC subset (Hemoglobin, WBC). Extendable to more analytes with patterns and reference ranges.


