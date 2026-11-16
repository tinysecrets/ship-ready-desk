"""Event -> ledger effects. Every effect is keyed by op_key so replays are no-ops."""
import asyncio
import logging
import secrets
from typing import Optional

import stripe
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

import money
from config import NAMESPACE
from db import Certificate, LedgerEntry, db, now
from slots import apply_slot_op

log = logging.getLogger("ledger")
LOCK = asyncio.Lock()
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_bg_tasks: set = set()


def result(status: str, detail: str, order_id=None) -> dict:
    return {"status": status, "detail": detail, "order_id": str(order_id) if order_id else None}


def unresolved(detail: str, order_id=None) -> dict:
    return result("unresolved", detail, order_id)


def ignored(detail: str, order_id=None) -> dict:
    return result("ignored", detail, order_id)


async def insert_ledger(entry: LedgerEntry) -> bool:
    try:
        await db.ledger.insert_one(entry.to_mongo())
        return True
    except DuplicateKeyError:
        return False


async def apply_order_effect(order_id, op_key: str, inc: dict, extra: Optional[dict] = None) -> None:
    update = {"$inc": inc, "$addToSet": {"applied_ops": op_key}}
    if extra:
        update["$set"] = extra
    await db.orders.update_one({"_id": order_id, "applied_ops": {"$ne": op_key}}, update)


async def match_order(obj: dict, ev_mode: str, pi: Optional[str] = None):
    md = obj.get("metadata") or {}
    ns, oid = md.get("namespace"), md.get("orderId")
    if ns and ns != NAMESPACE:
        return None, f"foreign namespace '{ns}'"
    order = None
    if ns and oid and ObjectId.is_valid(oid):
        order = await db.orders.find_one({"_id": ObjectId(oid)})
    if not order and pi:
        order = await db.orders.find_one({"payment_intent": pi})
    if not order and obj.get("object") == "checkout.session" and obj.get("id"):
        order = await db.orders.find_one({"session_id": obj["id"]})
    if not order:
        return None, "no matching local order"
    if order["namespace"] != NAMESPACE:
        return None, "order namespace mismatch"
    if order["mode"] != ev_mode:
        return None, f"mode mismatch (event {ev_mode}, order {order['mode']})"
    return order, ""


async def issue_certificate(order: dict) -> str:
    existing = await db.certificates.find_one({"order_id": order["_id"]})
    if existing:
        code = existing["code"]
    else:
        code = "SR-" + "".join(secrets.choice(CROCKFORD) for _ in range(12))
        cert = Certificate(code=code, order_id=str(order["_id"]), ship_id=str(order["ship_id"]), ship_title=order["ship_title"],
                           mode=order["mode"], amount_cents=order["amount_cents"], currency=order["currency"], issued_at=now())
        try:
            await db.certificates.insert_one(cert.to_mongo())
        except DuplicateKeyError:
            code = (await db.certificates.find_one({"order_id": order["_id"]}))["code"]
    await db.orders.update_one({"_id": order["_id"]}, {"$set": {"cert_code": code}})
    return code


async def record_actual_fee(order_id, pi: str) -> None:
    try:
        p = await asyncio.to_thread(stripe.PaymentIntent.retrieve, pi, expand=["latest_charge.balance_transaction"])
        bt = (p.get("latest_charge") or {}).get("balance_transaction")
        if bt and bt.get("fee") is not None:
            await db.orders.update_one({"_id": order_id}, {"$set": {"fee_actual_cents": int(bt["fee"])}})
    except Exception as exc:
        log.info("actual fee unavailable for %s: %s", pi, exc)


async def book_charge(order: dict, pi: Optional[str], amount, currency, event_id: Optional[str]) -> dict:
    oid = order["_id"]
    if not pi:
        return unresolved("paid event without payment_intent", oid)
    if amount != order["amount_cents"] or (currency or "").lower() != order["currency"]:
        return unresolved(f"amount/currency mismatch ({amount} {currency} vs {order['amount_cents']} {order['currency']})", oid)
    if order.get("payment_intent") and order["payment_intent"] != pi:
        return unresolved(f"order already paid by {order['payment_intent']}", oid)
    entry = LedgerEntry(op_key=f"charge:{pi}", kind="charge", order_id=str(oid), ship_id=str(order["ship_id"]), mode=order["mode"],
                        amount_cents=amount, fee_est_cents=money.fee_cents(amount), compute_cents=money.COMPUTE_CENTS,
                        currency=order["currency"], stripe_ref=pi, event_id=event_id, created_at=now())
    inserted = await insert_ledger(entry)
    await db.orders.update_one({"_id": oid, "payment_intent": None}, {"$set": {"payment_intent": pi}})
    await db.orders.update_one({"_id": oid, "state": {"$in": ["pending", "reserved", "expired", "failed"]}},
                               {"$set": {"state": "paid", "paid_at": now()}})
    current = await db.orders.find_one({"_id": oid})
    if current["slot"] == "held":
        await apply_slot_op(oid, "sell")
    elif current["slot"] == "released" and current["state"] == "paid" and "resell:" + str(oid) not in current.get("applied_ops", []):
        if not await apply_slot_op(oid, "resell"):
            await db.orders.update_one({"_id": oid}, {"$set": {"over_capacity": True}})
    code = await issue_certificate(current)
    if inserted:
        task = asyncio.create_task(record_actual_fee(oid, pi))
        _bg_tasks.add(task)
        task.add_done_callback(_bg_tasks.discard)
    return result("processed", f"charge {'booked' if inserted else 'already booked'}; certificate {code}", oid)


async def expire_order(order: dict, reason: str) -> dict:
    res = await db.orders.update_one({"_id": order["_id"], "state": {"$in": ["pending", "reserved"]}},
                                     {"$set": {"state": "expired", "expired_at": now(), "expire_reason": reason}})
    current = await db.orders.find_one({"_id": order["_id"]})
    if current["state"] == "expired" and current["slot"] == "held":
        await apply_slot_op(order["_id"], "release_hold")
    if res.modified_count:
        return result("processed", f"order expired ({reason}); slot released", order["_id"])
    return ignored(f"order is {current['state']}; nothing to expire", order["_id"])


async def book_refund(r: dict, ev_mode: str, event_id: Optional[str]) -> dict:
    if r.get("status") != "succeeded":
        return ignored(f"refund {r.get('id')} status {r.get('status')}")
    order, why = await match_order(r, ev_mode, pi=r.get("payment_intent"))
    if not order:
        return unresolved(f"refund {r.get('id')}: {why}")
    if (r.get("currency") or "").lower() != order["currency"]:
        return unresolved("refund currency mismatch", order["_id"])
    op_key = f"refund:{r['id']}"
    existing = await db.ledger.find_one({"op_key": op_key})
    fresh = False
    if existing:
        amt = -existing["amount_cents"]
    else:
        amt = min(int(r.get("amount") or 0), order["amount_cents"] - order["refunded_cents"] - order["disputed_cents"])
        if amt <= 0:
            return unresolved(f"refund {r['id']}: nothing left to refund", order["_id"])
        entry = LedgerEntry(op_key=op_key, kind="refund", order_id=str(order["_id"]), ship_id=str(order["ship_id"]), mode=order["mode"],
                            amount_cents=-amt, currency=order["currency"], stripe_ref=r["id"], event_id=event_id, created_at=now())
        fresh = await insert_ledger(entry)
        if not fresh:
            amt = -(await db.ledger.find_one({"op_key": op_key}))["amount_cents"]
    await apply_order_effect(order["_id"], op_key, {"refunded_cents": amt})
    current = await db.orders.find_one({"_id": order["_id"]})
    full = current["refunded_cents"] >= current["amount_cents"]
    if full:
        await db.orders.update_one({"_id": order["_id"]}, {"$set": {"state": "refunded"}})
        if current["slot"] == "sold":
            await apply_slot_op(order["_id"], "release_sold")
        await db.certificates.update_one({"order_id": order["_id"], "revoked": False}, {"$set": {"revoked": True, "revoked_at": now()}})
    return result("processed", f"refund {r['id']} {'booked' if fresh else 'already booked'} −{amt}{' (full: slot released, certificate revoked)' if full else ''}", order["_id"])


async def book_dispute(d: dict, ev_mode: str, event_id: Optional[str]) -> dict:
    order, why = await match_order(d, ev_mode, pi=d.get("payment_intent"))
    if not order:
        return unresolved(f"dispute {d.get('id')}: {why}")
    op_key = f"dispute:{d['id']}"
    existing = await db.ledger.find_one({"op_key": op_key})
    if existing:
        amt = -existing["amount_cents"]
    else:
        amt = min(int(d.get("amount") or 0), order["amount_cents"] - order["refunded_cents"] - order["disputed_cents"])
        if amt <= 0:
            return unresolved(f"dispute {d['id']}: nothing unrefunded to debit", order["_id"])
        entry = LedgerEntry(op_key=op_key, kind="dispute", order_id=str(order["_id"]), ship_id=str(order["ship_id"]), mode=order["mode"],
                            amount_cents=-amt, currency=order["currency"], stripe_ref=d["id"], event_id=event_id, created_at=now())
        if not await insert_ledger(entry):
            amt = -(await db.ledger.find_one({"op_key": op_key}))["amount_cents"]
    await apply_order_effect(order["_id"], op_key, {"disputed_cents": amt}, {"state": "disputed", "dispute_status": d.get("status", "open")})
    return result("processed", f"dispute {d['id']} debit −{amt}", order["_id"])


async def book_dispute_closed(d: dict, ev_mode: str, event_id: Optional[str]) -> dict:
    order, why = await match_order(d, ev_mode, pi=d.get("payment_intent"))
    if not order:
        return unresolved(f"dispute {d.get('id')}: {why}")
    status = d.get("status")
    if status != "won":
        await db.orders.update_one({"_id": order["_id"]}, {"$set": {"dispute_status": status}})
        return ignored(f"dispute {d['id']} closed {status}; debit stands", order["_id"])
    debit = await db.ledger.find_one({"op_key": f"dispute:{d['id']}"})
    if not debit:
        return unresolved(f"dispute {d['id']} won but no debit booked", order["_id"])
    op_key = f"dispute_reversal:{d['id']}"
    amt = -debit["amount_cents"]
    entry = LedgerEntry(op_key=op_key, kind="dispute_reversal", order_id=str(order["_id"]), ship_id=str(order["ship_id"]), mode=order["mode"],
                        amount_cents=amt, currency=order["currency"], stripe_ref=d["id"], event_id=event_id, created_at=now())
    await insert_ledger(entry)
    await apply_order_effect(order["_id"], op_key, {"disputed_cents": -amt}, {"dispute_status": "won"})
    return result("processed", f"dispute {d['id']} won; reversal +{amt}", order["_id"])


async def handle_event(event: dict) -> dict:
    t, obj, eid = event["type"], event["data"]["object"], event.get("id")
    ev_mode = "live" if event.get("livemode") else "test"
    if t == "checkout.session.completed":
        if obj.get("payment_status") != "paid":
            return ignored(f"session payment_status {obj.get('payment_status')}")
        order, why = await match_order(obj, ev_mode, pi=obj.get("payment_intent"))
        if not order:
            return unresolved(why)
        return await book_charge(order, obj.get("payment_intent"), obj.get("amount_total"), obj.get("currency"), eid)
    if t == "payment_intent.succeeded":
        order, why = await match_order(obj, ev_mode, pi=obj.get("id"))
        if not order:
            return unresolved(f"payment {obj.get('id')}: {why}")
        return await book_charge(order, obj.get("id"), obj.get("amount_received") or obj.get("amount"), obj.get("currency"), eid)
    if t in ("checkout.session.expired", "checkout.session.async_payment_failed"):
        order, why = await match_order(obj, ev_mode)
        if not order:
            return unresolved(why)
        return await expire_order(order, t)
    if t in ("refund.created", "refund.updated"):
        return await book_refund(obj, ev_mode, eid)
    if t == "charge.refunded":
        refunds = (obj.get("refunds") or {}).get("data") or []
        if not refunds:
            return ignored("charge.refunded without refund list; refund.* events carry the booking")
        outs = [await book_refund({**r, "payment_intent": r.get("payment_intent") or obj.get("payment_intent")}, ev_mode, eid) for r in refunds]
        bad = [o for o in outs if o["status"] == "unresolved"]
        return bad[0] if bad else result("processed", "; ".join(o["detail"] for o in outs), outs[0]["order_id"])
    if t == "charge.dispute.created":
        return await book_dispute(obj, ev_mode, eid)
    if t == "charge.dispute.closed":
        return await book_dispute_closed(obj, ev_mode, eid)
    return ignored(f"unhandled type {t}")
