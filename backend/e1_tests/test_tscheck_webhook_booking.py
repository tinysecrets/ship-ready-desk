import re, httpx
from conftest import API, new_order, sim, order, ledger
def test_paid_books_once_and_replay():
    oid = new_order("paid")
    out = sim("paid", oid); ev = re.search(r"event_id: (\S+)", out).group(1)
    for _ in range(5): sim("paid", oid, "--event-id", ev)
    o = order(oid)
    assert o["state"] == "paid" and len(ledger(oid, "charge")) == 1
    assert re.fullmatch(r"SR-[A-Z0-9]{12}", o["cert_code"])
    c = httpx.get(f"{API}/certificates/{o['cert_code']}").json()
    assert c.get("revoked") is False
    sim("refund", oid, "109000")  # free slot (fake refund event, own order)
def test_bad_sig():
    assert "400" in sim("bad-sig")
def test_mismatch_books_nothing():
    for flag in (["--amount", "100"], ["--currency", "eur"], ["--namespace", "other"]):
        oid = new_order("mm")
        sim("paid", oid, *flag)
        assert order(oid)["state"] != "paid" and ledger(oid) == [], flag
        sim("expire", oid)
def test_unknown_pi():
    out = sim("unknown-pi"); assert out.startswith("200") and "unresolved" in out
