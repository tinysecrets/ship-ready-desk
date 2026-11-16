# Shipready Phase 1 regression: health, checkout, webhook (signed sim), ledger, disputes, sweep, desk auth, real refunds.
# Run serially (shared slot state): pytest /app/backend/tests/test_shipready_phase1.py -n 0 -v
import concurrent.futures as cf
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta, timezone

FRONT = dotenv_values("/app/frontend/.env")
BACK = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONT["REACT_APP_BACKEND_URL"]).rstrip("/")
API = f"{BASE_URL}/api"
SLUG = "shipready-sprint"
SECRET = re.search(r"`([0-9a-f]{64})`", Path("/app/memory/test_credentials.md").read_text()).group(1)
CODE_RE = re.compile(r"^SR-[0-9A-HJKMNP-TV-Z]{12}$")
DB = MongoClient(BACK["MONGO_URL"])[BACK["DB_NAME"]]
SIM = "/app/scripts/stripe_sim.py"

created_orders: list = []


def sim(*args):
    out = subprocess.run([sys.executable, SIM, *args], capture_output=True, text=True, timeout=60)
    text = out.stdout + out.stderr
    first = text.strip().splitlines()[0] if text.strip() else ""
    return text, first


def idem():
    return f"TEST_{uuid.uuid4().hex}"


def checkout(key=None):
    h = {"x-idem-key": key} if key else {}
    return requests.post(f"{API}/ships/{SLUG}/checkout", headers=h, json={}, timeout=30)


def open_count():
    return requests.get(f"{API}/ships/{SLUG}", timeout=15).json()["open"]


def new_order():
    r = checkout(idem())
    assert r.status_code == 200, r.text
    oid = r.json()["orderId"]
    created_orders.append(oid)
    return oid


def order(oid):
    return DB.orders.find_one({"_id": ObjectId(oid)})


def ledger_rows(oid):
    return list(DB.ledger.find({"order_id": {"$in": [oid, ObjectId(oid)]}}))


@pytest.fixture(scope="module")
def op():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"secret": SECRET}, timeout=15)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for oid in created_orders:
        o = order(oid)
        if o and o["state"] == "reserved":
            sim("expire", oid)


# --- Health / spec / money (JRN-25, REQ-1..3)
def test_health_openapi_money():
    assert requests.get(f"{API}/health").json() == {"ok": True}
    spec = requests.get(f"{API}/openapi.json").json()
    assert "openapi" in spec and "/api/webhooks/stripe" in spec["paths"]
    m = requests.get(f"{API}/money").json()
    assert m["contribution_per_close_cents"] == 103809 and m["full_refund_contribution_cents"] == -5191 and m["closes_for_floor"] == 1


def test_ship_and_404():
    s = requests.get(f"{API}/ships/{SLUG}").json()
    assert s["title"] == "Shipready Sprint" and s["price_cents"] == 109000 and s["slots"] == 3 and s["mode"] == "test"
    assert requests.get(f"{API}/ships/not-a-ship").status_code == 404
    assert requests.get(f"{API}/certificates/SR-NOTREAL00000").status_code == 404


# --- Desk auth (JRN-15/16, Q-4)
def test_desk_unauth_401():
    for m, p in [("get", "/desk/summary"), ("get", "/desk/orders"), ("get", "/desk/status"), ("get", "/desk/unresolved"),
                 ("post", "/desk/sweep"), ("post", "/desk/orders/6afb39fb52e65336214190c9/refund"), ("get", "/auth/me")]:
        r = getattr(requests, m)(f"{API}{p}", json={}, headers={"x-idem-key": "abcdefgh123"})
        assert r.status_code == 401, (p, r.status_code)


def test_login_wrong_secret_and_cookie(op):
    r = requests.post(f"{API}/auth/login", json={"secret": "nope"})
    assert r.status_code == 401 and r.json()["detail"] == "Wrong secret."
    r2 = requests.post(f"{API}/auth/login", json={"secret": SECRET})
    sc = r2.headers.get("set-cookie", "")
    assert "__Host-operator_session" in sc and "HttpOnly" in sc and "Max-Age=28800" in sc
    # Preview ingress rewrites SameSite -> None; Partitioned. Verify backend's own header via localhost.
    local = requests.post("http://localhost:8001/api/auth/login", json={"secret": SECRET}).headers.get("set-cookie", "")
    assert "samesite=strict" in local.lower() and "Secure" in local and "HttpOnly" in local
    assert op.get(f"{API}/auth/me").status_code == 200


# --- Checkout (JRN-4/5, Q-6)
def test_checkout_idem_and_validation():
    assert checkout().status_code == 400
    assert checkout("short").status_code == 400
    before = open_count()
    key = idem()
    t0 = time.time()
    r1 = checkout(key)
    elapsed = (time.time() - t0) * 1000
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    created_orders.append(d1["orderId"])
    assert d1["url"].startswith("https://checkout.stripe.com") and d1["state"] == "reserved"
    r2 = checkout(key)
    assert r2.json()["orderId"] == d1["orderId"] and r2.json()["sessionId"] == d1["sessionId"]
    assert open_count() == before - 1
    print(f"checkout latency ms: {elapsed:.0f}")
    assert elapsed < 4000
    # expire -> slot released (JRN-12)
    text, first = sim("expire", d1["orderId"])
    assert first.startswith("200") and '"processed"' in first, text
    assert order(d1["orderId"])["state"] == "expired"
    assert open_count() == before


# --- Webhook signature / unknown (JRN-9/11, Q-5)
def test_bad_sig_and_unknown_pi(op):
    text, first = sim("bad-sig")
    assert first.startswith("400"), text
    u0 = op.get(f"{API}/desk/status").json()["unresolved_count"]
    text, first = sim("unknown-pi")
    assert first.startswith("200") and "unresolved" in first, text
    assert op.get(f"{API}/desk/status").json()["unresolved_count"] == u0 + 1


# --- Mismatch, paid, replay, cert, dispute, full refund (JRN-7,8,10,22, Q-1, Q-3)
def test_full_money_flow(op):
    s0 = op.get(f"{API}/desk/summary").json()
    oid = new_order()
    for extra in (["--amount", "100"], ["--currency", "eur"], ["--namespace", "other"], ["--livemode"]):
        text, first = sim("paid", oid, *extra)
        assert first.startswith("200") and "unresolved" in first, (extra, text)
        assert order(oid)["state"] == "reserved" and ledger_rows(oid) == []
    text, first = sim("paid", oid)
    assert "processed" in first, text
    eid = re.search(r"event_id: (\S+)", text).group(1)
    o = order(oid)
    assert o["state"] == "paid" and o["slot"] == "sold" and CODE_RE.match(o["cert_code"])
    code = o["cert_code"]
    for _ in range(5):
        _, f = sim("paid", oid, "--event-id", eid)
        assert '"replay"' in f
    assert len([r for r in ledger_rows(oid) if r["kind"] == "charge"]) == 1
    s1 = op.get(f"{API}/desk/summary").json()
    assert s1["contribution_cents"] - s0["contribution_cents"] == 103809
    assert s1["closes_booked"] == s0["closes_booked"] + 1
    assert s1["closes_remaining"] == 0
    proof = requests.get(f"{API}/proof").json()["certificates"]
    assert proof[0]["code"] == code and proof[0]["mode"] == "test" and proof[0]["revoked"] is False
    c = requests.get(f"{API}/certificates/{code}").json()
    assert c["verified_contribution_cents"] == 103809 and c["revoked"] is False
    # Dispute then won
    dp = f"dp_TEST{uuid.uuid4().hex[:10]}"
    text, f = sim("dispute", oid, "109000", "--id", dp)
    assert "processed" in f, text
    s2 = op.get(f"{API}/desk/summary").json()
    assert s2["disputes_net_cents"] - s1["disputes_net_cents"] == -109000
    assert order(oid)["state"] == "disputed"
    text, f = sim("dispute-closed", oid, "--id", dp, "--status", "won")
    assert "processed" in f, text
    s3 = op.get(f"{API}/desk/summary").json()
    assert s3["disputes_net_cents"] == s1["disputes_net_cents"]
    assert order(oid)["state"] == "disputed"
    # Full refund via signed event (fake PI, not desk-created) -> -5191 for this order, revoked, slot released
    before_open = open_count()
    text, f = sim("refund", oid, "109000", "--id", f"re_TEST{uuid.uuid4().hex[:10]}")
    assert "processed" in f, text
    o = order(oid)
    assert o["state"] == "refunded" and o["slot"] == "released"
    c = requests.get(f"{API}/certificates/{code}").json()
    assert c["revoked"] is True and c["verified_contribution_cents"] == -5191
    assert open_count() == before_open + 1
    s4 = op.get(f"{API}/desk/summary").json()
    assert s4["contribution_cents"] - s0["contribution_cents"] == -5191


# --- async_payment_failed (JRN-13)
def test_async_failed_releases():
    before = open_count()
    oid = new_order()
    assert open_count() == before - 1
    text, f = sim("async-failed", oid)
    assert "processed" in f, text
    assert order(oid)["state"] == "expired" and open_count() == before


# --- Sweep (JRN-14)
def test_sweep_expires(op):
    before = open_count()
    oid = new_order()
    DB.orders.update_one({"_id": ObjectId(oid)}, {"$set": {"hold_expires_at": datetime.now(timezone.utc) - timedelta(minutes=46)}})
    r = op.post(f"{API}/desk/sweep").json()
    assert r["expired"] >= 1, r
    assert order(oid)["state"] == "expired" and open_count() == before


# --- Oversell (JRN-6, Q-2)
def test_concurrent_no_oversell():
    before = open_count()
    with cf.ThreadPoolExecutor(10) as ex:
        res = list(ex.map(lambda _: checkout(idem()), range(10)))
    ok = [r for r in res if r.status_code == 200]
    sold = [r for r in res if r.status_code == 409]
    for r in ok:
        created_orders.append(r.json()["orderId"])
    assert len(ok) == before and len(sold) == 10 - before
    assert all(r.json()["detail"] == "sold out" for r in sold)
    assert open_count() == 0
    s = DB.ships.find_one({"slug": SLUG})["counters"]["test"]
    assert s["sold"] + s["reserved"] <= 3
    for r in ok:
        sim("expire", r.json()["orderId"])
    assert open_count() == before


# --- Real Stripe payment + desk refunds (JRN-18..21)
def wait_for(fn, timeout=40):
    end = time.time() + timeout
    while time.time() < end:
        if fn():
            return True
        time.sleep(2)
    return False


def test_real_refund_flow(op):
    oid = new_order()
    text, _ = sim("real-pay", oid)
    assert "succeeded" in text, text
    assert wait_for(lambda: order(oid)["state"] == "paid"), "Stripe webhook did not book charge"
    code = order(oid)["cert_code"]
    s0 = op.get(f"{API}/desk/summary").json()
    key = idem()
    r1 = op.post(f"{API}/desk/orders/{oid}/refund", json={"amount_cents": 10000}, headers={"x-idem-key": key})
    assert r1.status_code == 200 and r1.json()["replayed"] is False, r1.text
    r2 = op.post(f"{API}/desk/orders/{oid}/refund", json={"amount_cents": 10000}, headers={"x-idem-key": key})
    assert r2.json()["replayed"] is True and r2.json()["refund_id"] == r1.json()["refund_id"]
    assert wait_for(lambda: order(oid)["refunded_cents"] == 10000), "refund webhook not booked"
    time.sleep(5)
    assert order(oid)["refunded_cents"] == 10000 and order(oid)["state"] == "paid"
    assert requests.get(f"{API}/certificates/{code}").json()["revoked"] is False
    s1 = op.get(f"{API}/desk/summary").json()
    assert s1["refunds_cents"] - s0["refunds_cents"] == -10000
    before_open = open_count()
    r3 = op.post(f"{API}/desk/orders/{oid}/refund", json={"amount_cents": 5000000}, headers={"x-idem-key": idem()})
    assert r3.status_code == 200 and r3.json()["amount_cents"] == 99000 and r3.json()["capped"] is True, r3.text
    assert wait_for(lambda: order(oid)["state"] == "refunded"), "full refund not booked"
    assert requests.get(f"{API}/certificates/{code}").json()["revoked"] is True
    assert requests.get(f"{API}/certificates/{code}").json()["verified_contribution_cents"] == -5191
    assert open_count() == before_open + 1
    r4 = op.post(f"{API}/desk/orders/{oid}/refund", json={}, headers={"x-idem-key": idem()})
    assert r4.status_code == 409
