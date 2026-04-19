export interface LineItem {
  description: string;
  quantity: number | null;
  unit_price: number | null;
  line_total: number | null;
  hsn_code?: string;
  tax_rate?: number | null;
}

export interface TaxBreakdown {
  cgst: number | null;
  sgst: number | null;
  igst: number | null;
}

export interface Invoice {
  filename: string;
  vendor_name: string;
  invoice_number: string;
  invoice_date: string;
  currency: string;

  order_number?: string;
  payment_method?: string;
  vendor_gstin?: string;
  buyer_gstin?: string;
  delivery_address?: string;

  subtotal: number | null;
  discount_amount?: number | null;
  shipping_charges?: number | null;
  processing_fees?: number | null;
  tax: number | null;
  tax_breakdown?: TaxBreakdown;
  rounding_adjustment?: number | null;
  total: number | null;

  line_items: LineItem[];
  summary?: string;
  raw_ocr_excerpt: string;
  notes?: string;
  error?: string | null;
}

export interface ExtractResponse {
  invoices: Invoice[];
}
