import { useState } from "react";
import { Copy, Check, Timer } from "lucide-react";
import { toast } from "sonner";
import { Label } from "../Shell";
import { api, when, errMsg } from "../../lib/api";

const Item = ({ label, children, testid }) => (
  <div className="min-w-0 border-b border-[#23232a] py-3">
    <Label>{label}</Label>
    <div data-testid={testid} className="mt-1 break-all font-mono text-sm">{children}</div>
  </div>
);

const Yes = ({ on }) => <span className={on ? "text-[#c6f24e]" : "text-[#ff5555]"}>{on ? "yes" : "no"}</span>;

export const StatusPanel = ({ status: s, unresolved, onChange }) => {
  const [copied, setCopied] = useState(false);
  const [sweeping, setSweeping] = useState(false);
  const ep = s.stripe_endpoint;

  const copy = () => {
    navigator.clipboard?.writeText(s.webhook_url);
    setCopied(true);
    toast("Webhook URL copied");
    setTimeout(() => setCopied(false), 1500);
  };
  const sweep = async () => {
    setSweeping(true);
    try {
      const r = await api.post("/desk/sweep");
      toast(`Sweep: ${r.data.expired} expired, ${r.data.orphans_released} orphans released`);
      onChange();
    } catch (e) { toast.error(errMsg(e)); } finally { setSweeping(false); }
  };

  return (
    <div className="mt-4 border border-[#23232a] p-5 sm:p-6" data-testid="desk-status-panel">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Label>Status</Label>
        <button onClick={sweep} disabled={sweeping} data-testid="desk-sweep-button"
          className="inline-flex items-center gap-2 border border-[#23232a] px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest text-[#8a8a94] transition-colors hover:border-[#c6f24e] hover:text-[#c6f24e] disabled:opacity-50">
          <Timer className="h-3.5 w-3.5" /> {sweeping ? "Sweeping…" : "Run sweep now"}
        </button>
      </div>
      <div className="mt-2 grid gap-x-8 md:grid-cols-3">
        <Item label="Mode" testid="desk-status-mode">{s.mode.toUpperCase()} · payments {s.payments_configured ? "configured" : "not configured"}</Item>
        <Item label="Webhook secret set" testid="desk-status-secret-set"><Yes on={s.webhook_secret_set} /></Item>
        <Item label="Stripe endpoint" testid="desk-status-endpoint">{ep ? (ep.error ? <span className="text-[#ff5555]">{ep.error}</span> : `${ep.status} · ${ep.enabled_events.length} events`) : "not registered"}</Item>
        <div className="min-w-0 border-b border-[#23232a] py-3 md:col-span-3">
          <Label>Webhook URL — paste into Stripe</Label>
          <div className="mt-1 flex items-center gap-3">
            <code data-testid="desk-webhook-url" className="min-w-0 flex-1 break-all text-sm text-[#c6f24e]">{s.webhook_url}</code>
            <button onClick={copy} data-testid="desk-webhook-url-copy" className="shrink-0 border border-[#23232a] p-2 text-[#8a8a94] transition-colors hover:border-[#c6f24e] hover:text-[#c6f24e]" aria-label="Copy webhook URL">
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            </button>
          </div>
        </div>
        <Item label="Last webhook received" testid="desk-status-last-webhook">
          {s.last_webhook_at ? <>{when(s.last_webhook_at)}<br /><span className="text-[#8a8a94]">{s.last_webhook_type} · via {s.last_webhook_path}</span></> : "never"}
        </Item>
        <Item label="Last delivery to this URL" testid="desk-status-primary-webhook">
          {s.primary_last_at ? <>{when(s.primary_last_at)}<br /><span className="text-[#8a8a94]">{s.primary_last_type}</span></> : "never"}
        </Item>
        <Item label="Unresolved events" testid="desk-status-unresolved-count">
          <span className={s.unresolved_count ? "text-[#ffb86c]" : ""}>{s.unresolved_count}</span>
        </Item>
        <Item label="Sweep" testid="desk-status-sweep">every {Math.round(s.sweep_interval_seconds / 60)} min · holds {s.hold_minutes} min<br /><span className="text-[#8a8a94]">last {when(s.sweep_last_run)}</span></Item>
        <Item label="Stripe account (secret key)" testid="desk-status-stripe-account">
          {s.stripe_account?.id || s.stripe_account?.error || "—"}<br /><span className="text-[#8a8a94]">{s.mode} mode · live payments {s.mode === "live" ? "on" : "off"}</span>
        </Item>
        <Item label="Signature failures" testid="desk-status-sig-failures">
          {s.sig_failures}<br /><span className="text-[#8a8a94]">last {when(s.last_sig_failure_at)}</span>
        </Item>
      </div>
      <div className="mt-4 border-t border-[#23232a] pt-4" data-testid="desk-webhook-secrets">
        <Label>Webhook signing secrets (values never shown)</Label>
        <div className="mt-2 divide-y divide-[#23232a]">
          {s.webhook_secrets.map((w) => (
            <div key={w.label} data-testid={`desk-secret-${w.label}`} className="grid grid-cols-2 gap-2 py-2.5 font-mono text-xs md:grid-cols-[0.6fr_0.4fr_1.2fr_1.4fr]">
              <span className="text-[#e9e9ee]">{w.label}</span>
              <span>set: <Yes on={w.set} /></span>
              <span className="text-[#8a8a94]">{w.last_at ? `${when(w.last_at)} · ${w.livemode ? "livemode" : "test"}` : "no verified delivery"}</span>
              <span className="break-all text-[#8a8a94]">{w.type ? `${w.type} → ${w.outcome || "…"}` : ""}</span>
            </div>
          ))}
        </div>
      </div>
      {unresolved.length > 0 && (
        <details className="mt-4" data-testid="desk-unresolved-list">
          <summary className="cursor-pointer font-mono text-xs uppercase tracking-widest text-[#ffb86c]">Show unresolved events</summary>
          <ul className="mt-3 space-y-2">
            {unresolved.map((u) => (
              <li key={u.event_id} className="break-all border-l-2 border-[#ffb86c]/50 pl-3 font-mono text-xs">
                <span className="text-[#e9e9ee]">{u.type}</span> <span className="text-[#55555e]">{u.event_id}</span><br />
                <span className="text-[#8a8a94]">{u.detail}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
};
