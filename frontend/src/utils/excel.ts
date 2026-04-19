import * as XLSX from "xlsx";
import type { Invoice } from "../types";

const SUMMARY_COLUMNS = [
  "filename",
  "vendor_name",
  "invoice_number",
  "invoice_date",
  "currency",
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

const LINE_ITEM_COLUMNS = [
  "filename",
  "invoice_number",
  "vendor_name",
  "line_description",
  "quantity",
  "unit_price",
  "line_total",
  "hsn_code",
  "tax_rate",
] as const;

function summaryRow(inv: Invoice): Record<string, unknown> {
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

function lineItemRows(inv: Invoice): Record<string, unknown>[] {
  if (!inv.line_items || inv.line_items.length === 0) return [];
  return inv.line_items.map((li) => ({
    filename: inv.filename,
    invoice_number: inv.invoice_number,
    vendor_name: inv.vendor_name,
    line_description: li.description ?? "",
    quantity: li.quantity,
    unit_price: li.unit_price,
    line_total: li.line_total,
    hsn_code: li.hsn_code ?? "",
    tax_rate: li.tax_rate ?? "",
  }));
}

function autoWidths(rows: Record<string, unknown>[], columns: readonly string[]): { wch: number }[] {
  return columns.map((col) => {
    const headerLen = col.length;
    const maxDataLen = rows.reduce((max, r) => {
      const v = r[col];
      const s = v === null || v === undefined ? "" : String(v);
      return Math.max(max, s.length);
    }, 0);
    return { wch: Math.min(Math.max(headerLen, maxDataLen) + 2, 60) };
  });
}

export function invoicesToWorkbook(invoices: Invoice[]): XLSX.WorkBook {
  const summaryRows = invoices.map(summaryRow);
  const lineRows = invoices.flatMap(lineItemRows);

  const wb = XLSX.utils.book_new();

  const summarySheet = XLSX.utils.json_to_sheet(summaryRows, {
    header: SUMMARY_COLUMNS as unknown as string[],
  });
  summarySheet["!cols"] = autoWidths(summaryRows, SUMMARY_COLUMNS);
  XLSX.utils.book_append_sheet(wb, summarySheet, "Invoice Summary");

  const lineSheet = XLSX.utils.json_to_sheet(lineRows, {
    header: LINE_ITEM_COLUMNS as unknown as string[],
  });
  lineSheet["!cols"] = autoWidths(lineRows, LINE_ITEM_COLUMNS);
  XLSX.utils.book_append_sheet(wb, lineSheet, "Invoice Line Items");

  return wb;
}

export function downloadExcel(invoices: Invoice[], filename = "invoices.xlsx") {
  const wb = invoicesToWorkbook(invoices);
  XLSX.writeFile(wb, filename);
}
