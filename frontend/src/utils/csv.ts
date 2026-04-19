import type { Invoice, LineItem } from "../types";

// Column order: existing columns first (so the original CSV shape is
// preserved), then new metadata, price breakdown, and per-line-item fields.
const CSV_COLUMNS = [
  "filename",
  "vendor_name",
  "invoice_number",
  "invoice_date",
  "currency",
  "line_description",
  "quantity",
  "unit_price",
  "line_total",
  "hsn_code",
  "tax_rate",
  "subtotal",
  "discount_amount",
  "shipping_charges",
  "processing_fees",
  "tax",
  "cgst",
  "sgst",
  "igst",
  "rounding_adjustment",
  "total",
  "order_number",
  "payment_method",
  "vendor_gstin",
  "buyer_gstin",
  "delivery_address",
  "summary",
] as const;

function escapeCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const str = String(value);
  if (/[",\n\r]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function baseRow(inv: Invoice): Record<string, unknown> {
  const tb = inv.tax_breakdown ?? { cgst: null, sgst: null, igst: null };
  return {
    filename: inv.filename,
    vendor_name: inv.vendor_name,
    invoice_number: inv.invoice_number,
    invoice_date: inv.invoice_date,
    currency: inv.currency,
    subtotal: inv.subtotal,
    discount_amount: inv.discount_amount ?? "",
    shipping_charges: inv.shipping_charges ?? "",
    processing_fees: inv.processing_fees ?? "",
    tax: inv.tax,
    cgst: tb.cgst,
    sgst: tb.sgst,
    igst: tb.igst,
    rounding_adjustment: inv.rounding_adjustment ?? "",
    total: inv.total,
    order_number: inv.order_number ?? "",
    payment_method: inv.payment_method ?? "",
    vendor_gstin: inv.vendor_gstin ?? "",
    buyer_gstin: inv.buyer_gstin ?? "",
    delivery_address: inv.delivery_address ?? "",
    summary: inv.summary ?? "",
  };
}

function lineFields(li: LineItem): Record<string, unknown> {
  return {
    line_description: li.description,
    quantity: li.quantity,
    unit_price: li.unit_price,
    line_total: li.line_total,
    hsn_code: li.hsn_code ?? "",
    tax_rate: li.tax_rate ?? "",
  };
}

export function invoicesToCsv(invoices: Invoice[]): string {
  const rows: string[] = [CSV_COLUMNS.join(",")];

  for (const inv of invoices) {
    const base = baseRow(inv);

    if (!inv.line_items || inv.line_items.length === 0) {
      rows.push(
        CSV_COLUMNS.map((c) => escapeCell((base as Record<string, unknown>)[c] ?? "")).join(",")
      );
      continue;
    }

    for (const li of inv.line_items) {
      const row: Record<string, unknown> = { ...base, ...lineFields(li) };
      rows.push(CSV_COLUMNS.map((c) => escapeCell(row[c] ?? "")).join(","));
    }
  }

  return rows.join("\n");
}

export function downloadCsv(invoices: Invoice[], filename = "invoices.csv") {
  const csv = invoicesToCsv(invoices);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
