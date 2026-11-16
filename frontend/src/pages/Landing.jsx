import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Shell, Label, Disclaimer } from "../components/Shell";
import { api, usd } from "../lib/api";

const Row = ({ label, value, strong, testid }) => (
  <div className={`flex items-baseline justify-between gap-4 py-2.5 ${strong ? "border-t border-[#e9e9ee]/40 pt-3" : "border-b border-dashed border-[#23232a]"}`}>
    <span className={`text-sm ${strong ? "font-semibold text-[#e9e9ee]" : "text-[#8a8a94]"}`}>{label}</span>
    <span data-testid={testid} className={`font-mono tnum text-sm ${strong ? "text-[#c6f24e] font-bold" : "text-[#e9e9ee]"}`}>{value}</span>
  </div>
);

export default function Landing() {
  const [m, setM] = useState(null);
  useEffect(() => { api.get("/money").then((r) => setM(r.data)); }, []);

  return (
    <Shell>
      <section className="grid gap-14 py-16 sm:py-24 lg:grid-cols-[1.25fr_1fr] lg:gap-20">
        <div>
          <Label className="rise">Shipready / one offer</Label>
          <h1 data-testid="landing-headline" className="rise rise-1 mt-6 text-4xl font-black leading-[0.95] tracking-tight sm:text-5xl lg:text-6xl">
            Three slots.<br />One offer.<br />One price.
          </h1>
          <div className="rise rise-2 mt-10">
            <div data-testid="landing-price" className="font-mono tnum text-5xl font-bold tracking-tighter text-[#c6f24e] sm:text-6xl lg:text-7xl">
              {m ? usd(m.price_cents) : "$1,090.00"}
            </div>
            <p className="mt-3 max-w-md text-sm text-[#8a8a94] sm:text-base">
              The Shipready Sprint. Paid through Stripe Checkout, booked once in an append-only ledger, proven on a public certificate.
            </p>
          </div>
          <Link to="/s/shipready-sprint" data-testid="landing-take-slot-button"
            className="rise rise-3 group mt-10 inline-flex items-center gap-3 bg-[#c6f24e] px-7 py-4 text-sm font-bold text-[#0b0b0d] transition-colors duration-200 hover:bg-[#b2df3b] active:translate-y-px">
            Take a slot <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
          </Link>
        </div>

        <aside className="rise rise-4 self-end border border-[#23232a] bg-[#121216] p-6 sm:p-8" data-testid="landing-arithmetic">
          <Label>Per-close arithmetic</Label>
          <div className="mt-5">
            <Row label="Price" value={m ? usd(m.price_cents) : "…"} />
            <Row label={m ? `Stripe fee ${(m.fee_bps / 100).toFixed(1)}% + ${m.fee_fixed_cents}¢` : "Stripe fee"} value={m ? usd(-m.fee_per_close_cents) : "…"} />
            <Row label="Compute" value={m ? usd(-m.compute_cents) : "…"} />
            <Row strong label="Contribution per close" value={m ? usd(m.contribution_per_close_cents) : "…"} testid="landing-contribution" />
          </div>
          <div className="mt-6 grid grid-cols-2 gap-4 border-t border-[#23232a] pt-5">
            <div>
              <Label>Target</Label>
              <div className="mt-1 font-mono tnum text-lg">{m ? usd(m.floor_cents) : "…"}</div>
            </div>
            <div>
              <Label>Closes to clear</Label>
              <div className="mt-1 font-mono tnum text-lg" data-testid="landing-closes-for-floor">{m ? m.closes_for_floor : "…"}</div>
            </div>
          </div>
          <div className="mt-5"><Disclaimer testid="landing-disclaimer" /></div>
        </aside>
      </section>
    </Shell>
  );
}
