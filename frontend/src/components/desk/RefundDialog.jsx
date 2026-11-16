import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "../ui/dialog";
import { api, newIdemKey, usd, errMsg } from "../../lib/api";

export const RefundDialog = ({ order, onClose, onDone }) => {
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const idem = useRef(newIdemKey());

  useEffect(() => { setAmount(""); setResult(null); idem.current = newIdemKey(); }, [order?.id]);
  if (!order) return null;
  const remaining = order.amount_cents - order.refunded_cents - order.disputed_cents;

  const onAmount = (v) => { setAmount(v); setResult(null); idem.current = newIdemKey(); };
  const submit = async () => {
    const cents = amount.trim() ? Math.round(parseFloat(amount) * 100) : null;
    if (cents !== null && (!Number.isFinite(cents) || cents <= 0)) return toast.error("Enter a positive amount or leave empty for full.");
    setBusy(true);
    try {
      const r = await api.post(`/desk/orders/${order.id}/refund`, { amount_cents: cents }, { headers: { "x-idem-key": idem.current } });
      setResult(r.data);
      toast(r.data.replayed ? "Same request — no second refund created." : `Refund ${usd(r.data.amount_cents)} sent to Stripe${r.data.capped ? " (capped)" : ""}.`);
      onDone();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };

  return (
    <Dialog open={!!order} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="rounded-none border-[#23232a] bg-[#121216] text-[#e9e9ee] sm:max-w-md" data-testid="refund-dialog">
        <DialogHeader>
          <DialogTitle className="text-xl font-black tracking-tight">Refund order</DialogTitle>
          <DialogDescription className="break-all font-mono text-xs text-[#8a8a94]">{order.id} · remaining {usd(remaining)}</DialogDescription>
        </DialogHeader>
        <label className="mt-2 block font-mono text-[11px] uppercase tracking-widest text-[#8a8a94]" htmlFor="refund-amount">Amount in USD (empty = full remaining)</label>
        <input id="refund-amount" data-testid="refund-amount-input" inputMode="decimal" value={amount} onChange={(e) => onAmount(e.target.value)}
          placeholder={(remaining / 100).toFixed(2)}
          className="w-full border border-[#23232a] bg-[#0b0b0d] px-4 py-3 font-mono tnum text-sm focus:border-[#c6f24e] focus:outline-none" />
        <p className="font-mono text-[11px] text-[#8a8a94]">Amounts above the remaining balance are capped. Clicking again repeats the same request — Stripe gets it once.</p>
        {result && (
          <p data-testid="refund-result" className="break-all border border-[#23232a] p-3 font-mono text-xs">
            {result.replayed ? "replayed · " : ""}{result.refund_id} · {usd(result.amount_cents)} · {result.status}{result.capped ? " · capped" : ""}
          </p>
        )}
        <button onClick={submit} disabled={busy} data-testid="refund-submit-button"
          className="inline-flex w-full items-center justify-center gap-2 bg-[#ff5555] px-5 py-3 text-sm font-bold text-white transition-colors hover:bg-[#e04848] disabled:opacity-50">
          {busy && <Loader2 className="h-4 w-4 animate-spin" />} Issue refund
        </button>
      </DialogContent>
    </Dialog>
  );
};
