import { IndianRupee, AlertTriangle, Receipt } from "lucide-react";
import type { Invoice } from "../types";

interface Props {
  invoices: Invoice[];
}

function sumFinal(invoices: Invoice[]): { total: number; currency: string } {
  let total = 0;
  let currency = "";
  for (const inv of invoices) {
    const v = inv.total;
    if (typeof v === "number" && !Number.isNaN(v)) total += v;
    if (!currency && inv.currency) currency = inv.currency;
  }
  return { total, currency };
}

function formatCurrency(amount: number, code: string): string {
  const n = amount.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return code ? `${code} ${n}` : n;
}

export default function SummaryTiles({ invoices }: Props) {
  const total = invoices.length;
  const failed = invoices.filter((i) => !!i.error || !!i.notes?.toLowerCase().includes("failed")).length;
  const { total: spend, currency } = sumFinal(invoices);

  return (
    <div className="tiles">
      <div className="tile">
        <div className="tile__icon tile__icon--blue"><Receipt size={18} /></div>
        <div className="tile__body">
          <div className="tile__label">Invoices</div>
          <div className="tile__value">{total}</div>
        </div>
      </div>

      <div className="tile">
        <div className="tile__icon tile__icon--green"><IndianRupee size={18} /></div>
        <div className="tile__body">
          <div className="tile__label">Total spend</div>
          <div className="tile__value">{formatCurrency(spend, currency)}</div>
        </div>
      </div>

      <div className="tile">
        <div className={`tile__icon ${failed ? "tile__icon--red" : "tile__icon--gray"}`}>
          <AlertTriangle size={18} />
        </div>
        <div className="tile__body">
          <div className="tile__label">Failed</div>
          <div className="tile__value">{failed}</div>
        </div>
      </div>
    </div>
  );
}
