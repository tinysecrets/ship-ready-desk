from conftest import new_order, sim, order, ledger, wait_for, key
def test_partial_then_full_and_cap(op):
    oid = new_order("refund")
    print(sim("real-pay", oid))
    assert wait_for(lambda: order(oid)["state"] == "paid", 90), "real payment webhook never booked"
    k = key("ref")
    r1 = op.post(f"/desk/orders/{oid}/refund", json={"amount_cents": 10000}, headers={"x-idem-key": k})
    r2 = op.post(f"/desk/orders/{oid}/refund", json={"amount_cents": 10000}, headers={"x-idem-key": k})
    assert r1.status_code == 200, r1.text
    assert r2.json()["replayed"] is True and r2.json()["refund_id"] == r1.json()["refund_id"]
    assert wait_for(lambda: len(ledger(oid, "refund")) == 1, 90)
    assert ledger(oid, "refund")[0]["amount_cents"] == -10000 and order(oid)["state"] == "paid"
    r3 = op.post(f"/desk/orders/{oid}/refund", json={"amount_cents": 999999}, headers={"x-idem-key": key("ref")})
    assert r3.status_code == 200 and r3.json()["amount_cents"] == 99000 and r3.json()["capped"] is True
    assert wait_for(lambda: order(oid)["slot"] == "released", 90)
    o = order(oid); assert o["state"] == "refunded"
    import httpx; from conftest import API
    assert httpx.get(f"{API}/certificates/{o['cert_code']}").json()["revoked"] is True
    rows = ledger(oid)
    contrib = sum(r["amount_cents"] - r.get("fee_est_cents", 0) - r.get("compute_cents", 0) for r in rows)
    print("rows", [(r["kind"], r["amount_cents"], r.get("fee_est_cents"), r.get("compute_cents")) for r in rows], contrib)
    assert len(ledger(oid, "refund")) == 2
    assert contrib == -5191, contrib
