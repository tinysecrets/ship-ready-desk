import datetime
from conftest import new_order, sim, order
def test_expire_and_async_failed():
    for c in ("expire", "async-failed"):
        oid = new_order(c); sim(c, oid)
        o = order(oid); assert o["state"] == "expired" and o["slot"] == "released", (c, o["state"])
def test_sweep(op):
    from conftest import db; from bson import ObjectId
    oid = new_order("sweep")
    db.orders.update_one({"_id": ObjectId(oid)}, {"$set": {"hold_expires_at": datetime.datetime.utcnow() - datetime.timedelta(minutes=46)}})
    assert op.post("/desk/sweep").status_code == 200
    o = order(oid); assert o["state"] == "expired" and o["slot"] == "released"
