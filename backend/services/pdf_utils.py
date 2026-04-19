"""PDF utilities — native text extraction + rasterization via pdf2image/poppler."""
from __future__ import annotations

import io
import logging
from typing import List

from PIL import Image
from pdf2image import convert_from_bytes
from pypdf import PdfReader

from config import settings

logger = logging.getLogger(__name__)


def extract_embedded_text(pdf_bytes: bytes) -> str:
    """Pull the embedded text layer from a PDF, if present.

    Digital PDFs (e.g. Amazon order summaries, Tally invoices, any
    print-to-PDF output) already contain the text — reading it directly
    avoids OCR errors entirely (no ₹→2 confusion, perfect numeric
    accuracy). Returns an empty string for scanned/photographed PDFs.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    parts: List[str] = []
    for i, page in enumerate(reader.pages):
        try:
            txt = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("Native text extraction failed on page %d: %s", i + 1, exc)
            txt = ""
        if txt.strip():
            parts.append(txt)
    return "\n\n".join(parts)


def pdf_bytes_to_images(pdf_bytes: bytes, dpi: int = 300) -> List[Image.Image]:
    """Convert PDF bytes to a list of PIL images, one per page.

    Requires poppler installed on the system. Set POPPLER_PATH env var on
    Windows if poppler is not on PATH.
    """
    kwargs = {"dpi": dpi}
    if settings.poppler_path:
        kwargs["poppler_path"] = settings.poppler_path
    return convert_from_bytes(pdf_bytes, **kwargs)
