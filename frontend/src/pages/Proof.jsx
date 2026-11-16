import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Shell, Label, Badge, Disclaimer } from "../components/Shell";
import { api, usd, when } from "../lib/api";

export const certKind = (c) => (c.revoked ? "revoked" : c.mode);

export default function Proof() {
  const [certs, setCerts] = useState(null);
  useEffect(() => { api.get("/proof").then((r) => setCerts(r.data.certificates)); }, []);

  return (
    <Shell>
      <section className="py-14 sm:py-20">
        <Label>Proof wall</Label>
        <h1 className="mt-5 text-4xl font-black tracking-tight sm:text-5xl">Every slot, on the record.</h1>
        <p className="mt-3 max-w-xl text-sm text-[#8a8a94]">Certificates are issued only when Stripe confirms a payment. Newest first.</p>
        <div className="mt-12 border-t border-[#23232a]" data-testid="proof-list">
          {certs === null && <p className="py-8 font-mono text-xs text-[#8a8a94]">loading…</p>}
          {certs?.length === 0 && (
            <p data-testid="proof-empty-state" className="py-12 font-mono text-sm text-[#8a8a94]">No certificates yet. Nothing here is invented.</p>
          )}
          {certs?.map((c, i) => (
            <Link key={c.code} to={`/p/${c.code}`} data-testid={`proof-certificate-card-${c.code}`}
              style={{ animationDelay: `${i * 60}ms` }}
              className="rise group grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-2 border-b border-[#23232a] py-5 transition-colors duration-200 hover:bg-[#121216] sm:grid-cols-[1.2fr_1fr_auto_auto] sm:px-3">
              <span className={`font-mono text-sm sm:text-base ${c.revoked ? "text-[#8a8a94] line-through" : "text-[#e9e9ee] group-hover:text-[#c6f24e]"}`}>{c.code}</span>
              <span className="order-3 text-sm text-[#8a8a94] sm:order-none">{c.ship_title}</span>
              <span className="order-4 font-mono tnum text-sm sm:order-none">{usd(c.amount_cents)}</span>
              <Badge kind={certKind(c)} testid={`proof-badge-${c.code}`}>{c.revoked ? "REVOKED" : c.mode.toUpperCase()}</Badge>
              <span className="order-5 col-span-2 font-mono text-[11px] text-[#55555e] sm:col-span-4">issued {when(c.issued_at)}</span>
            </Link>
          ))}
        </div>
        <div className="mt-6"><Disclaimer testid="proof-disclaimer" /></div>
      </section>
    </Shell>
  );
}
