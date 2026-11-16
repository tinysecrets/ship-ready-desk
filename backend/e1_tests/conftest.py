import subprocess, time, uuid
import httpx, pytest
from pymongo import MongoClient
from bson import ObjectId

API = "http://localhost:8001/api"
SECRET = "29ef03a20d3798cfe3466051d665f5eb0c456eb125aabfdb62b3aa29388508e9"
SIM = ["python", "/app/scripts/stripe_sim.py"]
db = MongoClient("mongodb://localhost:27017")["test_database"]

def key(slug): return f"tscheck-{slug}-{uuid.uuid4().hex[:12]}"

def sim(*args):
    out = subprocess.run(SIM + list(args), capture_output=True, text=True, timeout=90)
    return out.stdout + out.stderr

def checkout(slug="x"):
    return httpx.post(f"{API}/ships/shipready-sprint/checkout", headers={"x-idem-key": key(slug)}, timeout=60)

def new_order(slug="x"):
    r = checkout(slug)
    if r.status_code == 409:
        pytest.skip("capacity full")
    assert r.status_code == 200, r.text
    return r.json()["orderId"]

def order(oid): return db.orders.find_one({"_id": ObjectId(oid)})
def ledger(oid, kind=None):
    q = {"order_id": ObjectId(oid)}
    if kind: q["kind"] = kind
    return list(db.ledger.find(q))

def wait_for(fn, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v: return v
        time.sleep(2)
    return fn()

@pytest.fixture(scope="session")
def op():
    c = httpx.Client(base_url=API, timeout=90)
    r = c.post("/auth/login", json={"secret": SECRET})
    assert r.status_code == 200
    # cookie is Secure; carry it manually over http
    c.headers["cookie"] = f"__Host-operator_session={r.cookies.get('__Host-operator_session')}"
    return c
