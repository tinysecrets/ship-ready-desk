import httpx
from conftest import API
def test_unauth_and_wrong():
    for p in ("/auth/me", "/desk/summary", "/desk/orders", "/desk/status"):
        assert httpx.get(API + p).status_code == 401, p
    assert httpx.post(API + "/auth/login", json={"secret": "tscheck-wrong"}).status_code in (401, 403)
def test_status(op):
    j = op.get("/desk/status").json()
    assert j["mode"] == "test" and j["webhook_url"].endswith("/api/webhooks/stripe")
    assert op.get("/desk/summary").json()["target_cents"] == 100000
