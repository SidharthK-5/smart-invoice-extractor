"""OCR service — encapsulates Tesseract so we can swap in PaddleOCR later.

Public API:
    ocr_image(image) -> str
    extract_text_from_pdf_bytes(pdf_bytes) -> str
    extract_text_from_image_bytes(image_bytes) -> str
"""
from __future__ import annotations

import io
import logging
from typing import List

import pytesseract
from PIL import Image, ImageFilter, ImageOps

from config import settings
from services.pdf_utils import extract_embedded_text, pdf_bytes_to_images

logger = logging.getLogger(__name__)

if settings.tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


# Tesseract performs best around ~300 DPI. For photographed documents the
# rendered page may be small — upscale so short text isn't ~10px tall.
_MIN_WIDTH_PX = 1800

_TESSERACT_LANG = "eng"

# --oem 1  : LSTM-only engine — more accurate than the auto/legacy hybrid,
#            and importantly recognizes modern glyphs like ₹ properly.
# --psm 6  : assume a single uniform block of text (good default for invoices).
# preserve_interword_spaces : keep column alignment so tables stay readable.
# user_defined_dpi          : gives Tesseract's language model a sane DPI
#                             hint when the source image has none embedded.
_BASE_TESSERACT_FLAGS = (
    "--oem 1 "
    "-c preserve_interword_spaces=1 "
    "-c user_defined_dpi=300"
)
_TESSERACT_CONFIG = f"{_BASE_TESSERACT_FLAGS} --psm 6"
_FALLBACK_TESSERACT_CONFIG = f"{_BASE_TESSERACT_FLAGS} --psm 3"


def _preprocess(image: Image.Image) -> Image.Image:
    """Prep image for OCR: normalize mode, upscale (+sharpen), grayscale,
    autocontrast.

    Deliberately does NOT binarize — Tesseract runs Otsu internally and
    handles uneven lighting (shadows, glare, perspective on photos) better
    than a fixed global threshold.
    """
    if image.mode not in ("L", "RGB"):
        image = image.convert("RGB")

    if image.width < _MIN_WIDTH_PX:
        scale = _MIN_WIDTH_PX / image.width
        new_size = (int(image.width * scale), int(image.height * scale))
        image = image.resize(new_size, Image.LANCZOS)
        # Lanczos upscaling leaves edges a little soft — unsharp-mask sharpens
        # stroke edges back up so thin glyphs (₹, %, commas) survive binarization.
        image = image.filter(
            ImageFilter.UnsharpMask(radius=1.2, percent=150, threshold=3)
        )

    gray = ImageOps.grayscale(image)
    # cutoff=1 clips the top/bottom 1% — better for photos than the default.
    gray = ImageOps.autocontrast(gray, cutoff=1)
    return gray


def ocr_image(image: Image.Image) -> str:
    """Run OCR on a single PIL image. PSM 6 first (invoice block layout);
    fall back to PSM 3 (full auto) only if the first pass is near-empty."""
    processed = _preprocess(image)
    text = pytesseract.image_to_string(
        processed, lang=_TESSERACT_LANG, config=_TESSERACT_CONFIG
    )
    if len(text.strip()) < 20:
        alt = pytesseract.image_to_string(
            processed, lang=_TESSERACT_LANG, config=_FALLBACK_TESSERACT_CONFIG
        )
        if len(alt.strip()) > len(text.strip()):
            return alt
    return text


def extract_text_from_image_bytes(image_bytes: bytes) -> str:
    """Open bytes as a PIL image and run OCR. Handles PNG/JPG invoices.

    Respects EXIF orientation so portrait phone photos aren't processed
    sideways — a JPEG straight from a phone often has orientation stored as
    metadata rather than rotated pixels, and Tesseract reads the pixels.
    """
    with Image.open(io.BytesIO(image_bytes)) as img:
        img.load()
        img = ImageOps.exif_transpose(img)
        return ocr_image(img)


# Minimum char count required for the embedded text layer to be considered
# "useful". Some scanned PDFs have a few garbage chars in the text layer
# (page numbers, watermarks) while the actual content is image-only —
# require a meaningful amount of text before trusting it.
_NATIVE_TEXT_MIN_CHARS = 80


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Return text from a PDF using the best available method.

    1. Try the embedded text layer — for digital PDFs this is exact
       (perfect currency symbols, numbers, no OCR guessing).
    2. Fall back to rasterize-then-OCR for scanned/photographed PDFs.
    """
    try:
        native = extract_embedded_text(pdf_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Native PDF text extraction failed: %s", exc)
        native = ""

    if len(native.strip()) >= _NATIVE_TEXT_MIN_CHARS:
        logger.info("PDF has embedded text layer (%d chars) — skipping OCR.", len(native))
        return native

    logger.info("No usable embedded text — falling back to OCR.")
    images: List[Image.Image] = pdf_bytes_to_images(pdf_bytes)
    texts: List[str] = []
    for i, img in enumerate(images):
        try:
            texts.append(ocr_image(img))
        except Exception as exc:  # noqa: BLE001
            logger.warning("OCR failed on page %d: %s", i + 1, exc)
            texts.append("")
        finally:
            img.close()
    return "\n\n".join(texts)
