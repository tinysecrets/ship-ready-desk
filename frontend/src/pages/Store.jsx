import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowRight, Loader2 } from "lucide-react";
import { Shell, Label, Badge, Disclaimer } from "../components/Shell";
import { api, newIdemKey, usd, errMsg } from "../lib/api";
import NotFound from "./NotFound";

const Confirmation = ({ orderId }) => {
  const [o, setO] = useState(null);
  useEffect(() => {
    let n = 0;
    let t;
    const tick = async () => {
      try {
        const r = await api.get(`/orders/${orderId}`);
        setO(r.data);
        if (r.data.certificate_code || ++n > 30) return;
      } catch { if (++n > 30) return; }
      t = setTimeout(tick, 2000);
    };
    tick();
    return () => clearTimeout(t);
  }, [orderId]);

  return (
    <div data-testid="store-confirmation" className="rise mb-10 border border-[#c6f24e]/40 bg-[#c6f24e]/5 p-5">
      <Label className="text-[#c6f24e]">Payment returned</Label>
      {o?.certificate_code ? (
        <p className="mt-2 text-sm">
          Booked. Your certificate:{" "}
          <Link data-testid="store-confirmation-link" to={`/p/${o.certificate_code}`} className="font-mono text-[#c6f24e] underline underline-offset-4">
            {o.certificate_code}
          </Link>
        </p>
      ) : (
        <p className="mt-2 flex items-center gap-2 text-sm text-[#8a8a94]" data-testid="store-confirmation-pending">
          <Loader2 className="h-4 w-4 animate-spin" /> Waiting for Stripe to confirm the payment{o ? ` (order ${o.state})` : ""}…
        </p>
      )}
    </div>
  );
};

const Slots = ({ open, total }) => (
  <div className="flex gap-1.5" aria-hidden>
    {Array.from({ length: total }).map((_, i) => (
      <span key={i} className={`h-2 w-10 ${i < open ? "bg-[#c6f24e]" : "bg-[#23232a]"}`} />
    ))}
  </div>
);

export default function Store() {
  const { slug } = useParams();
  const [params] = useSearchParams();
  const [ship, setShip] = useState(null);
  const [missing, setMissing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const idem = useRef(newIdemKey());

  const load = () => api.get(`/ships/${slug}`).then((r) => setShip(r.data)).catch((e) => e?.response?.status === 404 && setMissing(true));
  useEffect(() => { load(); }, [slug]); // eslint-disable-line react-hooks/exhaustive-deps

  const take = async () => {
    setBusy(true);
    setError("");
    try {
      const r = await api.post(`/ships/${slug}/checkout`, { origin_url: window.location.origin }, { headers: { "x-idem-key": idem.current } });
      window.location.href = r.data.url;
    } catch (e) {
      setError(errMsg(e) === "sold out" ? "Sold out." : errMsg(e));
      idem.current = newIdemKey();
      setBusy(false);
      load();
    }
  };

  if (missing) return <NotFound />;
  const soldOut = ship && ship.open === 0;

  return (
    <Shell>
      <section className="py-14 sm:py-20">
        {params.get("ok") === "1" && params.get("order") && <Confirmation orderId={params.get("order")} />}
        {params.get("cancelled") === "1" && (
          <p data-testid="store-cancelled" className="mb-8 font-mono text-xs text-[#8a8a94]">Checkout cancelled. Your hold is released when it expires.</p>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Label>Store / {slug}</Label>
          {ship && <Badge kind={ship.mode} testid="store-mode-badge">{ship.mode} mode</Badge>}
        </div>
        <h1 data-testid="store-title" className="rise mt-6 text-4xl font-black tracking-tight sm:text-5xl lg:text-6xl">{ship?.title || " "}</h1>

        <div className="mt-12 grid gap-10 border-t border-[#23232a] pt-10 md:grid-cols-[1.4fr_1fr]">
          <div>
            <Label>Price</Label>
            <div data-testid="store-price" className="rise rise-1 mt-2 font-mono tnum text-5xl font-bold tracking-tighter text-[#c6f24e] sm:text-6xl lg:text-7xl">
              {ship ? usd(ship.price_cents) : "…"}
            </div>
            <p className="mt-3 text-sm text-[#8a8a94]">One payment. One slot. A public certificate once Stripe confirms it.</p>
          </div>
          <div className="rise rise-2 border border-[#23232a] bg-[#121216] p-6">
            <Label>Capacity ({ship?.mode || "…"} mode)</Label>
            <div data-testid="store-slot-count-badge" className="mt-3 font-mono tnum text-2xl font-bold">
              {ship ? `${ship.open} of ${ship.slots} open` : "…"}
            </div>
            {ship && <div className="mt-4"><Slots open={ship.open} total={ship.slots} /></div>}
            <div className="mt-6">
              {ship && !ship.payments_configured ? (
                <p data-testid="store-payment-unconfigured-message" className="font-mono text-sm text-[#ffb86c]">Payments not configured.</p>
              ) : soldOut ? (
                <p data-testid="store-sold-out-message" className="text-lg font-bold">Sold out.</p>
              ) : (
                <button data-testid="store-checkout-button" onClick={take} disabled={!ship || busy}
                  className="group inline-flex w-full items-center justify-center gap-3 bg-[#c6f24e] px-6 py-4 text-sm font-bold text-[#0b0b0d] transition-colors duration-200 hover:bg-[#b2df3b] active:translate-y-px disabled:cursor-not-allowed disabled:opacity-50">
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  {busy ? "Holding your slot…" : "Take a slot"}
                  {!busy && <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />}
                </button>
              )}
              {error && <p data-testid="store-checkout-error" className="mt-3 font-mono text-xs text-[#ff5555]">{error}</p>}
            </div>
            <p className="mt-5 font-mono text-[11px] text-[#8a8a94]">Taking a slot holds it for 45 minutes while you pay.</p>
          </div>
        </div>
        <div className="mt-8"><Disclaimer testid="store-disclaimer" /></div>
      </section>
    </Shell>
  );
}
