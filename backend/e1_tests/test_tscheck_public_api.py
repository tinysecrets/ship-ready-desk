import httpx
from conftest import API
def test_ship_and_404():
    r = httpx.get(f"{API}/ships/shipready-sprint"); j = r.json()
    assert r.status_code == 200 and j["slots"] == 3 and j["price_cents"] == 109000 and j["mode"] == "test"
    assert httpx.get(f"{API}/ships/tscheck-nope").status_code == 404
    assert httpx.get(f"{API}/certificates/SR-TSCHECKNOPE0").status_code == 404
    assert "certificates" in httpx.get(f"{API}/proof").json()
def test_health_openapi():
    assert httpx.get(f"{API}/health").json()["ok"] is True
    assert "paths" in httpx.get(f"{API}/openapi.json").json()
