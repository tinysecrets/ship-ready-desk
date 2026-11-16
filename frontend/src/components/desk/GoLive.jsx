import { useState } from "react";
import { toast } from "sonner";
import { Check, X } from "lucide-react";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "../ui/alert-dialog";
import { Label } from "../Shell";
import { api, errMsg } from "../../lib/api";

export const GoLive = ({ checklist, onChange }) => {
  const [busy, setBusy] = useState(false);
  const reset = async () => {
    setBusy(true);
    try {
      const r = await api.post("/desk/reset-test", { confirm: "RESET TEST" });
      const d = r.data.deleted;
      toast(`Test data wiped: ${d.orders} orders, ${d.ledger} ledger rows, ${d.certificates} certificates. Live data untouched.`);
      onChange();
    } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };

  return (
    <div className="mt-4 grid gap-4 md:grid-cols-[1.6fr_1fr]">
      <div className="border border-[#23232a] p-5 sm:p-6" data-testid="desk-go-live-checklist">
        <Label>Go-live checklist</Label>
        <ul className="mt-3 divide-y divide-[#23232a]">
          {checklist.map((c) => (
            <li key={c.key} data-testid={`go-live-item-${c.key}`} className="flex items-start gap-3 py-3">
              <span className={`mt-0.5 shrink-0 ${c.ok ? "text-[#c6f24e]" : "text-[#ff5555]"}`}>{c.ok ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}</span>
              <div className="min-w-0">
                <div className="text-sm">{c.label}: <span data-testid={`go-live-state-${c.key}`} className={`font-mono ${c.ok ? "text-[#c6f24e]" : "text-[#ff8a8a]"}`}>{c.ok ? "yes" : "no"}</span></div>
                <div className="break-all font-mono text-[11px] text-[#8a8a94]">{c.detail}</div>
              </div>
            </li>
          ))}
        </ul>
      </div>
      <div className="border border-[#ff5555]/30 p-5 sm:p-6" data-testid="desk-reset-panel">
        <Label>Test data</Label>
        <p className="mt-3 text-sm text-[#8a8a94]">Deletes TEST-mode orders, ledger rows, certificates, refund requests and webhook inbox entries, and resets test slot counters. Live data is never touched.</p>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <button disabled={busy} data-testid="desk-reset-test-button"
              className="mt-4 border border-[#ff5555]/50 px-4 py-2 font-mono text-[11px] uppercase tracking-widest text-[#ff8a8a] transition-colors hover:bg-[#ff5555] hover:text-white disabled:opacity-50">
              {busy ? "Resetting…" : "Reset test data"}
            </button>
          </AlertDialogTrigger>
          <AlertDialogContent className="rounded-none border-[#23232a] bg-[#121216] text-[#e9e9ee]" data-testid="reset-confirm-dialog">
            <AlertDialogHeader>
              <AlertDialogTitle>Wipe all test-mode data?</AlertDialogTitle>
              <AlertDialogDescription className="text-[#8a8a94]">This cannot be undone. Live orders, ledger and certificates stay exactly as they are.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel data-testid="reset-cancel-button" className="rounded-none border-[#23232a] bg-transparent">Cancel</AlertDialogCancel>
              <AlertDialogAction data-testid="reset-confirm-button" onClick={reset} className="rounded-none bg-[#ff5555] text-white hover:bg-[#e04848]">Reset test data</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  );
};
