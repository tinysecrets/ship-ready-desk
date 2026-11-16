import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Label } from "../Shell";
import { api, usd, when, errMsg } from "../../lib/api";
import { RefundDialog } from "./RefundDialog";

const DeliveryNote = ({ o }) => {
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const write = async () => {
    setBusy(true);
    try {
      await api.post(`/desk/orders/${o.id}/delivery-note`);
      toast("Delivery note drafted. Nothing was sent.", { action: { label: "Open outbox", onClick: () => navigate("/desk/drafts") } });
    } catch (e) { toast.error(errMsg(e, "Draft failed — try again")); } finally { setBusy(false); }
  };
  return (
    <button data-testid={`desk-delivery-note-button-${o.id}`} onClick={write} disabled={busy}
      className="border border-[#c6f24e]/40 px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest text-[#c6f24e] transition-colors hover:bg-[#c6f24e] hover:text-[#0b0b0d] disabled:opacity-50">
      {busy ? "Writing…" : "Write delivery note"}
    </button>
  );
};

const STATE = {
  paid: "text-[#c6f24e]", reserved: "text-[#ffb86c]", refunded: "text-[#ff8a8a]",
  disputed: "text-[#ff5555]", expired: "text-[#55555e]", failed: "text-[#55555e]",
};

export const OrdersTable = ({ orders, onChange }) => {
  const [target, setTarget] = useState(null);
  return (
    <div className="mt-4 border border-[#23232a]" data-testid="desk-orders-table">
      <div className="flex items-center justify-between border-b border-[#23232a] bg-[#121216] px-5 py-3">
        <Label>Orders</Label><span className="font-mono text-[11px] text-[#8a8a94]">{orders.length}</span>
      </div>
      {orders.length === 0 && <p data-testid="desk-orders-empty" className="px-5 py-8 font-mono text-sm text-[#8a8a94]">No orders yet.</p>}
      <div className="divide-y divide-[#23232a]">
        {orders.map((o) => {
          const remaining = o.amount_cents - o.refunded_cents - o.disputed_cents;
          const refundable = ["paid", "disputed"].includes(o.state) && remaining > 0 && o.payment_intent;
          return (
            <div key={o.id} data-testid={`desk-order-row-${o.id}`} className="grid grid-cols-2 gap-x-4 gap-y-2 px-5 py-4 text-sm md:grid-cols-[1.2fr_0.7fr_0.8fr_0.8fr_1.1fr_1.5fr] md:items-center">
              <div className="col-span-2 min-w-0 md:col-span-1">
                <div className="truncate font-mono text-xs text-[#e9e9ee]">{o.id}</div>
                <div className="font-mono text-[11px] text-[#55555e]">{when(o.created_at)}</div>
              </div>
              <div data-testid={`desk-order-state-${o.id}`} className={`font-mono text-xs uppercase tracking-wider ${STATE[o.state] || ""}`}>
                {o.state}{o.dispute_status ? ` · ${o.dispute_status}` : ""}{o.over_capacity ? " · over cap" : ""}
              </div>
              <div className="font-mono tnum" data-testid={`desk-order-amount-${o.id}`}>{usd(o.amount_cents)}</div>
              <div className="font-mono tnum text-[#ff8a8a]" data-testid={`desk-order-refunded-${o.id}`}>{o.refunded_cents ? usd(-o.refunded_cents) : "—"}</div>
              <div className="min-w-0 font-mono text-xs" data-testid={`desk-order-cert-${o.id}`}>
                {o.cert_code ? <Link to={`/p/${o.cert_code}`} className="text-[#c6f24e] hover:underline">{o.cert_code}</Link> : <span className="text-[#55555e]">no certificate</span>}
              </div>
              <div className="col-span-2 flex flex-wrap gap-2 md:col-span-1 md:justify-end">
                {["paid", "disputed"].includes(o.state) && o.cert_code && <DeliveryNote o={o} />}
                {refundable && (
                  <button data-testid={`desk-refund-button-${o.id}`} onClick={() => setTarget(o)}
                    className="border border-[#ff5555]/40 px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest text-[#ff8a8a] transition-colors hover:bg-[#ff5555] hover:text-white">
                    Refund
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <RefundDialog order={target && (orders.find((o) => o.id === target.id) || target)} onClose={() => setTarget(null)} onDone={onChange} />
    </div>
  );
};
