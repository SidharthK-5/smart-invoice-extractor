"""Pydantic models for the invoice extraction API."""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: Optional[str] = ""
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    hsn_code: Optional[str] = ""         # Indian GST classification
    tax_rate: Optional[float] = None     # percent (e.g. 18.0 for 18%)


class TaxBreakdown(BaseModel):
    cgst: Optional[float] = None
    sgst: Optional[float] = None
    igst: Optional[float] = None


class Invoice(BaseModel):
    filename: str
    vendor_name: Optional[str] = ""
    invoice_number: Optional[str] = ""
    invoice_date: Optional[str] = ""
    currency: Optional[str] = ""

    # Identity / metadata
    order_number: Optional[str] = ""
    payment_method: Optional[str] = ""
    vendor_gstin: Optional[str] = ""
    buyer_gstin: Optional[str] = ""
    delivery_address: Optional[str] = ""

    # Money breakdown
    subtotal: Optional[float] = None
    discount_amount: Optional[float] = None
    shipping_charges: Optional[float] = None
    processing_fees: Optional[float] = None
    tax: Optional[float] = None
    tax_breakdown: TaxBreakdown = Field(default_factory=TaxBreakdown)
    rounding_adjustment: Optional[float] = None
    total: Optional[float] = None        # final amount payable after all discounts/fees

    line_items: List[LineItem] = Field(default_factory=list)

    summary: Optional[str] = ""          # human-readable one-liner
    raw_ocr_excerpt: str = ""
    notes: Optional[str] = ""            # parse issues / missing fields
    error: Optional[str] = None


class ExtractResponse(BaseModel):
    invoices: List[Invoice]


class HealthResponse(BaseModel):
    status: str
    gemini_configured: bool
