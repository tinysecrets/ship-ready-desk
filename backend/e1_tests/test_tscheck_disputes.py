from conftest import new_order, sim, ledger
def test_dispute_won_nets_zero():
    oid = new_order("disp"); sim("paid", oid)
    sim("refund", oid, "9000")
    did = "dp_tscheck_" + oid
    sim("dispute", oid, "109000", "--id", did)
    deb = [r for r in ledger(oid) if r["kind"].startswith("dispute") and r["amount_cents"] < 0]
    assert len(deb) == 1 and deb[0]["amount_cents"] == -100000, deb
    sim("dispute-closed", oid, "--id", did, "--status", "won")
    d = [r for r in ledger(oid) if r["kind"].startswith("dispute")]
    assert sum(r["amount_cents"] for r in d) == 0 and len(d) == 2, d
    sim("refund", oid, "100000")
