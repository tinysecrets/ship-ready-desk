"""Shipready Stripe simulator. Run from anywhere: python /app/scripts/stripe_sim.py <command> ...

Signed fake events (signed with STRIPE_WEBHOOK_SECRET, posted to the public webhook URL):
  paid <order_id> [--amount N] [--currency usd] [--namespace X] [--livemode] [--pi pi_x]
  pi-succeeded <order_id> [--amount N] [--pi pi_x]
  expire <order_id>                 checkout.session.expired
  async-failed <order_id>           checkout.session.async_payment_failed
  refund <order_id> <amount> [--id re_x] [--status succeeded]
  dispute <order_id> <amount> [--id dp_x]
  dispute-closed <order_id> --id dp_x [--status won|lost]
  unknown-pi                        payment_intent.succeeded for a PI nobody knows
  raw <type> '<object json>' [--event-id evt_x] [--livemode]
  bad-sig                           posts with an invalid signature (expect 400)
  Every command accepts --event-id evt_x so you can replay the exact same event.

Real Stripe test-mode objects (Stripe itself then delivers the webhooks):
  real-pay <order_id> [--dispute]   confirms a real PaymentIntent (pm_card_visa / pm_card_createDispute) with the order metadata
  real-win <dispute_id>             submits winning evidence so Stripe closes the dispute as won
"""
import argparse
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

ENV = dotenv_values(Path(__file__).resolve().parent.parent / "backend" / ".env")
FRONT = dotenv_values(Path(__file__).resolve().parent.parent / "frontend" / ".env")
URL = os.environ.get("WEBHOOK_URL") or FRONT["REACT_APP_BACKEND_URL"].rstrip("/") + "/api/webhooks/stripe"
SECRET = ENV["STRIPE_WEBHOOK_SECRET"]
NS = ENV["SHIPREADY_NAMESPACE"]


def order_doc(order_id):
    from bson import ObjectId
    from pymongo import MongoClient
    o = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]].orders.find_one({"_id": ObjectId(order_id)})
    if not o:
        sys.exit(f"order {order_id} not found")
    return o


def rid(prefix):
    return f"{prefix}_sim{secrets.token_hex(8)}"


def post(event, bad=False):
    payload = json.dumps(event, separators=(",", ":"))
    t = int(time.time())
    sig = hmac.new(SECRET.encode(), f"{t}.{payload}".encode(), hashlib.sha256).hexdigest()
    if bad:
        sig = "0" * 64
    req = urllib.request.Request(URL, data=payload.encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "Stripe/1.0 (+https://stripe.com/docs/webhooks) shipready-sim", "Stripe-Signature": f"t={t},v1={sig}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(r.status, r.read().decode())
    except urllib.error.HTTPError as e:
        print(e.code, e.read().decode())
    print("event_id:", event["id"])


def event(etype, obj, a):
    return {"id": a.event_id or rid("evt"), "object": "event", "type": etype, "livemode": bool(a.livemode),
            "created": int(time.time()), "api_version": "2024-06-20", "data": {"object": obj}}


def md(o, a):
    return {"namespace": a.namespace or NS, "orderId": str(o["_id"])}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd")
    p.add_argument("args", nargs="*")
    p.add_argument("--amount", type=int)
    p.add_argument("--currency", default=None)
    p.add_argument("--namespace")
    p.add_argument("--livemode", action="store_true")
    p.add_argument("--pi")
    p.add_argument("--id")
    p.add_argument("--status")
    p.add_argument("--event-id")
    p.add_argument("--dispute", action="store_true")
    a = p.parse_args()
    c = a.cmd

    if c in ("paid", "pi-succeeded"):
        o = order_doc(a.args[0])
        pi = a.pi or o.get("payment_intent") or rid("pi")
        amt = a.amount if a.amount is not None else o["amount_cents"]
        cur = a.currency or o["currency"]
        if c == "paid":
            obj = {"id": o.get("session_id") or rid("cs"), "object": "checkout.session", "payment_status": "paid", "status": "complete",
                   "amount_total": amt, "currency": cur, "payment_intent": pi, "metadata": md(o, a)}
            post(event("checkout.session.completed", obj, a))
        else:
            obj = {"id": pi, "object": "payment_intent", "status": "succeeded", "amount": amt, "amount_received": amt,
                   "currency": cur, "metadata": md(o, a)}
            post(event("payment_intent.succeeded", obj, a))
        print("payment_intent:", pi)
    elif c in ("expire", "async-failed"):
        o = order_doc(a.args[0])
        obj = {"id": o.get("session_id") or rid("cs"), "object": "checkout.session", "status": "expired",
               "payment_status": "unpaid", "amount_total": o["amount_cents"], "currency": o["currency"], "metadata": md(o, a)}
        post(event("checkout.session.expired" if c == "expire" else "checkout.session.async_payment_failed", obj, a))
    elif c == "refund":
        o = order_doc(a.args[0])
        obj = {"id": a.id or rid("re"), "object": "refund", "status": a.status or "succeeded", "amount": int(a.args[1]),
               "currency": a.currency or o["currency"], "payment_intent": o.get("payment_intent"), "metadata": md(o, a)}
        post(event("refund.updated", obj, a))
        print("refund_id:", obj["id"])
    elif c in ("dispute", "dispute-closed"):
        o = order_doc(a.args[0])
        obj = {"id": a.id or rid("dp"), "object": "dispute", "payment_intent": o.get("payment_intent"),
               "amount": int(a.args[1]) if len(a.args) > 1 else o["amount_cents"], "currency": o["currency"],
               "status": a.status or ("needs_response" if c == "dispute" else "won")}
        post(event("charge.dispute.created" if c == "dispute" else "charge.dispute.closed", obj, a))
        print("dispute_id:", obj["id"])
    elif c == "unknown-pi":
        obj = {"id": rid("pi"), "object": "payment_intent", "status": "succeeded", "amount": 109000, "amount_received": 109000,
               "currency": "usd", "metadata": {}}
        post(event("payment_intent.succeeded", obj, a))
    elif c == "raw":
        post(event(a.args[0], json.loads(a.args[1]), a))
    elif c == "bad-sig":
        post(event("payment_intent.succeeded", {"id": rid("pi"), "object": "payment_intent"}, a), bad=True)
    elif c == "real-pay":
        import stripe
        stripe.api_key = ENV["STRIPE_SECRET_KEY"]
        o = order_doc(a.args[0])
        pi = stripe.PaymentIntent.create(amount=o["amount_cents"], currency=o["currency"], confirm=True,
                                         payment_method="pm_card_createDispute" if a.dispute else "pm_card_visa",
                                         payment_method_types=["card"], metadata={"namespace": NS, "orderId": str(o["_id"])})
        print("real payment_intent:", pi.id, pi.status, "- Stripe will deliver payment_intent.succeeded to the webhook")
    elif c == "real-win":
        import stripe
        stripe.api_key = ENV["STRIPE_SECRET_KEY"]
        d = stripe.Dispute.modify(a.args[0], evidence={"uncategorized_text": "winning_evidence"}, submit=True)
        print("dispute", d.id, d.status, "- Stripe will deliver charge.dispute.closed when it resolves")
    else:
        p.print_help()


if __name__ == "__main__":
    main()
