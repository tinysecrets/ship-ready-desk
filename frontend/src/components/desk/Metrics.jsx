import { Label } from "../Shell";
import { usd } from "../../lib/api";

const Tile = ({ label, value, sub, signal, testid }) => (
  <div className="border border-[#23232a] bg-[#121216] p-5 sm:p-6">
    <Label>{label}</Label>
    <div data-testid={testid} className={`mt-3 font-mono tnum text-3xl font-bold tracking-tight sm:text-4xl ${signal ? "text-[#c6f24e]" : ""}`}>{value}</div>
    {sub && <div className="mt-2 font-mono text-[11px] text-[#8a8a94]">{sub}</div>}
  </div>
);

const Line = ({ label, value, testid, neg }) => (
  <div className="flex items-baseline justify-between gap-4 border-b border-dashed border-[#23232a] py-2.5">
    <span className="text-sm text-[#8a8a94]">{label}</span>
    <span data-testid={testid} className={`font-mono tnum text-sm ${neg ? "text-[#ff8a8a]" : ""}`}>{value}</span>
  </div>
);

export const Metrics = ({ s }) => {
  const pct = Math.max(0, Math.min(100, (s.contribution_cents / s.target_cents) * 100));
  return (
    <div className="mt-10 space-y-4">
      <div className="grid gap-4 md:grid-cols-[1.6fr_1fr_1fr]">
        <div className="border border-[#23232a] bg-[#121216] p-5 sm:p-6">
          <Label>Contribution vs target</Label>
          <div data-testid="desk-contribution-metric"
            className={`mt-3 font-mono tnum text-4xl font-bold tracking-tighter sm:text-5xl ${s.contribution_cents < 0 ? "text-[#ff5555]" : "text-[#c6f24e]"}`}>
            {usd(s.contribution_cents)}
          </div>
          <div className="mt-4 h-1.5 w-full bg-[#23232a]"><div className="h-full bg-[#c6f24e] transition-[width] duration-700" style={{ width: `${pct}%` }} /></div>
          <div className="mt-2 flex justify-between font-mono text-[11px] text-[#8a8a94]">
            <span>ledger-derived</span><span>target <span data-testid="desk-target-value">{usd(s.target_cents)}</span></span>
          </div>
        </div>
        <Tile label="Closes booked" value={s.closes_booked} sub={`${s.closes_net} net of full refunds`} testid="desk-closes-booked-metric" />
        <Tile label="Closes remaining" value={s.closes_remaining} sub={`to ${usd(s.target_cents)} at ${usd(s.money.contribution_per_close_cents)}/close`} testid="desk-closes-remaining-metric" />
      </div>
      <div className="border border-[#23232a] p-5 sm:p-6" data-testid="desk-breakdown">
        <Label>Breakdown ({s.mode})</Label>
        <div className="mt-3 grid gap-x-10 md:grid-cols-2">
          <div>
            <Line label="Gross" value={usd(s.gross_cents)} testid="desk-gross-value" />
            <Line label="Refunds" value={usd(s.refunds_cents)} testid="desk-refunds-value" neg={s.refunds_cents < 0} />
            <Line label="Disputes (net)" value={usd(s.disputes_net_cents)} testid="desk-disputes-value" neg={s.disputes_net_cents < 0} />
            <Line label="Dispute debits / reversals" value={`${usd(s.disputes_cents)} / ${usd(s.dispute_reversals_cents)}`} testid="desk-dispute-detail-value" />
          </div>
          <div>
            <Line label="Fees (estimated)" value={usd(-s.fees_est_cents)} testid="desk-fees-est-value" neg={s.fees_est_cents > 0} />
            <Line label={`Fees (actual, ${s.fees_actual_known} known)`} value={usd(-s.fees_actual_cents)} testid="desk-fees-actual-value" />
            <Line label="Compute" value={usd(-s.compute_cents)} testid="desk-compute-value" neg={s.compute_cents > 0} />
            <Line label="Ledger rows" value={s.ledger_rows} testid="desk-ledger-rows-value" />
          </div>
        </div>
      </div>
    </div>
  );
};
