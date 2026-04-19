"""LLM extraction service — calls Gemini and parses structured JSON.

The prompt is exposed as INVOICE_EXTRACTION_PROMPT so it's easy to tweak
during the hackathon.
"""
from __future__ import annotations

import json
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

# Retry tuning for Gemini 429 / 503. Free tier is ~15 RPM / 1500 RPD so a
# short burst of uploads can easily hit the per-minute cap; waiting and
# retrying is usually enough to get through.
_MAX_RETRIES = 4
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_DEFAULT_BACKOFF_SECONDS = 2.0
_MAX_BACKOFF_SECONDS = 30.0


# ---------------------------------------------------------------------------
# Prompt — edit this to iterate on extraction quality.
# ---------------------------------------------------------------------------
INVOICE_EXTRACTION_PROMPT = """You are an invoice parsing engine. Your ONLY job is to
read raw OCR / PDF text of an invoice and output a single valid JSON object
that conforms EXACTLY to the schema below. Do not include any explanation,
prose, code fences, or markdown — output raw JSON only.

Schema:
{
  "vendor_name": string,                 // seller / merchant name
  "invoice_number": string,              // invoice / tax-invoice number
  "order_number": string,                // order / reference number if distinct from invoice_number
  "invoice_date": string,                // ISO YYYY-MM-DD where possible
  "currency": string,                    // ISO code if detectable (INR, USD, EUR); else ""
  "payment_method": string,              // e.g. "Mastercard ending 8012", "UPI", "COD"
  "vendor_gstin": string,                // seller GSTIN (India) if present
  "buyer_gstin": string,                 // buyer GSTIN if present
  "delivery_address": string,            // ship-to address if different from billing; else ""

  "subtotal": number | null,             // pre-tax / pre-discount item total
  "discount_amount": number | null,      // combined discounts (bank offer + coupon + promo); positive number
  "shipping_charges": number | null,     // delivery / shipping fee
  "processing_fees": number | null,      // offer processing / convenience / platform fee
  "tax": number | null,                  // total tax (sum of all tax lines)
  "tax_breakdown": {                     // Indian GST split, if available
    "cgst": number | null,
    "sgst": number | null,
    "igst": number | null
  },
  "rounding_adjustment": number | null,  // round-off line; may be positive or negative
  "total": number | null,                // FINAL amount paid/payable after all discounts, fees, shipping, tax

  "line_items": [
    {
      "description": string,
      "quantity": number | null,
      "unit_price": number | null,
      "line_total": number | null,
      "hsn_code": string,                // Indian HSN/SAC code if shown
      "tax_rate": number | null          // tax rate as a percent, e.g. 18 for 18%
    }
  ],

  "summary": string,                     // 1–2 sentence human summary: vendor, key items, price breakdown, payment
  "notes": string                        // parse issues, ambiguities, missing fields
}

Multi-invoice rule (IMPORTANT):
- Documents sometimes contain TWO invoices stitched together: (A) the
  customer-facing product / tax invoice from the seller, and (B) a
  marketplace / platform / commission / seller-service fees invoice
  (e.g. Amazon Seller Services Pvt. Ltd., Flipkart Internet Pvt. Ltd.
  charging commission to the seller).
- Extract ONLY (A), the customer product invoice. Completely IGNORE (B) —
  do not include its vendor, its line items, or its totals. Signals of (B):
  heading mentions "marketplace / platform fees", "commission", "seller
  services", "fulfillment fees", or the "billed to" party is the same
  seller as the "billed from".

General rules:
- Output JSON ONLY. No prose, no backticks, no markdown.
- Use null for missing numeric fields, "" for missing strings.
- Strip currency symbols and thousands separators from numbers; keep signs
  (e.g. a discount line showing "-100.00" means discount_amount = 100).
- `total` is always the FINAL amount the customer paid/pays after every
  discount, offer, bank offer, shipping charge, processing fee, tax, and
  rounding have been applied. If the invoice shows "Total" and "Grand Total"
  as separate values, use the Grand Total (the final payable amount).
- `summary` should read naturally, e.g.: "OnePlus Bullets Wireless Z3 from
  Cocoblu Retail on Amazon — subtotal ₹1,299, ₹9 processing fee, ₹100 bank
  discount, paid ₹1,208 via Mastercard ending 8012 on 15 Jan 2026."
- If text is garbled or clearly not an invoice, return the schema with
  empty / null fields and explain briefly in `notes`.

OCR / PDF TEXT:
<<<
{ocr_text}
>>>
"""


def _empty_result(notes: str) -> Dict[str, Any]:
    return {
        "vendor_name": "",
        "invoice_number": "",
        "order_number": "",
        "invoice_date": "",
        "currency": "",
        "payment_method": "",
        "vendor_gstin": "",
        "buyer_gstin": "",
        "delivery_address": "",
        "subtotal": None,
        "discount_amount": None,
        "shipping_charges": None,
        "processing_fees": None,
        "tax": None,
        "tax_breakdown": {"cgst": None, "sgst": None, "igst": None},
        "rounding_adjustment": None,
        "total": None,
        "line_items": [],
        "summary": "",
        "notes": notes,
    }


def _parse_number(value: Any) -> Optional[float]:
    """Parse a value into float — strips currency symbols, commas, whitespace."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"[^\d\.\-]", "", value.replace(",", ""))
    if cleaned in ("", "-", ".", "-."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_json_blob(text: str) -> Optional[str]:
    """Pull out the first {...} JSON blob even if the model wrapped it in fences."""
    if not text:
        return None
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1)
    # Greedy curly match from first { to last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return None


def _parse_retry_delay(resp: httpx.Response) -> Optional[float]:
    """Best-effort extraction of Gemini's suggested retry delay (seconds).

    Honors the standard Retry-After header first, then Gemini's RetryInfo
    detail in the JSON error body (`error.details[].retryDelay = "Ns"`).
    """
    retry_after = resp.headers.get("Retry-After")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass

    try:
        body = resp.json()
    except ValueError:
        return None

    details = (body.get("error") or {}).get("details") or []
    for detail in details:
        delay = detail.get("retryDelay")
        if isinstance(delay, str) and delay.endswith("s"):
            try:
                return float(delay[:-1])
            except ValueError:
                continue
    return None


def _call_gemini(prompt: str) -> str:
    """POST to Gemini generateContent with retry + backoff on 429/5xx."""
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    url = f"{settings.gemini_endpoint}/{settings.gemini_model}:generateContent"
    generation_config: Dict[str, Any] = {"temperature": 0.1}
    # responseMimeType is Gemini-only; Gemma rejects it with a 400.
    if settings.gemini_model.lower().startswith("gemini"):
        generation_config["responseMimeType"] = "application/json"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": settings.gemini_api_key,
    }

    last_error: Optional[Exception] = None
    with httpx.Client(timeout=60.0) as client:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = client.post(url, json=payload, headers=headers)
            except httpx.RequestError as exc:
                last_error = exc
                if attempt == _MAX_RETRIES:
                    raise
                sleep_s = min(
                    _DEFAULT_BACKOFF_SECONDS * (2 ** (attempt - 1)),
                    _MAX_BACKOFF_SECONDS,
                )
                logger.warning(
                    "Gemini network error (attempt %d/%d): %s — retrying in %.1fs",
                    attempt, _MAX_RETRIES, exc, sleep_s,
                )
                time.sleep(sleep_s)
                continue

            if resp.status_code in _RETRYABLE_STATUSES and attempt < _MAX_RETRIES:
                suggested = _parse_retry_delay(resp)
                backoff = _DEFAULT_BACKOFF_SECONDS * (2 ** (attempt - 1))
                # Full jitter on the computed backoff; API suggestion wins when present.
                sleep_s = suggested if suggested is not None else backoff * (0.5 + random.random() / 2)
                sleep_s = min(sleep_s, _MAX_BACKOFF_SECONDS)
                logger.warning(
                    "Gemini %d (attempt %d/%d) — sleeping %.1fs before retry",
                    resp.status_code, attempt, _MAX_RETRIES, sleep_s,
                )
                time.sleep(sleep_s)
                continue

            resp.raise_for_status()
            data = resp.json()
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError, TypeError) as exc:
                logger.error("Unexpected Gemini response shape: %s", data)
                raise RuntimeError(f"Unexpected Gemini response: {exc}") from exc

    # Exhausted retries without a usable response.
    raise RuntimeError(
        f"Gemini request failed after {_MAX_RETRIES} attempts: {last_error}"
    )


def _normalize_line_items(raw_items: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "description": str(item.get("description") or "").strip(),
                "quantity": _parse_number(item.get("quantity")),
                "unit_price": _parse_number(item.get("unit_price")),
                "line_total": _parse_number(item.get("line_total")),
                "hsn_code": str(item.get("hsn_code") or "").strip(),
                "tax_rate": _parse_number(item.get("tax_rate")),
            }
        )
    return normalized


def _normalize_tax_breakdown(raw: Any) -> Dict[str, Optional[float]]:
    if not isinstance(raw, dict):
        return {"cgst": None, "sgst": None, "igst": None}
    return {
        "cgst": _parse_number(raw.get("cgst")),
        "sgst": _parse_number(raw.get("sgst")),
        "igst": _parse_number(raw.get("igst")),
    }


def _post_process(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize numeric/string fields and return the canonical dict."""
    line_items = _normalize_line_items(parsed.get("line_items"))
    subtotal = _parse_number(parsed.get("subtotal"))
    discount_amount = _parse_number(parsed.get("discount_amount"))
    shipping_charges = _parse_number(parsed.get("shipping_charges"))
    processing_fees = _parse_number(parsed.get("processing_fees"))
    tax = _parse_number(parsed.get("tax"))
    tax_breakdown = _normalize_tax_breakdown(parsed.get("tax_breakdown"))
    rounding_adjustment = _parse_number(parsed.get("rounding_adjustment"))
    # `total` is the single canonical final payable — if the model returned a
    # distinct `grand_total`, prefer that since it's always the post-discount
    # final figure on consumer invoices.
    total = _parse_number(parsed.get("grand_total"))
    if total is None:
        total = _parse_number(parsed.get("total"))

    return {
        "vendor_name": str(parsed.get("vendor_name") or "").strip(),
        "invoice_number": str(parsed.get("invoice_number") or "").strip(),
        "order_number": str(parsed.get("order_number") or "").strip(),
        "invoice_date": str(parsed.get("invoice_date") or "").strip(),
        "currency": str(parsed.get("currency") or "").strip(),
        "payment_method": str(parsed.get("payment_method") or "").strip(),
        "vendor_gstin": str(parsed.get("vendor_gstin") or "").strip(),
        "buyer_gstin": str(parsed.get("buyer_gstin") or "").strip(),
        "delivery_address": str(parsed.get("delivery_address") or "").strip(),
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "shipping_charges": shipping_charges,
        "processing_fees": processing_fees,
        "tax": tax,
        "tax_breakdown": tax_breakdown,
        "rounding_adjustment": rounding_adjustment,
        "total": total,
        "line_items": line_items,
        "summary": str(parsed.get("summary") or "").strip(),
        "notes": str(parsed.get("notes") or "").strip(),
    }


def extract_invoice_data(ocr_text: str) -> Dict[str, Any]:
    """Run Gemini on OCR text and return a normalized dict.

    Never raises — returns a minimal object with `notes` describing the
    failure if anything goes wrong.
    """
    if not ocr_text or not ocr_text.strip():
        return _post_process(_empty_result("No OCR text to process."))

    prompt = INVOICE_EXTRACTION_PROMPT.replace("{ocr_text}", ocr_text)

    try:
        raw_text = _call_gemini(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gemini call failed")
        return _post_process(_empty_result(f"LLM call failed: {exc}"))

    blob = _extract_json_blob(raw_text)
    if not blob:
        logger.error("Could not locate JSON in Gemini response: %s", raw_text[:500])
        return _post_process(_empty_result("LLM did not return JSON."))

    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError as exc:
        logger.error("JSON parse failed: %s | raw=%s", exc, raw_text[:500])
        return _post_process(_empty_result(f"JSON parse failed: {exc}"))

    if not isinstance(parsed, dict):
        return _post_process(_empty_result("LLM returned non-object JSON."))

    return _post_process(parsed)
