import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy } from "lucide-react";
import { api, when, errMsg } from "../../lib/api";

const STATUS = { draft: "text-[#ffb86c]", approved: "text-[#c6f24e]", discarded: "text-[#55555e]" };
const btn = "border border-[#23232a] px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest transition-colors disabled:opacity-40";

export const DraftCard = ({ d, onChange }) => {
  const [text, setText] = useState(d.text);
  useEffect(() => setText(d.text), [d.text]);
  const dirty = text !== d.text;

  const act = async (fn, msg) => {
    try { await fn(); toast(msg); onChange(); } catch (e) { toast.error(errMsg(e)); }
  };
  const save = () => act(() => api.patch(`/desk/drafts/${d.id}`, { text }), "Saved.");
  const approve = () => act(() => api.post(`/desk/drafts/${d.id}/approve`), "Approved. Copy it and send it yourself.");
  const discard = () => act(() => api.post(`/desk/drafts/${d.id}/discard`), "Discarded.");
  const copy = () => { navigator.clipboard?.writeText(d.text); toast("Copied to clipboard"); };
  const closed = d.status === "discarded";

  return (
    <div data-testid={`draft-card-${d.id}`} className="border-b border-[#23232a] p-5">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] uppercase tracking-widest">
        <span data-testid={`draft-kind-${d.id}`} className="text-[#e9e9ee]">{d.kind}</span>
        <span data-testid={`draft-target-${d.id}`} className="normal-case text-[#8a8a94]">→ {d.target}</span>
        <span data-testid={`draft-status-${d.id}`} className={STATUS[d.status]}>{d.status}</span>
        <span className="normal-case text-[#55555e]">{when(d.created_at)}</span>
      </div>
      <textarea data-testid={`draft-text-${d.id}`} value={text} onChange={(e) => setText(e.target.value)} disabled={closed} rows={7}
        className="mt-3 w-full resize-y border border-[#23232a] bg-[#0b0b0d] p-3 text-sm leading-relaxed focus:border-[#c6f24e] focus:outline-none disabled:text-[#55555e]" />
      {!closed && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button onClick={save} disabled={!dirty} data-testid={`draft-save-${d.id}`} className={`${btn} text-[#e9e9ee] hover:border-[#8a8a94]`}>Save</button>
          <button onClick={approve} disabled={dirty || d.status === "approved"} data-testid={`draft-approve-${d.id}`} className={`${btn} text-[#c6f24e] hover:border-[#c6f24e]`}>Approve</button>
          {d.status === "approved" && (
            <button onClick={copy} data-testid={`draft-copy-${d.id}`} className={`${btn} inline-flex items-center gap-1.5 bg-[#c6f24e] text-[#0b0b0d] hover:bg-[#b2df3b]`}>
              <Copy className="h-3.5 w-3.5" /> Copy
            </button>
          )}
          <button onClick={discard} data-testid={`draft-discard-${d.id}`} className={`${btn} text-[#ff8a8a] hover:border-[#ff5555]`}>Discard</button>
        </div>
      )}
    </div>
  );
};
