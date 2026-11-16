import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Loader2, Trash2 } from "lucide-react";
import { Shell, Label } from "../components/Shell";
import { api, errMsg } from "../lib/api";
import { DraftCard } from "../components/drafts/DraftCard";

const ProspectRow = ({ p, onDraft, onDelete, busy }) => (
  <div data-testid={`prospect-row-${p.id}`} className="flex flex-wrap items-center justify-between gap-3 border-b border-[#23232a] py-3">
    <div className="min-w-0">
      <div className="font-mono text-sm text-[#e9e9ee]" data-testid={`prospect-handle-${p.id}`}>{p.handle}</div>
      <div className="text-xs text-[#8a8a94]">{p.reason || "no note"}</div>
    </div>
    <div className="flex gap-2">
      <button onClick={() => onDraft(p)} disabled={busy} data-testid={`prospect-write-outreach-${p.id}`}
        className="inline-flex items-center gap-2 bg-[#c6f24e] px-3 py-1.5 text-xs font-bold text-[#0b0b0d] transition-colors hover:bg-[#b2df3b] disabled:opacity-50">
        {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />} {busy ? "Writing…" : "Write outreach"}
      </button>
      <button onClick={() => onDelete(p)} aria-label="Remove prospect" data-testid={`prospect-delete-${p.id}`}
        className="border border-[#23232a] p-1.5 text-[#8a8a94] transition-colors hover:border-[#ff5555] hover:text-[#ff5555]">
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  </div>
);

export default function Drafts() {
  const navigate = useNavigate();
  const [ok, setOk] = useState(false);
  const [text, setText] = useState("");
  const [prospects, setProspects] = useState([]);
  const [drafts, setDrafts] = useState([]);
  const [busyId, setBusyId] = useState(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [p, d] = await Promise.all([api.get("/desk/prospects"), api.get("/desk/drafts")]);
      setProspects(p.data.prospects);
      setDrafts(d.data.drafts);
      setOk(true);
    } catch (e) {
      if (e?.response?.status === 401) navigate("/access", { replace: true });
    }
  }, [navigate]);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    if (!text.trim()) return;
    try {
      const r = await api.post("/desk/prospects", { text });
      setNotice(`${r.data.created.length} saved · ${r.data.skipped} lines skipped`);
      setText("");
      load();
    } catch (e) { toast.error(errMsg(e)); }
  };
  const draft = async (p) => {
    setBusyId(p.id);
    setError("");
    try {
      await api.post(`/desk/prospects/${p.id}/outreach`);
      toast("Draft written. Nothing was sent.");
      load();
    } catch (e) { setError(errMsg(e, "Draft failed — try again")); } finally { setBusyId(null); }
  };
  const remove = async (p) => { await api.delete(`/desk/prospects/${p.id}`); load(); };

  if (!ok) return <Shell><p className="py-20 font-mono text-xs text-[#8a8a94]">checking access…</p></Shell>;

  return (
    <Shell>
      <section className="py-12 sm:py-16" data-testid="drafts-page">
        <Link to="/desk" className="font-mono text-xs uppercase tracking-widest text-[#8a8a94] hover:text-[#e9e9ee]" data-testid="drafts-back-link">← Desk</Link>
        <h1 className="mt-4 text-4xl font-black tracking-tight sm:text-5xl">Drafts outbox.</h1>
        <p className="mt-3 max-w-2xl text-sm text-[#8a8a94]">
          Claude writes, you edit and approve. Nothing here is ever sent, posted or emailed — approved drafts are for you to copy and send yourself.
        </p>
        <div className="mt-10 grid gap-6 lg:grid-cols-[1fr_1.4fr]">
          <div className="space-y-4">
            <div className="border border-[#23232a] p-5">
              <Label>Paste prospects — one per line: handle | reason</Label>
              <textarea data-testid="prospects-textarea" value={text} onChange={(e) => setText(e.target.value)} rows={5}
                placeholder={"alice | replied twice\nbob | runs an agency"}
                className="mt-3 w-full resize-y border border-[#23232a] bg-[#121216] p-3 font-mono text-sm placeholder:text-[#3d3d45] focus:border-[#c6f24e] focus:outline-none" />
              <div className="mt-3 flex flex-wrap items-center gap-4">
                <button onClick={save} data-testid="prospects-save-button"
                  className="bg-[#c6f24e] px-5 py-2.5 text-sm font-bold text-[#0b0b0d] transition-colors hover:bg-[#b2df3b]">Save prospects</button>
                {notice && <span data-testid="prospects-notice" className="font-mono text-xs text-[#8a8a94]">{notice}</span>}
              </div>
            </div>
            <div className="border border-[#23232a] p-5" data-testid="prospects-list">
              <Label>Prospects ({prospects.length})</Label>
              {error && <p data-testid="draft-error-message" className="mt-3 font-mono text-sm text-[#ff5555]">{error}</p>}
              {prospects.length === 0 && <p className="mt-3 font-mono text-xs text-[#8a8a94]">No prospects yet.</p>}
              {prospects.map((p) => <ProspectRow key={p.id} p={p} onDraft={draft} onDelete={remove} busy={busyId === p.id} />)}
            </div>
          </div>
          <div className="border border-[#23232a]" data-testid="drafts-list">
            <div className="border-b border-[#23232a] bg-[#121216] px-5 py-3"><Label>Outbox ({drafts.length})</Label></div>
            {drafts.length === 0 && <p data-testid="drafts-empty" className="px-5 py-8 font-mono text-sm text-[#8a8a94]">No drafts yet.</p>}
            {drafts.map((d) => <DraftCard key={d.id} d={d} onChange={load} />)}
          </div>
        </div>
      </section>
    </Shell>
  );
}
