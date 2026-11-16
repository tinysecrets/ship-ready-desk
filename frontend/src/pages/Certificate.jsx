import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Copy } from "lucide-react";
import { toast } from "sonner";
import { Shell, Label, Badge, Disclaimer } from "../components/Shell";
import { api, usd, when } from "../lib/api";
import NotFound from "./NotFound";

const Field = ({ label, children, testid }) => (
  <div className="border-b border-[#23232a] py-4">
    <Label>{label}</Label>
    <div data-testid={testid} className="mt-1.5 font-mono tnum text-base">{children}</div>
  </div>
);

export default function Certificate() {
  const { code } = useParams();
  const [c, setC] = useState(null);
  const [missing, setMissing] = useState(false);
  useEffect(() => {
    api.get(`/certificates/${code}`).then((r) => setC(r.data)).catch(() => setMissing(true));
  }, [code]);

  if (missing) return <NotFound />;
  const copy = () => { navigator.clipboard?.writeText(c.code); toast("Code copied"); };

  return (
    <Shell>
      <section className="mx-auto max-w-2xl py-14 sm:py-20">
        <Label>Certificate</Label>
        {c && (
          <div className="rise mt-6 border border-[#23232a] bg-[#121216] p-6 sm:p-10">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <h1 data-testid="certificate-status-badge"
                className={`text-4xl font-black tracking-tight sm:text-5xl ${c.revoked ? "text-[#ff5555]" : "text-[#c6f24e]"}`}>
                {c.revoked ? "REVOKED" : "Verified"}
              </h1>
              <Badge kind={c.mode} testid="certificate-mode-badge">{c.mode.toUpperCase()}</Badge>
            </div>
            <button onClick={copy} data-testid="certificate-code-copy"
              className="group mt-6 flex max-w-full items-center gap-3 break-all font-mono text-lg text-[#e9e9ee] transition-colors hover:text-[#c6f24e] sm:text-xl">
              <span data-testid="certificate-code">{c.code}</span>
              <Copy className="h-4 w-4 shrink-0 text-[#8a8a94] group-hover:text-[#c6f24e]" />
            </button>
            <div className="mt-6 border-t border-[#23232a]">
              <Field label="Ship">{c.ship_title}</Field>
              <Field label="Paid" testid="certificate-paid-value">{usd(c.amount_cents)}</Field>
              <Field label="Verified contribution" testid="certificate-contribution-value">
                <span className={c.verified_contribution_cents < 0 ? "text-[#ff5555]" : "text-[#c6f24e]"}>{usd(c.verified_contribution_cents)}</span>
              </Field>
              <Field label="Issued" testid="certificate-issued-value">{when(c.issued_at)}</Field>
              {c.revoked && <Field label="Revoked" testid="certificate-revoked-value">{when(c.revoked_at)}</Field>}
            </div>
            <div className="mt-5"><Disclaimer testid="certificate-disclaimer" /></div>
          </div>
        )}
      </section>
    </Shell>
  );
}
