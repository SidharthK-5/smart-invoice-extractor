# Smart Invoice Extractor

An end-to-end invoice intelligence service that ingests PDF or image invoices,
runs a hybrid OCR + text-layer extraction pipeline, and uses a large language
model to return a fully structured, finance-ready data model. The application
ships with a responsive web console for uploading invoices, reviewing the
extracted fields, and exporting the results as a multi-sheet Excel workbook for
downstream accounting or ERP integration.

The system is built with a clear separation between the OCR layer, the
structured-extraction layer, and the presentation layer, which makes each
component independently testable and replaceable — you can swap the OCR engine,
upgrade the LLM, or rebuild the UI without touching the rest of the stack.

---

## Capabilities

- **Multi-format ingestion** — PDF (digital or scanned), PNG, JPEG.
- **Hybrid text-extraction pipeline** — embedded text layer (fast, lossless) is
  preferred; Tesseract OCR with image preprocessing is used as a fallback for
  scanned or photographed invoices.
- **Structured extraction** — vendor identity, invoice metadata, payment
  details, tax breakdown (CGST / SGST / IGST), line items with HSN and tax
  rate, shipping and processing charges, rounding adjustments, and a
  human-readable summary.
- **Resilient LLM client** — automatic retry with exponential backoff and
  jitter, honouring `Retry-After` / `retryDelay` for 429 and 5xx responses.
- **Model flexibility** — supports both Google Gemini and Gemma models via the
  same REST endpoint; the client auto-detects the model family and adjusts
  request options accordingly.
- **Multi-invoice handling** — documents that bundle multiple invoices
  (e.g. marketplace orders that include both a customer invoice and a
  commission invoice) are disambiguated so that only the customer-facing
  invoice is returned.
- **Excel export** — a two-sheet workbook (`Invoice Summary`,
  `Invoice Line Items`) with normalized columns, eliminating the ambiguity of
  a denormalized CSV.
- **Operational readiness** — health endpoint, structured logging, configurable
  upload limits and MIME-type allow-list, Dockerised backend, and a single-file
  Render Blueprint for one-click deployment.

---

## Architecture

```text
                                     ┌──────────────────────┐
                                     │   Browser (React)    │
                                     │  Upload • Review •   │
                                     │   Excel export       │
                                     └──────────┬───────────┘
                                                │ multipart/form-data
                                                ▼
                                     ┌──────────────────────┐
                                     │   FastAPI service    │
                                     │  CORS • validation   │
                                     │  size & MIME gates   │
                                     └──────────┬───────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    ▼                           ▼                           ▼
         ┌────────────────────┐      ┌────────────────────┐      ┌────────────────────┐
         │   Text extractor   │      │   OCR pipeline     │      │   LLM extractor    │
         │   (pypdf)          │      │   (Tesseract)      │      │   (Gemini / Gemma) │
         │ Embedded-text fast │ ---> │ Preprocess → OCR   │ ---> │ Prompted JSON      │
         │ path for digital   │      │ fallback for       │      │ extraction with    │
         │ PDFs               │      │ scans / images     │      │ retry & backoff    │
         └────────────────────┘      └────────────────────┘      └─────────┬──────────┘
                                                                           │
                                                                           ▼
                                                            ┌──────────────────────────┐
                                                            │   Pydantic response      │
                                                            │   model → JSON → UI      │
                                                            └──────────────────────────┘
```

### Request lifecycle

1. **Ingress** — the client uploads one or more files. The API validates
   MIME type and enforces `MAX_UPLOAD_BYTES`.
2. **Text acquisition** — for PDFs, the service first attempts to read the
   embedded text layer with `pypdf`. If the extracted text is below a minimum
   threshold (i.e. the document is scanned or photographed), the pipeline
   falls back to Tesseract OCR. Images always use the OCR path.
3. **OCR preprocessing** — EXIF-based orientation correction, LANCZOS
   upscaling to a minimum width, unsharp masking, and adaptive contrast are
   applied before Tesseract is invoked with tuned PSM / OEM settings.
4. **Structured extraction** — the cleaned text is sent to the configured
   LLM with a strict, schema-driven prompt. The model returns a JSON object
   which is validated, normalised, and post-processed (tax breakdown
   reconciliation, currency propagation, total consolidation).
5. **Response** — the API returns a typed `ExtractResponse` with one
   `Invoice` per uploaded file. Errors are captured per-file so a single bad
   upload never fails the batch.

---

## Technology stack

| Layer       | Choice                                                 |
| ----------- | ------------------------------------------------------ |
| Backend API | FastAPI, Uvicorn, Pydantic                             |
| OCR         | Tesseract (via `pytesseract`), Pillow preprocessing    |
| PDF parsing | `pypdf` (text layer), `pdf2image` + Poppler (rasterise)|
| LLM client  | `httpx`, Google Generative Language REST API           |
| Default LLM | `gemma-3-27b-it` (Gemini-compatible endpoint)          |
| Frontend    | React 18, TypeScript, Vite                             |
| UI          | Lucide icons, custom CSS design system                 |
| Export      | SheetJS (`xlsx`) — multi-sheet `.xlsx`                 |
| Packaging   | Docker (backend), static bundle (frontend)             |
| Deployment  | Render Blueprint (`render.yaml`)                       |

---

## Extracted data model

Each processed invoice returns the following fields (optional fields are
omitted when not detected):

**Identity & metadata** — `filename`, `vendor_name`, `invoice_number`,
`invoice_date`, `currency`, `order_number`, `payment_method`, `vendor_gstin`,
`buyer_gstin`, `delivery_address`.

**Financials** — `subtotal`, `discount_amount`, `shipping_charges`,
`processing_fees`, `tax`, `tax_breakdown` (`cgst`, `sgst`, `igst`),
`rounding_adjustment`, `total` (final amount payable).

**Line items** — array of `{ description, quantity, unit_price, line_total,
hsn_code, tax_rate }`.

**Narrative & diagnostics** — `summary` (human-readable one-liner),
`raw_ocr_excerpt` (first 300 characters of the source text), `notes`
(parser observations), `error` (per-file error if extraction failed).

---

## Prerequisites

- Python 3.10 or higher
- Node.js 18 or higher
- Tesseract OCR
  - macOS: `brew install tesseract`
  - Debian / Ubuntu: `sudo apt-get install tesseract-ocr`
  - Windows: [UB-Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki)
- Poppler (required by `pdf2image`)
  - macOS: `brew install poppler`
  - Debian / Ubuntu: `sudo apt-get install poppler-utils`
  - Windows: download Poppler binaries and set `POPPLER_PATH`
- A Google Generative Language API key (Gemini or Gemma).

---

## Local development

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate              # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env                  # populate GEMINI_API_KEY
uvicorn main:app --reload             # http://localhost:8000
```

Health check:

```bash
curl http://localhost:8000/api/health
```

### Frontend

```bash
cd frontend
npm install
npm run dev                           # http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://localhost:8000`, so no CORS
configuration is required in development.

---

## Configuration

All backend configuration is environment-driven. See `backend/.env.example`
for the canonical list.

| Variable            | Required | Default                                                      | Description                                                                 |
| ------------------- | -------- | ------------------------------------------------------------ | --------------------------------------------------------------------------- |
| `GEMINI_API_KEY`    | Yes      | —                                                            | Google Generative Language API key.                                         |
| `GEMINI_MODEL`      | No       | `gemma-3-27b-it`                                             | Any Gemini or Gemma model id. Gemma omits `responseMimeType` automatically. |
| `GEMINI_ENDPOINT`   | No       | `https://generativelanguage.googleapis.com/v1beta/models`    | Override the base URL (e.g. for a proxy).                                   |
| `TESSERACT_CMD`     | No       | resolved from `PATH`                                         | Absolute path to the Tesseract binary when not on `PATH`.                   |
| `POPPLER_PATH`      | No       | resolved from `PATH`                                         | Path to Poppler `bin/` (primarily Windows).                                 |
| `MAX_UPLOAD_BYTES`  | No       | `10485760` (10 MB)                                           | Per-file upload size ceiling.                                               |
| `CORS_ORIGINS`      | No       | `http://localhost:5173,http://127.0.0.1:5173`                | Comma-separated list of allowed origins.                                    |

The frontend reads `VITE_API_BASE` at build time. Leave it empty in
development (the dev proxy handles routing); set it to the deployed API
origin in production.

---

## API reference

### `GET /api/health`

Returns a lightweight readiness probe.

```json
{ "status": "ok", "gemini_configured": true }
```

### `POST /api/extract`

`multipart/form-data` upload with one or more `files`. Returns an
`ExtractResponse` containing one `Invoice` per uploaded file.

```json
{
  "invoices": [
    {
      "filename": "acme-march.pdf",
      "vendor_name": "ACME Supplies Pvt. Ltd.",
      "invoice_number": "INV-12345",
      "invoice_date": "2024-03-01",
      "currency": "INR",
      "order_number": "ORD-98765",
      "payment_method": "UPI",
      "vendor_gstin": "27AABCA1234A1Z5",
      "buyer_gstin": "29AAACB9876B1Z2",
      "delivery_address": "…",
      "subtotal": 1000.0,
      "discount_amount": 50.0,
      "shipping_charges": 40.0,
      "processing_fees": null,
      "tax": 171.0,
      "tax_breakdown": { "cgst": 85.5, "sgst": 85.5, "igst": null },
      "rounding_adjustment": -0.5,
      "total": 1161.0,
      "line_items": [
        {
          "description": "Widget A",
          "quantity": 2,
          "unit_price": 500.0,
          "line_total": 1000.0,
          "hsn_code": "8471",
          "tax_rate": 18.0
        }
      ],
      "summary": "Two Widget A units billed to ACME Supplies on 1 March 2024.",
      "raw_ocr_excerpt": "…",
      "notes": "",
      "error": null
    }
  ]
}
```

Per-file failures are non-fatal: the offending entry is returned with an
`error` field populated, and the remaining invoices are processed normally.

---

## Excel export

The web console exports results as a `.xlsx` workbook with two normalized
sheets:

- **Invoice Summary** — one row per invoice with all header-level fields
  (vendor, dates, tax breakdown, totals, payment details, summary).
- **Invoice Line Items** — one row per line item, joined back to the parent
  invoice by `filename` + `invoice_number` + `vendor_name`.

This normalization avoids the classic denormalized-CSV pitfall in which
invoice-level totals are repeated across every line-item row.

---

## Deployment

The repository ships with production-ready Docker and Render configuration.

### Render (one-click Blueprint)

1. Push the repository to GitHub.
2. In the Render dashboard, **New → Blueprint** and connect the repo.
   Render will detect `render.yaml` and provision both services.
3. After the initial deploy, populate the three synced variables:
   - `GEMINI_API_KEY` on the API service
   - `CORS_ORIGINS` on the API service (the deployed web origin)
   - `VITE_API_BASE` on the web service (the deployed API origin)
4. Trigger a manual redeploy of the web service so the Vite build embeds
   the updated API base URL.

### Docker (backend)

```bash
cd backend
docker build -t invoice-extractor-api .
docker run --rm -p 8000:8000 -e GEMINI_API_KEY=... invoice-extractor-api
```

The image includes Tesseract and Poppler, so no additional system setup is
required on the host.

---

## Project layout

```text
backend/
  main.py                 FastAPI app, /api/extract, /api/health
  config.py               environment-backed settings
  models.py               Pydantic request / response schemas
  services/
    ocr.py                Tesseract wrapper with preprocessing
    pdf_utils.py          pdf2image helper
    extraction.py         prompt, LLM client, retry, post-processing
  Dockerfile              Python 3.11 + Tesseract + Poppler
  requirements.txt
  .env.example

frontend/
  src/
    App.tsx               top-level page
    api.ts                fetch wrapper
    types.ts              shared TypeScript types
    components/
      UploadForm.tsx      drag-and-drop uploader
      InvoiceTable.tsx    expandable results table
      SummaryTiles.tsx    dashboard tiles
    utils/
      excel.ts            multi-sheet Excel export (SheetJS)
  vite.config.ts          dev-time /api proxy

render.yaml               Render Blueprint (API + static web)
```

---

## Extensibility

### Replacing the OCR engine

`backend/services/ocr.py` exposes `extract_text_from_image_bytes` and
`extract_text_from_pdf_bytes`. Any alternative engine (PaddleOCR, AWS Textract,
Google Document AI) can be dropped in by re-implementing these two functions —
no other module depends on Tesseract directly.

### Adjusting the extraction schema

The authoritative prompt lives in `backend/services/extraction.py` as
`INVOICE_EXTRACTION_PROMPT`. Extending it requires three coordinated edits:

1. Update the prompt to request the new field.
2. Add the field to `models.py` (Pydantic) and `frontend/src/types.ts`
   (TypeScript).
3. Surface the field in `InvoiceTable.tsx` or `excel.ts` as appropriate.

### Switching models

Set `GEMINI_MODEL` to any supported model id (for example
`gemini-2.0-flash`, `gemini-1.5-pro`, `gemma-3-27b-it`). The LLM client
detects Gemma models and omits `responseMimeType` automatically, since that
option is Gemini-specific.

---

## Operational notes

- **Rate limits** — free-tier quotas on the Generative Language API are
  modest. The client retries up to four times with jittered exponential
  backoff, but persistent 429s indicate you should move to a higher-quota
  tier or a paid model.
- **Cold starts** — on Render's free web-service tier the API sleeps after
  15 minutes of inactivity. Warm it with a `GET /api/health` before a demo
  or a scheduled job if latency on the first request matters.
- **Secrets** — `GEMINI_API_KEY` is a server-side secret. It is never sent
  to the browser; all LLM calls originate from the API service.
