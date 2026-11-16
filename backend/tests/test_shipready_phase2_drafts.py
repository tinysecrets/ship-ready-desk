# Shipready Phase 2 regression: prospects, AI outreach/delivery drafts (Claude), honesty checks, edit/approve/discard,
# Q-10 no-side-effects on orders/ledger/certs/ships, auth 401s, go-live checklist, AI failure simulation, openapi.
# Run serially: pytest /app/backend/tests/test_shipready_phase2_drafts.py -n 0 -v
# NOTE: reset-test is NOT exercised here (destructive) — only its auth guard and confirm validation.
import os
import re
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

FRONT = dotenv_values("/app/frontend/.env")
BACK = dotenv_values("/app/backend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or FRONT["REACT_APP_BACKEND_URL"]).rstrip("/")
API = f"{BASE_URL}/api"
SECRET = re.search(r"`([0-9a-f]{64})`", Path("/app/memory/test_credentials.md").read_text()).group(1)
DB = MongoClient(BACK["MONGO_URL"])[BACK["DB_NAME"]]
FORBIDDEN = re.compile(r"guarantee|passive income|make \$|earn \$|\d+x|testimonial|ROI|double your|clients say", re.I)
LINK = f"{BASE_URL}/s/shipready-sprint"
created_prospects: list = []


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    r = sess.post(f"{API}/auth/login", json={"secret": SECRET}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"login failed {r.status_code}")
    yield sess
    for pid in created_prospects:
        sess.delete(f"{API}/desk/prospects/{pid}", timeout=20)


def snapshot():
    ship = DB.ships.find_one({"slug": "shipready-sprint"})
    return {"orders": DB.orders.count_documents({}), "ledger": DB.ledger.count_documents({}),
            "certs": DB.certificates.count_documents({}), "counters": ship.get("counters"),
            "slot_ops": len(ship.get("slot_ops") or []), "inbox": DB.webhook_inbox.count_documents({})}


def paid_order_id():
    o = DB.orders.find_one({"state": "paid", "cert_code": {"$exists": True, "$ne": None}})
    return (str(o["_id"]), o["cert_code"]) if o else (None, None)


# --- auth guard (JRN-34)
@pytest.mark.parametrize("method,path", [
    ("get", "/desk/prospects"), ("post", "/desk/prospects"), ("delete", "/desk/prospects/6afb39fb52e65336214190c9"),
    ("post", "/desk/prospects/6afb39fb52e65336214190c9/outreach"), ("get", "/desk/drafts"),
    ("patch", "/desk/drafts/6afb39fb52e65336214190c9"), ("post", "/desk/drafts/6afb39fb52e65336214190c9/approve"),
    ("post", "/desk/drafts/6afb39fb52e65336214190c9/discard"),
    ("post", "/desk/orders/6afb39fb52e65336214190c9/delivery-note"), ("post", "/desk/reset-test")])
def test_401_without_cookie(method, path):
    r = getattr(requests, method)(f"{API}{path}", json={"text": "x", "confirm": "RESET TEST"}, timeout=20)
    assert r.status_code == 401, f"{method} {path} -> {r.status_code}"


def test_openapi_has_new_routes():
    paths = requests.get(f"{API}/openapi.json", timeout=20).json()["paths"]
    for p in ["/api/desk/prospects", "/api/desk/prospects/{prospect_id}/outreach", "/api/desk/drafts",
              "/api/desk/drafts/{draft_id}", "/api/desk/drafts/{draft_id}/approve", "/api/desk/drafts/{draft_id}/discard",
              "/api/desk/orders/{order_id}/delivery-note", "/api/desk/reset-test"]:
        assert p in paths, p


# --- JRN-27 prospects parsing
def test_add_prospects_parsing(s):
    r = s.post(f"{API}/desk/prospects", json={"text": "TEST_alice | replied twice\nTEST_bob | runs an agency\nbadline"}, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["created"]) == 2 and d["skipped"] == 1
    assert d["message"] == "2 saved · 1 lines skipped"
    created_prospects.extend(p["id"] for p in d["created"])
    listed = {p["id"]: p for p in s.get(f"{API}/desk/prospects", timeout=20).json()["prospects"]}
    for p in d["created"]:
        assert p["id"] in listed
    assert listed[d["created"][0]["id"]]["reason"] == "replied twice"


def test_reset_requires_confirm(s):
    r = s.post(f"{API}/desk/reset-test", json={"confirm": "nope"}, timeout=20)
    assert r.status_code == 400


# --- JRN-37 simulated AI failure
def test_ai_failure_503_no_draft(s):
    pid = created_prospects[0]
    before = DB.drafts.count_documents({})
    r = s.post(f"{API}/desk/prospects/{pid}/outreach", headers={"x-simulate-ai-failure": "1"}, timeout=60)
    assert r.status_code == 503
    assert r.json()["detail"] == "Draft failed — try again"
    assert DB.drafts.count_documents({}) == before


def test_unknown_ids_404(s):
    assert s.post(f"{API}/desk/prospects/000000000000000000000000/outreach", timeout=20).status_code == 404
    assert s.post(f"{API}/desk/orders/notanid/delivery-note", timeout=20).status_code == 404
    assert s.patch(f"{API}/desk/drafts/000000000000000000000000", json={"text": "x"}, timeout=20).status_code == 404


# --- JRN-28 / Q-8 / Q-9 / Q-10: 5 outreach drafts, honesty, no side effects
drafts_made: list = []


def test_outreach_drafts_honest_and_side_effect_free(s):
    import time
    before = snapshot()
    r = s.post(f"{API}/desk/prospects", json={"text": "\n".join(f"TEST_p{i} | note {i}: builds a SaaS side project" for i in range(3))}, timeout=20)
    created_prospects.extend(p["id"] for p in r.json()["created"])
    timings, failures = [], []
    for pid in created_prospects[:5]:
        t = time.time()
        r = s.post(f"{API}/desk/prospects/{pid}/outreach", timeout=90)
        timings.append(round(time.time() - t, 1))
        if r.status_code != 200:
            failures.append((pid, r.status_code, r.text[:200]))
            continue
        d = r.json()
        drafts_made.append(d)
        txt = d["text"]
        print(f"\n--- draft {d['id']} ({timings[-1]}s):\n{txt}")
        assert d["kind"] == "outreach" and d["status"] == "draft" and d["model"] == "claude-sonnet-5-5"
        assert "$1,090" in txt and "3 slots" in txt and LINK in txt
        assert not FORBIDDEN.search(txt), FORBIDDEN.search(txt).group(0)
    print("timings", timings, "failures", failures)
    assert not failures, failures
    assert max(timings) < 30, timings
    assert snapshot() == before


def test_edit_approve_discard_flow(s):
    assert drafts_made, "no drafts"
    did = drafts_made[0]["id"]
    r = s.patch(f"{API}/desk/drafts/{did}", json={"text": "TEST_edited text"}, timeout=20)
    assert r.status_code == 200 and r.json()["text"] == "TEST_edited text"
    got = [d for d in s.get(f"{API}/desk/drafts", timeout=20).json()["drafts"] if d["id"] == did][0]
    assert got["text"] == "TEST_edited text" and got["status"] == "draft"
    r = s.post(f"{API}/desk/drafts/{did}/approve", timeout=20)
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["approved_at"]
    # edit after approve -> back to draft
    r = s.patch(f"{API}/desk/drafts/{did}", json={"text": "TEST_edited again"}, timeout=20)
    assert r.json()["status"] == "draft"
    r = s.post(f"{API}/desk/drafts/{did}/discard", timeout=20)
    assert r.json()["status"] == "discarded"
    assert s.post(f"{API}/desk/drafts/{did}/approve", timeout=20).status_code == 409
    assert s.patch(f"{API}/desk/drafts/{did}", json={"text": "x"}, timeout=20).status_code == 409
    filtered = s.get(f"{API}/desk/drafts?status=discarded", timeout=20).json()["drafts"]
    assert all(d["status"] == "discarded" for d in filtered) and any(d["id"] == did for d in filtered)


# --- JRN-32 delivery note
def test_delivery_note_paid_order(s):
    oid, code = paid_order_id()
    if not oid:
        pytest.skip("no paid order")
    before = snapshot()
    r = s.post(f"{API}/desk/orders/{oid}/delivery-note", timeout=90)
    assert r.status_code == 200, r.text
    d = r.json()
    print("\n--- delivery:\n" + d["text"])
    assert d["kind"] == "delivery" and d["target"] == code
    assert code in d["text"] and f"{BASE_URL}/p/{code}" in d["text"]
    assert not FORBIDDEN.search(d["text"])
    assert snapshot() == before


def test_delivery_note_non_paid_409(s):
    o = DB.orders.find_one({"state": {"$nin": ["paid", "disputed"]}})
    if not o:
        pytest.skip("no non-paid order")
    r = s.post(f"{API}/desk/orders/{o['_id']}/delivery-note", timeout=20)
    assert r.status_code == 409


# --- JRN-35 go-live checklist
def test_go_live_checklist(s):
    d = s.get(f"{API}/desk/status", timeout=30).json()
    cl = {c["key"]: c for c in d["go_live_checklist"]}
    assert list(cl) == ["public_url", "live_key", "live_whsec", "live_webhook"]
    assert d["mode"] == "test"
    assert cl["live_key"]["ok"] is False and cl["live_whsec"]["ok"] is False
    assert cl["public_url"]["ok"] is False  # preview URL


def test_proof_mode_test_lists_test_certs():
    d = requests.get(f"{API}/proof", timeout=20).json()
    assert d["mode"] == "test"
