# Smart Invoice Extractor

A 24-hour hackathon MVP: upload invoice PDFs/images, and the app uses
open-source OCR (Tesseract) + Google Gemini to extract vendor, dates, totals,
and line items. The UI displays the results in a table and lets you download
a flattened CSV.

## Stack

- **Backend**: Python 3, FastAPI, `pytesseract`, `pdf2image`, `httpx`
- **Frontend**: Vite + React + TypeScript
- **LLM**: Google Gemini / Gemma via REST. Default is `gemma-3-27b-it` (generous free-tier quota, no billing required). Override with `GEMINI_MODEL`.

## Prerequisites

System-level binaries:

- **Tesseract OCR** — `brew install tesseract` (macOS) /
  `apt-get install tesseract-ocr` (Ubuntu) /
  [download for Windows](https://github.com/UB-Mannheim/tesseract/wiki)
- **Poppler** (needed by `pdf2image`) — `brew install poppler` /
  `apt-get install poppler-utils` / Windows: download and set `POPPLER_PATH`
- **Python 3.10+**, **Node 18+**

A Google Gemini API key (`GEMINI_API_KEY`).

## Backend

The venv lives inside the backend so the folder is a self-contained deployable unit.

```bash
cd backend
python3 -m venv venv              # macOS arm64: /opt/homebrew/bin/python3.12 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env              # then edit .env and paste your key
# or export inline:
export GEMINI_API_KEY=...

uvicorn main:app --reload         # http://localhost:8000
```

> **Deployment note:** `venv/` is gitignored — do **not** commit it. macOS wheels
> (especially on Apple Silicon) won't run on Linux build servers. Deployment
> platforms (Vercel, Railway, Fly, Docker, etc.) install from `requirements.txt`
> at build time.

Health check: `curl http://localhost:8000/api/health`.

Env vars supported (see `backend/.env.example`):

- `GEMINI_API_KEY` (required)
- `GEMINI_MODEL` (default `gemma-3-27b-it`; also works with any Gemini model id like `gemini-2.0-flash`. Note: the code auto-detects Gemma and omits `responseMimeType` since Gemma rejects it.)
- `TESSERACT_CMD` — path to tesseract binary if not on `PATH`
- `POPPLER_PATH` — poppler `bin/` dir if not on `PATH` (mostly Windows)
- `CORS_ORIGINS` — comma-separated origins, default
  `http://localhost:5173,http://127.0.0.1:5173`
- `MAX_UPLOAD_BYTES` — default `10485760` (10 MB)

## Frontend

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://localhost:8000`, so no CORS
dance needed during development.

## API

`POST /api/extract` — `multipart/form-data` with one or more `files`. Returns:

```json
{
  "invoices": [
    {
      "filename": "invoice1.pdf",
      "vendor_name": "ACME Supplies",
      "invoice_number": "INV-12345",
      "invoice_date": "2024-03-01",
      "currency": "INR",
      "subtotal": 1000.0,
      "tax": 180.0,
      "total": 1180.0,
      "validation": { "line_items_sum": 1000.0, "totals_match": true },
      "line_items": [
        { "description": "Item A", "quantity": 2, "unit_price": 500.0, "line_total": 1000.0 }
      ],
      "raw_ocr_excerpt": "first 300 chars of OCR text",
      "notes": ""
    }
  ]
}
```

`GET /api/health` — returns `{ "status": "ok", "gemini_configured": true }`.

## Project layout

```text
backend/
  main.py               FastAPI app + /api/extract, /api/health
  config.py             env-backed settings
  models.py             Pydantic request/response models
  services/
    ocr.py              Tesseract wrapper (swap to PaddleOCR here)
    pdf_utils.py        pdf2image helper
    extraction.py       Gemini call + prompt + post-processing
  requirements.txt
  .env.example

frontend/
  src/
    App.tsx             top-level page
    api.ts              fetch helper
    types.ts            shared types
    components/
      UploadForm.tsx
      InvoiceTable.tsx
    utils/csv.ts        flatten invoices -> CSV + browser download
  vite.config.ts        /api proxy to :8000
```

## Tweaking the LLM prompt

The prompt lives in `backend/services/extraction.py` as
`INVOICE_EXTRACTION_PROMPT`. Edit it in place to iterate on extraction
quality during the hackathon.

## Swapping OCR engines

`services/ocr.py` exposes `ocr_image`, `extract_text_from_image_bytes`, and
`extract_text_from_pdf_bytes`. To swap in PaddleOCR (or anything else),
replace those implementations — nothing else in the codebase depends on
Tesseract directly.
