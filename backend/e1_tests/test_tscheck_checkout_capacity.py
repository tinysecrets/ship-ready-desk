import httpx, concurrent.futures as cf
from conftest import API, key, sim, order, db
def test_checkout_idem_and_missing_key():
    k = key("idem")
    r1 = httpx.post(f"{API}/ships/shipready-sprint/checkout", headers={"x-idem-key": k}, timeout=60)
    if r1.status_code == 409: import pytest; pytest.skip("full")
    r2 = httpx.post(f"{API}/ships/shipready-sprint/checkout", headers={"x-idem-key": k}, timeout=60)
    assert r1.status_code == 200 and r1.json()["url"].startswith("https://checkout.stripe.com/")
    assert r1.json()["orderId"] == r2.json()["orderId"] and r1.json()["sessionId"] == r2.json()["sessionId"]
    assert order(r1.json()["orderId"])["slot"] in ("reserved", "held") or order(r1.json()["orderId"])["state"] == "reserved"
    sim("expire", r1.json()["orderId"])
    assert httpx.post(f"{API}/ships/shipready-sprint/checkout", timeout=30).status_code == 400
def test_concurrent_never_oversell():
    def go(_): return httpx.post(f"{API}/ships/shipready-sprint/checkout", headers={"x-idem-key": key("conc")}, timeout=90)
    with cf.ThreadPoolExecutor(8) as ex: rs = list(ex.map(go, range(8)))
    codes = [r.status_code for r in rs]
    ok = [r.json()["orderId"] for r in rs if r.status_code == 200]
    try:
        assert set(codes) <= {200, 409}, codes
        assert 409 in codes
        ship = db.ships.find_one({"slug": "shipready-sprint"})
        used = db.orders.count_documents({"ship_id": ship["_id"], "mode": "test", "slot": {"$in": ["reserved", "sold"]}})
        assert used <= 3, used
    finally:
        for o in ok: sim("expire", o)
