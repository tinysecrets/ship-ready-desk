import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LogOut, PenLine, RefreshCw } from "lucide-react";
import { Shell, Label, Badge, Disclaimer } from "../components/Shell";
import { api } from "../lib/api";
import { Metrics } from "../components/desk/Metrics";
import { OrdersTable } from "../components/desk/OrdersTable";
import { StatusPanel } from "../components/desk/StatusPanel";
import { GoLive } from "../components/desk/GoLive";

export default function Desk() {
  const navigate = useNavigate();
  const [ok, setOk] = useState(false);
  const [data, setData] = useState({ summary: null, orders: null, status: null, unresolved: [] });

  const load = useCallback(async () => {
    try {
      const [s, o, st, u] = await Promise.all([api.get("/desk/summary"), api.get("/desk/orders"), api.get("/desk/status"), api.get("/desk/unresolved")]);
      setData({ summary: s.data, orders: o.data.orders, status: st.data, unresolved: u.data.events });
      setOk(true);
    } catch (e) {
      if (e?.response?.status === 401) navigate("/access", { replace: true });
    }
  }, [navigate]);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  const logout = async () => { await api.post("/auth/logout"); navigate("/access"); };

  if (!ok) return <Shell><p className="py-20 font-mono text-xs text-[#8a8a94]" data-testid="desk-loading">checking access…</p></Shell>;
  const { summary, orders, status, unresolved } = data;

  return (
    <Shell>
      <section className="py-12 sm:py-16" data-testid="desk-page">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-3"><Label>Operator desk</Label><Badge kind={summary.mode} testid="desk-mode-badge">{summary.mode.toUpperCase()}</Badge></div>
            <h1 className="mt-4 text-4xl font-black tracking-tight sm:text-5xl">The numbers.</h1>
          </div>
          <div className="flex gap-2">
            <Link to="/desk/drafts" data-testid="desk-drafts-link" className="inline-flex items-center gap-2 bg-[#c6f24e] px-4 py-2 font-mono text-xs font-bold uppercase tracking-widest text-[#0b0b0d] transition-colors hover:bg-[#b2df3b]">
              <PenLine className="h-3.5 w-3.5" /> Drafts
            </Link>
            <button onClick={load} data-testid="desk-refresh-button" className="inline-flex items-center gap-2 border border-[#23232a] px-4 py-2 font-mono text-xs uppercase tracking-widest text-[#8a8a94] transition-colors hover:border-[#8a8a94] hover:text-[#e9e9ee]">
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </button>
            <button onClick={logout} data-testid="desk-logout-button" className="inline-flex items-center gap-2 border border-[#23232a] px-4 py-2 font-mono text-xs uppercase tracking-widest text-[#8a8a94] transition-colors hover:border-[#8a8a94] hover:text-[#e9e9ee]">
              <LogOut className="h-3.5 w-3.5" /> Out
            </button>
          </div>
        </div>
        <div className="mt-3"><Disclaimer testid="desk-disclaimer" /></div>
        <Metrics s={summary} />
        <StatusPanel status={status} unresolved={unresolved} onChange={load} />
        <GoLive checklist={status.go_live_checklist} onChange={load} />
        <OrdersTable orders={orders} onChange={load} />
      </section>
    </Shell>
  );
}
