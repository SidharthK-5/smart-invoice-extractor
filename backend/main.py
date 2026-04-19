"""FastAPI entrypoint for Smart Invoice Extractor."""
from __future__ import annotations

import logging
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from models import (
    ExtractResponse,
    HealthResponse,
    Invoice,
    LineItem,
    TaxBreakdown,
)
from services.extraction import extract_invoice_data
from services.ocr import extract_text_from_image_bytes, extract_text_from_pdf_bytes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("smart-invoice-extractor")

app = FastAPI(title="Smart Invoice Extractor", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ocr_file(filename: str, content_type: str, data: bytes) -> str:
    if content_type == "application/pdf" or filename.lower().endswith(".pdf"):
        return extract_text_from_pdf_bytes(data)
    return extract_text_from_image_bytes(data)


def _build_invoice(filename: str, ocr_text: str, extracted: dict, error: str | None = None) -> Invoice:
    tb_data = extracted.get("tax_breakdown") or {}
    line_items = [LineItem(**li) for li in extracted.get("line_items", [])]
    return Invoice(
        filename=filename,
        vendor_name=extracted.get("vendor_name", ""),
        invoice_number=extracted.get("invoice_number", ""),
        invoice_date=extracted.get("invoice_date", ""),
        currency=extracted.get("currency", ""),
        order_number=extracted.get("order_number", ""),
        payment_method=extracted.get("payment_method", ""),
        vendor_gstin=extracted.get("vendor_gstin", ""),
        buyer_gstin=extracted.get("buyer_gstin", ""),
        delivery_address=extracted.get("delivery_address", ""),
        subtotal=extracted.get("subtotal"),
        discount_amount=extracted.get("discount_amount"),
        shipping_charges=extracted.get("shipping_charges"),
        processing_fees=extracted.get("processing_fees"),
        tax=extracted.get("tax"),
        tax_breakdown=TaxBreakdown(
            cgst=tb_data.get("cgst"),
            sgst=tb_data.get("sgst"),
            igst=tb_data.get("igst"),
        ),
        rounding_adjustment=extracted.get("rounding_adjustment"),
        total=extracted.get("total"),
        line_items=line_items,
        summary=extracted.get("summary", ""),
        raw_ocr_excerpt=(ocr_text or "")[:300],
        notes=extracted.get("notes", ""),
        error=error,
    )


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", gemini_configured=bool(settings.gemini_api_key))


@app.post("/api/extract", response_model=ExtractResponse)
async def extract(files: List[UploadFile] = File(...)) -> ExtractResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    invoices: List[Invoice] = []

    for upload in files:
        filename = upload.filename or "unknown"
        content_type = (upload.content_type or "").lower()

        if content_type and content_type not in settings.allowed_mime_types:
            invoices.append(
                _build_invoice(
                    filename,
                    "",
                    {"notes": f"Unsupported MIME type: {content_type}"},
                    error=f"Unsupported MIME type: {content_type}",
                )
            )
            continue

        try:
            data = await upload.read()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed reading upload %s", filename)
            invoices.append(
                _build_invoice(filename, "", {"notes": "Failed reading upload."}, error=str(exc))
            )
            continue
        finally:
            await upload.close()

        if len(data) > settings.max_upload_bytes:
            invoices.append(
                _build_invoice(
                    filename,
                    "",
                    {"notes": f"File exceeds {settings.max_upload_bytes} bytes."},
                    error="File too large.",
                )
            )
            continue

        ocr_text = ""
        try:
            ocr_text = _ocr_file(filename, content_type, data)
            print(f"OCR successful for {filename}. Extracted text length: {len(ocr_text)}")
            print(f"OCR excerpt for {filename}: {ocr_text[:]}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("OCR failed for %s", filename)
            invoices.append(
                _build_invoice(filename, "", {"notes": f"OCR failed: {exc}"}, error=f"OCR failed: {exc}")
            )
            continue

        try:
            extracted = extract_invoice_data(ocr_text)
            logger.info("Extraction successful for %s: %s", filename, extracted)
            print(f"Extraction successful for {filename}: {extracted}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Extraction failed for %s", filename)
            invoices.append(
                _build_invoice(
                    filename,
                    ocr_text,
                    {"notes": f"Extraction failed: {exc}"},
                    error=f"Extraction failed: {exc}",
                )
            )
            continue

        invoices.append(_build_invoice(filename, ocr_text, extracted))

    return ExtractResponse(invoices=invoices)
