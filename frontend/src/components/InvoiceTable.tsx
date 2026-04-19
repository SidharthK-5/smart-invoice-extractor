import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { Invoice } from "../types";

interface Props {
  invoices: Invoice[];
}

function fmt(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return Number.isInteger(v) ? v.toString() : v.toFixed(2);
}

function money(v: number | null | undefined, currency: string): string {
  if (v === null || v === undefined) return "—";
  const n = v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return currency ? `${currency} ${n}` : n;
}

export default function InvoiceTable({ invoices }: Props) {
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  function toggle(i: number) {
    setExpanded((prev) => ({ ...prev, [i]: !prev[i] }));
  }

  return (
    <div className="invoice-table-wrap">
      <table className="invoice-table">
        <thead>
          <tr>
            <th style={{ width: 36 }}></th>
            <th>Filename</th>
            <th>Vendor</th>
            <th>Invoice #</th>
            <th>Date</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((inv, i) => {
            const isOpen = !!expanded[i];
            const currency = inv.currency || "";
            return (
              <Fragment key={i}>
                <tr className={isOpen ? "row row--open" : "row"} onClick={() => toggle(i)}>
                  <td>
                    <button className="expand-btn" aria-label={isOpen ? "Collapse" : "Expand"}>
                      {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>
                  </td>
                  <td className="cell-ellipsis" title={inv.filename}>{inv.filename}</td>
                  <td>{inv.vendor_name || "—"}</td>
                  <td>{inv.invoice_number || "—"}</td>
                  <td>{inv.invoice_date || "—"}</td>
                  <td><strong>{money(inv.total, currency)}</strong></td>
                </tr>

                {isOpen && (
                  <tr className="row-expand">
                    <td colSpan={6} className="expand-body">
                      {inv.summary && (
                        <div className="summary-block">{inv.summary}</div>
                      )}

                      <div className="detail-grid">
                        <div className="detail-section">
                          <h4>Invoice details</h4>
                          <dl className="kv">
                            {inv.order_number && (<><dt>Order #</dt><dd>{inv.order_number}</dd></>)}
                            {inv.payment_method && (<><dt>Payment</dt><dd>{inv.payment_method}</dd></>)}
                            {inv.vendor_gstin && (<><dt>Vendor GSTIN</dt><dd>{inv.vendor_gstin}</dd></>)}
                            {inv.buyer_gstin && (<><dt>Buyer GSTIN</dt><dd>{inv.buyer_gstin}</dd></>)}
                            {inv.delivery_address && (<><dt>Delivery</dt><dd>{inv.delivery_address}</dd></>)}
                            {!inv.order_number && !inv.payment_method && !inv.vendor_gstin && !inv.buyer_gstin && !inv.delivery_address && (
                              <div className="status">No additional details extracted.</div>
                            )}
                          </dl>
                        </div>

                        <div className="detail-section">
                          <h4>Financial breakdown</h4>
                          <dl className="kv">
                            <dt>Subtotal</dt><dd>{money(inv.subtotal, currency)}</dd>
                            {inv.shipping_charges != null && (<><dt>Shipping</dt><dd>{money(inv.shipping_charges, currency)}</dd></>)}
                            {inv.processing_fees != null && (<><dt>Processing fee</dt><dd>{money(inv.processing_fees, currency)}</dd></>)}
                            {inv.tax != null && (<><dt>Tax</dt><dd>{money(inv.tax, currency)}</dd></>)}
                            {inv.rounding_adjustment != null && (<><dt>Rounding</dt><dd>{money(inv.rounding_adjustment, currency)}</dd></>)}
                            {inv.discount_amount != null && (<><dt>Discount</dt><dd>− {money(inv.discount_amount, currency)}</dd></>)}
                            <dt className="kv__strong">Total</dt><dd className="kv__strong">{money(inv.total, currency)}</dd>
                          </dl>
                        </div>
                      </div>

                      <div className="detail-section">
                        <h4>Line items</h4>
                        {inv.line_items.length === 0 ? (
                          <div className="status">No line items extracted.</div>
                        ) : (
                          <table className="line-items-table">
                            <thead>
                              <tr>
                                <th>Description</th>
                                <th style={{ width: 70 }}>Qty</th>
                                <th style={{ width: 120 }}>Unit price</th>
                                <th style={{ width: 120 }}>Line total</th>
                              </tr>
                            </thead>
                            <tbody>
                              {inv.line_items.map((li, j) => (
                                <tr key={j}>
                                  <td>{li.description || "—"}</td>
                                  <td>{fmt(li.quantity)}</td>
                                  <td>{money(li.unit_price, currency)}</td>
                                  <td>{money(li.line_total, currency)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>

                      {(inv.notes || inv.error || inv.raw_ocr_excerpt) && (
                        <div className="detail-section detail-section--muted">
                          {inv.notes && <div className="notes">Notes: {inv.notes}</div>}
                          {inv.error && <div className="row-error">Error: {inv.error}</div>}
                          {inv.raw_ocr_excerpt && (
                            <details style={{ marginTop: 6 }}>
                              <summary>OCR excerpt</summary>
                              <pre className="ocr-excerpt">{inv.raw_ocr_excerpt}</pre>
                            </details>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
