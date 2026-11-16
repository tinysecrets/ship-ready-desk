"""Slot counter transitions. Each op is applied to the ship at most once per order (slot_ops key)."""
from pymongo import ReturnDocument

from db import db

OPS = {
    "hold": ("none", "held", {"reserved": 1}, True),
    "sell": ("held", "sold", {"reserved": -1, "sold": 1}, False),
    "release_hold": ("held", "released", {"reserved": -1}, False),
    "release_sold": ("sold", "released", {"sold": -1}, False),
    "resell": ("released", "sold", {"sold": 1}, True),
}


def capacity_expr(mode: str) -> dict:
    return {"$lt": [{"$add": [f"$counters.{mode}.sold", f"$counters.{mode}.reserved"]}, "$slots"]}


async def finish_op(order: dict, op: str) -> bool:
    _, to, inc, needs_capacity = OPS[op]
    mode, key = order["mode"], f"{op}:{order['_id']}"
    flt = {"_id": order["ship_id"], "slot_ops": {"$ne": key}}
    if needs_capacity:
        flt["$expr"] = capacity_expr(mode)
    res = await db.ships.update_one(
        flt, {"$inc": {f"counters.{mode}.{k}": v for k, v in inc.items()}, "$addToSet": {"slot_ops": key}}
    )
    applied = res.modified_count == 1 or await db.ships.count_documents({"_id": order["ship_id"], "slot_ops": key}) > 0
    update = {"slot_pending": None, **({"slot": to} if applied else {})}
    await db.orders.update_one({"_id": order["_id"], "slot_pending": op}, {"$set": update})
    return applied


async def apply_slot_op(order_id, op: str) -> bool:
    frm, to, _, _ = OPS[op]
    order = await db.orders.find_one_and_update(
        {"_id": order_id, "slot": frm, "slot_pending": None},
        {"$set": {"slot_pending": op}},
        return_document=ReturnDocument.AFTER,
    )
    if not order:
        current = await db.orders.find_one({"_id": order_id})
        if current and current.get("slot_pending") == op:
            return await finish_op(current, op)
        return bool(current and current.get("slot") == to)
    return await finish_op(order, op)


async def repair_pending(limit: int = 50) -> int:
    n = 0
    async for o in db.orders.find({"slot_pending": {"$ne": None}}).limit(limit):
        ok = await finish_op(o, o["slot_pending"])
        if o["slot_pending"] == "hold" and not ok:
            await db.orders.update_one({"_id": o["_id"], "state": "pending"}, {"$set": {"state": "expired", "expire_reason": "no capacity"}})
        n += 1
    return n


async def open_slots(ship: dict, mode: str) -> int:
    c = (ship.get("counters") or {}).get(mode) or {}
    return max(0, ship["slots"] - c.get("sold", 0) - c.get("reserved", 0))
