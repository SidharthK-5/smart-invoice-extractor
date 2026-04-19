import { useState } from "react";
import { Download, ScanLine, FileSearch } from "lucide-react";
import "./App.css";
import UploadForm from "./components/UploadForm";
import InvoiceTable from "./components/InvoiceTable";
import SummaryTiles from "./components/SummaryTiles";
import { extractInvoices } from "./api";
import { downloadCsv } from "./utils/csv";
import type { Invoice } from "./types";

export default function App() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(files: File[]) {
    setBusy(true);
    setError(null);
    setStatus(`Uploading ${files.length} file${files.length > 1 ? "s" : ""}…`);
    try {
      setStatus(`Processing ${files.length} invoice${files.length > 1 ? "s" : ""}…`);
      const resp = await extractInvoices(files);
      setInvoices(resp.invoices);
      setStatus(`Extracted ${resp.invoices.length} invoice${resp.invoices.length > 1 ? "s" : ""}.`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setStatus("");
    } finally {
      setBusy(false);
    }
  }

  const hasResults = invoices.length > 0;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__brand">
          <div className="app-header__logo"><ScanLine size={22} /></div>
          <div>
            <h1>Smart Invoice Extractor</h1>
            <p>
              Upload invoice PDFs or images — we use OCR + Gemma to pull out
              vendor, totals, line items, GST split, and payment details, ready
              to download as CSV.
            </p>
          </div>
        </div>
      </header>

      <section className="card">
        <h2 className="card__title">Upload invoices</h2>
        <UploadForm onSubmit={handleSubmit} busy={busy} status={status} />
        {error && <div className="error" style={{ marginTop: 10 }}>{error}</div>}
      </section>

      {hasResults && (
        <>
          <SummaryTiles invoices={invoices} />

          <section className="card">
            <div className="card__header-row">
              <h2 className="card__title">Extracted invoices</h2>
              <button className="btn" onClick={() => downloadCsv(invoices)}>
                <Download size={16} style={{ marginRight: 6 }} />
                Download CSV
              </button>
            </div>
            <InvoiceTable invoices={invoices} />
          </section>
        </>
      )}

      {!hasResults && !busy && (
        <section className="empty-state">
          <FileSearch size={40} className="empty-state__icon" />
          <div className="empty-state__title">No invoices yet</div>
          <div className="empty-state__subtitle">
            Drag in a PDF or image above, or click the drop zone to browse.
            You'll see a summary table and can export everything as CSV.
          </div>
        </section>
      )}
    </div>
  );
}
