import asyncio
import json
import logging
from contextlib import suppress
from datetime import timedelta
from typing import Optional

import stripe
from bson import ObjectId
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError
from starlette.middleware.cors import CORSMiddleware

import money
from auth import check_rate, clear_session, require_operator, set_session, verify_secret
from config import (MODE, NAMESPACE, PAYMENTS_CONFIGURED, SECRET_SOURCES, STRIPE_WEBHOOK_ENDPOINT_ID, STRIPE_WEBHOOK_SECRET,
                    SWEEP_INTERVAL_SECONDS, WEBHOOK_SECRETS)
from db import Certificate, LedgerEntry, Order, Ship, client, db, ensure_indexes, now
from drafts import router as drafts_router
from ledger import LOCK, book_charge, expire_order, handle_event, record_actual_fee
from slots import apply_slot_op, finish_op, open_slots, repair_pending

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger("shipready")

app = FastAPI(title="Shipready API", openapi_url="/api/openapi.json", docs_url="/api/docs", redoc_url=None)
api = APIRouter(prefix="/api")
SEED_SLUG = "shipready-sprint"
ORDER_PUBLIC_FIELDS = {"idem_key", "applied_ops", "namespace", "origin", "session_url"}


def oid_or_404(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(404, "Nothing at this address.")
    return ObjectId(value)


def public_base(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{'https' if proto == 'https' or not host.startswith(('localhost', '127.')) else proto}://{host}"


async def get_ship(slug: str) -> dict:
    ship = await db.ships.find_one({"slug": slug, "published": True})
    if not ship:
        raise HTTPException(404, "Nothing at this address.")
    return ship


# ---------- public ----------
@api.get("/health")
async def health():
    return {"ok": True}


@api.get("/money")
async def money_constants():
    return money.as_dict()


@api.get("/stripe/status")
async def stripe_status():
    return {"configured": PAYMENTS_CONFIGURED, "mode": MODE, "webhook_secret_set": bool(STRIPE_WEBHOOK_SECRET)}


@api.get("/ships/{slug}")
async def ship_detail(slug: str):
    ship = await get_ship(slug)
    s = Ship.from_mongo(ship)
    return {"slug": s.slug, "title": s.title, "price_cents": s.price_cents, "currency": s.currency, "slots": s.slots,
            "open": await open_slots(ship, MODE), "mode": MODE, "payments_configured": PAYMENTS_CONFIGURED}


class CheckoutBody(BaseModel):
    origin_url: Optional[str] = None


def checkout_response(order: dict) -> dict:
    return {"orderId": str(order["_id"]), "sessionId": order.get("session_id"), "url": order.get("session_url"), "state": order["state"]}


async def create_session(order: dict) -> dict:
    oid = str(order["_id"])
    md = {"namespace": NAMESPACE, "orderId": oid}
    params = dict(
        mode="payment",
        line_items=[{"price_data": {"currency": order["currency"], "unit_amount": order["amount_cents"],
                                    "product_data": {"name": order["ship_title"]}}, "quantity": 1}],
        success_url=f"{order['origin']}/s/{order['ship_slug']}?ok=1&order={oid}",
        cancel_url=f"{order['origin']}/s/{order['ship_slug']}?cancelled=1&order={oid}",
        client_reference_id=oid,
        metadata=md,
        payment_intent_data={"metadata": md},
        expires_at=int(order["hold_expires_at"].timestamp()),
    )
    try:
        session = await asyncio.to_thread(stripe.checkout.Session.create, **params, idempotency_key=f"checkout:{oid}")
    except stripe.error.StripeError as exc:
        log.error("checkout session failed for %s: %s", oid, exc)
        await db.orders.update_one({"_id": order["_id"], "state": {"$in": ["pending", "reserved"]}}, {"$set": {"state": "failed"}})
        await apply_slot_op(order["_id"], "release_hold")
        raise HTTPException(503, "Could not start Stripe Checkout. Your slot was released; try again.")
    await db.orders.update_one({"_id": order["_id"]}, {"$set": {"session_id": session.id, "session_url": session.url}})
    return {**order, "session_id": session.id, "session_url": session.url}


async def resume_checkout(order: dict) -> dict:
    if order["state"] == "reserved" and order.get("session_url"):
        return checkout_response(order)
    if order["state"] == "reserved":
        return checkout_response(await create_session(order))
    if order["state"] == "pending":
        raise HTTPException(409, "Checkout already in progress for this key.")
    if order["state"] == "failed":
        raise HTTPException(503, "Checkout failed for this key; use a new one.")
    if order["state"] == "expired":
        raise HTTPException(409, "This hold expired; use a new key.")
    return checkout_response(order)


@api.post("/ships/{slug}/checkout")
async def checkout(slug: str, request: Request, body: Optional[CheckoutBody] = None, x_idem_key: Optional[str] = Header(default=None)):
    if not x_idem_key or len(x_idem_key) < 8 or len(x_idem_key) > 128:
        raise HTTPException(400, "x-idem-key header (8-128 chars) required")
    ship = await get_ship(slug)
    if not PAYMENTS_CONFIGURED:
        raise HTTPException(503, "Payments not configured.")
    existing = await db.orders.find_one({"idem_key": x_idem_key})
    if existing:
        return await resume_checkout(existing)
    origin = (body.origin_url if body and body.origin_url else public_base(request)).rstrip("/")
    if not origin.startswith(("https://", "http://localhost")):
        raise HTTPException(400, "origin_url must be https")
    t = now()
    order = Order(ship_id=str(ship["_id"]), ship_slug=ship["slug"], ship_title=ship["title"], mode=MODE, namespace=NAMESPACE,
                  idem_key=x_idem_key, state="pending", slot="none", slot_pending="hold", amount_cents=ship["price_cents"],
                  currency=ship["currency"], origin=origin, created_at=t,
                  hold_expires_at=t + timedelta(minutes=money.HOLD_MINUTES)).to_mongo()
    try:
        await db.orders.insert_one(order)
    except DuplicateKeyError:
        return await resume_checkout(await db.orders.find_one({"idem_key": x_idem_key}))
    if not await finish_op(order, "hold"):
        await db.orders.delete_one({"_id": order["_id"]})
        raise HTTPException(409, "sold out")
    await db.orders.update_one({"_id": order["_id"], "state": "pending"}, {"$set": {"state": "reserved"}})
    order["state"] = "reserved"
    return checkout_response(await create_session(order))


async def reconcile_from_stripe(order: dict) -> None:
    try:
        s = await asyncio.to_thread(stripe.checkout.Session.retrieve, order["session_id"])
    except stripe.error.StripeError:
        return
    if s.get("payment_status") == "paid" and s.get("livemode") == (order["mode"] == "live"):
        async with LOCK:
            await book_charge(order, s.get("payment_intent"), s.get("amount_total"), s.get("currency"), None)


@api.get("/orders/{order_id}")
async def order_public(order_id: str):
    order = await db.orders.find_one({"_id": oid_or_404(order_id)})
    if not order:
        raise HTTPException(404, "Nothing at this address.")
    if order["state"] == "reserved" and order.get("session_id") and PAYMENTS_CONFIGURED:
        await reconcile_from_stripe(order)
        order = await db.orders.find_one({"_id": order["_id"]})
    return {"orderId": str(order["_id"]), "state": order["state"], "certificate_code": order.get("cert_code"), "ship_slug": order["ship_slug"]}


async def order_contribution(order_id) -> int:
    rows = await db.ledger.find({"order_id": order_id}).to_list(100)
    return sum(r["amount_cents"] - r.get("fee_est_cents", 0) - r.get("compute_cents", 0) for r in rows)


def cert_out(c: dict) -> dict:
    cert = Certificate.from_mongo(c)
    return {"code": cert.code, "ship_title": cert.ship_title, "mode": cert.mode, "amount_cents": cert.amount_cents,
            "currency": cert.currency, "revoked": cert.revoked, "revoked_at": cert.revoked_at, "issued_at": cert.issued_at}


@api.get("/proof")
async def proof():
    q = {"mode": "live"} if MODE == "live" else {}
    certs = await db.certificates.find(q).sort("issued_at", -1).to_list(500)
    return {"mode": MODE, "certificates": [cert_out(c) for c in certs]}


@api.get("/certificates/{code}")
async def certificate(code: str):
    c = await db.certificates.find_one({"code": code.upper()})
    if not c:
        raise HTTPException(404, "Nothing at this address.")
    return {**cert_out(c), "verified_contribution_cents": await order_contribution(c["order_id"])}


# ---------- webhook ----------
async def receive_stripe_webhook(request: Request, path: str):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    if not WEBHOOK_SECRETS:
        raise HTTPException(400, "Webhook secret not configured")
    label = None
    for name, secret in (WEBHOOK_SECRETS if sig else []):
        try:
            stripe.Webhook.construct_event(payload, sig, secret)
            label = name
            break
        except (stripe.error.SignatureVerificationError, ValueError):
            continue
    if not label:
        try:
            claimed = json.loads(payload)
        except ValueError:
            claimed = {}
        claimed = claimed if isinstance(claimed, dict) else {}
        await db.webhook_sig_failures.insert_one({
            "at": now(), "path": path, "tried": [n for n, _ in WEBHOOK_SECRETS] if sig else [], "signed": bool(sig),
            "unverified_event_id": claimed.get("id"), "unverified_type": claimed.get("type"),
            "unverified_livemode": claimed.get("livemode"), "unverified_account": claimed.get("account")})
        await db.meta.update_one({"_id": "webhook"}, {"$set": {"last_sig_failure_at": now(), "last_sig_failure_path": path},
                                                       "$inc": {"sig_failures": 1}}, upsert=True)
        raise HTTPException(400, "Invalid signature" if sig else "Missing Stripe-Signature")
    event = json.loads(payload)
    eid, etype = event.get("id"), event.get("type")
    livemode = bool(event.get("livemode"))
    route = "primary" if path == "/api/webhooks/stripe" else "platform"
    live = {"live_last_at": now(), "live_last_type": etype} if livemode and MODE == "live" else {}
    await db.meta.update_one({"_id": "webhook"}, {"$set": {"last_at": now(), "last_type": etype, "last_event_id": eid, "last_path": path,
                                                           f"{route}_last_at": now(), f"{route}_last_type": etype, **live,
                                                           f"secrets.{label}": {"last_at": now(), "livemode": livemode, "type": etype,
                                                                                "event_id": eid, "path": path,
                                                                                "account": event.get("account")}},
                                                   "$inc": {"received": 1}}, upsert=True)
    async with LOCK:
        claim = {"event_id": eid, "type": etype, "livemode": livemode, "path": path, "secret": label, "status": "processing", "received_at": now()}
        try:
            await db.webhook_inbox.insert_one(claim)
        except DuplicateKeyError:
            prior = await db.webhook_inbox.find_one({"event_id": eid})
            if prior and prior["status"] != "processing":
                return {"status": "replay", "event_id": eid}
        try:
            outcome = await handle_event(event)
        except Exception:
            log.exception("webhook %s (%s) failed; releasing inbox claim for retry", eid, etype)
            await db.webhook_inbox.delete_one({"event_id": eid})
            raise HTTPException(500, "processing failed; retry")
        await db.webhook_inbox.update_one({"event_id": eid}, {"$set": {**outcome, "processed_at": now()}})
        await db.meta.update_one({"_id": "webhook"}, {"$set": {f"secrets.{label}.outcome": outcome["status"], f"secrets.{label}.detail": outcome["detail"]}})
    log.info("webhook %s %s -> %s: %s", eid, etype, outcome["status"], outcome["detail"])
    return {**outcome, "event_id": eid}


@api.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    return await receive_stripe_webhook(request, "/api/webhooks/stripe")


@api.post("/stripe/webhook", include_in_schema=False)
async def stripe_webhook_platform(request: Request):
    return await receive_stripe_webhook(request, "/api/stripe/webhook")


# ---------- operator ----------
class LoginBody(BaseModel):
    secret: str = Field(min_length=1, max_length=256)


@api.post("/auth/login")
async def login(body: LoginBody, request: Request, response: Response):
    check_rate(request)
    if not verify_secret(request, body.secret.strip()):
        raise HTTPException(401, "Wrong secret.")
    set_session(response)
    return {"ok": True}


@api.post("/auth/logout")
async def logout(response: Response):
    clear_session(response)
    return {"ok": True}


@api.get("/auth/me", dependencies=[Depends(require_operator)])
async def me():
    return {"operator": True}


desk = APIRouter(prefix="/api/desk", dependencies=[Depends(require_operator)])


def pick_mode(mode: Optional[str]) -> str:
    return mode if mode in ("test", "live") else MODE


@desk.get("/summary")
async def desk_summary(mode: Optional[str] = None):
    m = pick_mode(mode)
    rows = [LedgerEntry.from_mongo(r) for r in await db.ledger.find({"mode": m}).to_list(10000)]
    by = lambda k: sum(r.amount_cents for r in rows if r.kind == k)
    charges = [r for r in rows if r.kind == "charge"]
    gross, refunds = by("charge"), by("refund")
    disputes, reversals = by("dispute"), by("dispute_reversal")
    fees_est = sum(r.fee_est_cents for r in charges)
    compute = sum(r.compute_cents for r in charges)
    contribution = gross + refunds + disputes + reversals - fees_est - compute
    fee_docs = await db.orders.find({"mode": m, "fee_actual_cents": {"$ne": None}}, {"fee_actual_cents": 1}).to_list(10000)
    fully_refunded = await db.orders.count_documents({"mode": m, "state": "refunded"})
    return {"mode": m, "contribution_cents": contribution, "closes_booked": len(charges), "closes_net": len(charges) - fully_refunded,
            "closes_remaining": money.closes_remaining(contribution), "target_cents": money.FLOOR_CENTS,
            "gross_cents": gross, "refunds_cents": refunds, "disputes_cents": disputes, "dispute_reversals_cents": reversals,
            "disputes_net_cents": disputes + reversals, "fees_est_cents": fees_est,
            "fees_actual_cents": sum(d["fee_actual_cents"] for d in fee_docs), "fees_actual_known": len(fee_docs),
            "compute_cents": compute, "ledger_rows": len(rows), "money": money.as_dict()}


@desk.get("/orders")
async def desk_orders(mode: Optional[str] = None):
    docs = await db.orders.find({"mode": pick_mode(mode), "state": {"$ne": "pending"}}).sort("created_at", -1).to_list(200)
    return {"orders": [Order.from_mongo(d).model_dump(exclude=ORDER_PUBLIC_FIELDS) for d in docs]}


class RefundBody(BaseModel):
    amount_cents: Optional[int] = Field(default=None, gt=0)


@desk.post("/orders/{order_id}/refund")
async def desk_refund(order_id: str, body: RefundBody, x_idem_key: Optional[str] = Header(default=None)):
    if not x_idem_key or len(x_idem_key) < 8 or len(x_idem_key) > 128:
        raise HTTPException(400, "x-idem-key header (8-128 chars) required")
    order = await db.orders.find_one({"_id": oid_or_404(order_id)})
    if not order:
        raise HTTPException(404, "order not found")
    key = f"refund:{order_id}:{body.amount_cents or 'full'}:{x_idem_key}"
    prior = await db.refund_requests.find_one({"key": key})
    if prior:
        return {"refund_id": prior.get("refund_id"), "amount_cents": prior["amount_cents"], "status": prior.get("status"), "replayed": True}
    if order["state"] not in ("paid", "disputed") or not order.get("payment_intent"):
        raise HTTPException(409, f"order is {order['state']}; nothing to refund")
    remaining = order["amount_cents"] - order["refunded_cents"] - order["disputed_cents"]
    if remaining <= 0:
        raise HTTPException(409, "nothing left to refund")
    amount = min(body.amount_cents or remaining, remaining)
    try:
        await db.refund_requests.insert_one({"key": key, "order_id": order["_id"], "requested_cents": body.amount_cents,
                                             "amount_cents": amount, "status": "creating", "created_at": now()})
    except DuplicateKeyError:
        prior = await db.refund_requests.find_one({"key": key})
        return {"refund_id": prior.get("refund_id"), "amount_cents": prior["amount_cents"], "status": prior.get("status"), "replayed": True}
    try:
        r = await asyncio.to_thread(stripe.Refund.create, payment_intent=order["payment_intent"], amount=amount,
                                    metadata={"namespace": NAMESPACE, "orderId": order_id}, idempotency_key=key)
    except stripe.error.StripeError as exc:
        await db.refund_requests.delete_one({"key": key})
        raise HTTPException(503, f"Stripe refused the refund: {exc.user_message or str(exc)}")
    await db.refund_requests.update_one({"key": key}, {"$set": {"status": r.status, "refund_id": r.id}})
    return {"refund_id": r.id, "amount_cents": amount, "capped": bool(body.amount_cents and body.amount_cents > amount),
            "status": r.status, "replayed": False}


_endpoint_cache: dict = {}


async def stripe_endpoint_info() -> Optional[dict]:
    if not (PAYMENTS_CONFIGURED and STRIPE_WEBHOOK_ENDPOINT_ID):
        return None
    cached = _endpoint_cache.get("v")
    if cached and (now() - cached["at"]).total_seconds() < 60:
        return cached["data"]
    try:
        w = await asyncio.to_thread(stripe.WebhookEndpoint.retrieve, STRIPE_WEBHOOK_ENDPOINT_ID)
        data = {"id": w.id, "url": w.url, "status": w.status, "enabled_events": list(w.enabled_events)}
    except stripe.error.StripeError as exc:
        data = {"id": STRIPE_WEBHOOK_ENDPOINT_ID, "error": str(exc)}
    _endpoint_cache["v"] = {"at": now(), "data": data}
    return data


async def stripe_account_info() -> Optional[dict]:
    if not PAYMENTS_CONFIGURED:
        return None
    if "acct" in _endpoint_cache:
        return _endpoint_cache["acct"]
    try:
        a = await asyncio.to_thread(stripe.Account.retrieve)
        data = {"id": a.id, "country": a.get("country"), "mode": MODE}
    except stripe.error.StripeError as exc:
        return {"error": str(exc), "mode": MODE}
    _endpoint_cache["acct"] = data
    return data


@desk.get("/status")
async def desk_status(request: Request):
    hook = await db.meta.find_one({"_id": "webhook"}) or {}
    sweep = await db.meta.find_one({"_id": "sweep"}) or {}
    base = public_base(request)
    host = base.split("://", 1)[1]
    is_preview = host.endswith(".preview.emergentagent.com") or host.startswith(("localhost", "127."))
    checklist = [
        {"key": "public_url", "label": "Deployed public URL in use", "ok": not is_preview,
         "detail": f"{base}{' (preview URL)' if is_preview else ''}"},
        {"key": "live_key", "label": "Live key set", "ok": MODE == "live",
         "detail": "sk_live_… configured" if MODE == "live" else "test key (sk_test_…)" if PAYMENTS_CONFIGURED else "no key"},
        {"key": "live_whsec", "label": "Live webhook secret set", "ok": MODE == "live" and bool(WEBHOOK_SECRETS),
         "detail": "whsec set for live key" if MODE == "live" and WEBHOOK_SECRETS else "test mode — live whsec not in use" if WEBHOOK_SECRETS else "missing"},
        {"key": "live_webhook", "label": "Last live webhook received", "ok": MODE == "live" and bool(hook.get("live_last_at")),
         "detail": f"{hook['live_last_at'].isoformat()} · {hook.get('live_last_type')}" if MODE == "live" and hook.get("live_last_at") else "never (in live mode)"},
    ]
    seen = hook.get("secrets") or {}
    secrets_status = [{"label": label, "env": env, "set": bool(value), **{k: seen.get(label, {}).get(k) for k in
                       ("last_at", "livemode", "type", "outcome", "detail", "path")}} for label, env, value in SECRET_SOURCES]
    return {"mode": MODE, "payments_configured": PAYMENTS_CONFIGURED, "namespace": NAMESPACE, "go_live_checklist": checklist,
            "stripe_account": await stripe_account_info(), "webhook_secrets": secrets_status,
            "sig_failures": hook.get("sig_failures", 0), "last_sig_failure_at": hook.get("last_sig_failure_at"),
            "live_last_at": hook.get("live_last_at"),
            "webhook_url": f"{base}/api/webhooks/stripe", "webhook_secret_set": bool(STRIPE_WEBHOOK_SECRET),
            "stripe_endpoint": await stripe_endpoint_info(),
            "last_webhook_at": hook.get("last_at"), "last_webhook_type": hook.get("last_type"), "webhooks_received": hook.get("received", 0),
            "last_webhook_path": hook.get("last_path"),
            "primary_last_at": hook.get("primary_last_at"), "primary_last_type": hook.get("primary_last_type"),
            "unresolved_count": await db.webhook_inbox.count_documents({"status": "unresolved"}),
            "sweep_last_run": sweep.get("last_run"), "sweep_last_expired": sweep.get("last_expired", 0),
            "sweep_interval_seconds": SWEEP_INTERVAL_SECONDS, "hold_minutes": money.HOLD_MINUTES}


@desk.get("/unresolved")
async def desk_unresolved():
    docs = await db.webhook_inbox.find({"status": "unresolved"}, {"_id": 0}).sort("received_at", -1).to_list(25)
    return {"events": docs}


@desk.get("/webhook-log")
async def desk_webhook_log(limit: int = 25):
    limit = max(1, min(limit, 100))
    inbox = await db.webhook_inbox.find({}, {"_id": 0}).sort("received_at", -1).to_list(limit)
    oids = [ObjectId(e["order_id"]) for e in inbox if e.get("order_id") and ObjectId.is_valid(e["order_id"])]
    orders = {str(o["_id"]): o for o in await db.orders.find({"_id": {"$in": oids}}, {"state": 1, "session_id": 1}).to_list(limit)}
    for e in inbox:
        o = orders.get(e.get("order_id") or "")
        e["order"] = {"id": str(o["_id"]), "state": o["state"], "via_checkout": bool(o.get("session_id"))} if o else None
    failures = await db.webhook_sig_failures.find({}, {"_id": 0}).sort("at", -1).to_list(limit)
    return {"deliveries": inbox, "signature_failures": failures,
            "signature_failure_count": await db.webhook_sig_failures.count_documents({})}


@desk.post("/sweep")
async def desk_sweep():
    return await run_sweep()


class ResetBody(BaseModel):
    confirm: str


@desk.post("/reset-test")
async def reset_test_data(body: ResetBody):
    if body.confirm != "RESET TEST":
        raise HTTPException(400, 'confirm must be "RESET TEST"')
    async with LOCK:
        ids = [o["_id"] for o in await db.orders.find({"mode": "test"}, {"_id": 1}).to_list(100000)]
        keys = [f"{op}:{i}" for i in ids for op in ("hold", "sell", "release_hold", "release_sold", "resell")]
        out = {
            "orders": (await db.orders.delete_many({"mode": "test"})).deleted_count,
            "ledger": (await db.ledger.delete_many({"mode": "test"})).deleted_count,
            "certificates": (await db.certificates.delete_many({"mode": "test"})).deleted_count,
            "webhook_inbox": (await db.webhook_inbox.delete_many({"livemode": False})).deleted_count,
            "refund_requests": (await db.refund_requests.delete_many({"order_id": {"$in": ids}})).deleted_count,
            "delivery_drafts": (await db.drafts.delete_many({"kind": "delivery", "ref_id": {"$in": ids}})).deleted_count,
        }
        await db.ships.update_many({}, {"$set": {"counters.test": {"sold": 0, "reserved": 0}}, "$pull": {"slot_ops": {"$in": keys}}})
        if MODE == "test":
            await db.meta.update_one({"_id": "webhook"}, {"$unset": {"live_last_at": "", "live_last_type": ""}})
    log.info("reset test data: %s", out)
    return {"ok": True, "deleted": out}


# ---------- sweep ----------
async def run_sweep(limit: int = 50) -> dict:
    repaired = await repair_pending()
    expired, skipped = 0, 0
    async for o in db.orders.find({"state": "reserved", "hold_expires_at": {"$lt": now()}}).limit(limit):
        if o.get("session_id") and PAYMENTS_CONFIGURED:
            try:
                await asyncio.to_thread(stripe.checkout.Session.expire, o["session_id"])
            except stripe.error.InvalidRequestError:
                try:
                    s = await asyncio.to_thread(stripe.checkout.Session.retrieve, o["session_id"])
                except stripe.error.StripeError:
                    skipped += 1
                    continue
                if s.get("status") == "complete":
                    await reconcile_from_stripe(o)
                    skipped += 1
                    continue
            except stripe.error.StripeError:
                skipped += 1
                continue
        async with LOCK:
            out = await expire_order(o, "sweep: hold past 45 min")
        expired += out["status"] == "processed"
    released = 0
    async for o in db.orders.find({"state": {"$in": ["expired", "failed"]}, "slot": "held", "slot_pending": None}).limit(limit):
        released += await apply_slot_op(o["_id"], "release_hold")
    if PAYMENTS_CONFIGURED:
        async for o in db.orders.find({"fee_actual_cents": None, "payment_intent": {"$regex": "^pi_(?!sim)"}}).limit(10):
            await record_actual_fee(o["_id"], o["payment_intent"])
    await db.meta.update_one({"_id": "sweep"}, {"$set": {"last_run": now(), "last_expired": expired}}, upsert=True)
    return {"expired": expired, "skipped": skipped, "orphans_released": released, "repaired": repaired}


async def sweep_loop():
    while True:
        try:
            r = await run_sweep()
            if any(r.values()):
                log.info("sweep: %s", r)
        except Exception:
            log.exception("sweep failed")
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)


async def seed():
    ship = Ship(slug=SEED_SLUG, title="Shipready Sprint", price_cents=money.PRICE_CENTS, compute_cents=money.COMPUTE_CENTS,
                currency=money.CURRENCY, slots=money.SLOTS, published=True,
                counters={"test": {"sold": 0, "reserved": 0}, "live": {"sold": 0, "reserved": 0}}).to_mongo()
    ship.pop("_id")
    with suppress(DuplicateKeyError):
        await db.ships.update_one({"slug": SEED_SLUG}, {"$setOnInsert": {**ship, "slot_ops": []}}, upsert=True)


app.include_router(api)
app.include_router(desk)
app.include_router(drafts_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origin_regex=".*", allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    await ensure_indexes()
    await seed()
    app.state.sweep_task = asyncio.create_task(sweep_loop())


@app.on_event("shutdown")
async def shutdown():
    app.state.sweep_task.cancel()
    with suppress(asyncio.CancelledError):
        await app.state.sweep_task
    client.close()
