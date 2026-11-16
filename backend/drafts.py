"""AI drafts outbox. Reads orders/certificates/ships only; writes prospects and drafts only. Never sends anything."""
import logging
import re
from typing import Optional

from bson import ObjectId
from emergentintegrations.llm.chat import LlmChat, StreamDone, TextDelta, UserMessage
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

import money
from auth import require_operator
from config import DRAFTS_MODEL, EMERGENT_LLM_KEY
from db import BaseDocument, PyObjectId, db, now
from datetime import datetime

log = logging.getLogger("drafts")
router = APIRouter(prefix="/api/desk", dependencies=[Depends(require_operator)], tags=["drafts"])
STORE_SLUG = "shipready-sprint"
FAILED = "Draft failed — try again"
FORBIDDEN = re.compile(r"guarantee|passive income|make \$|earn \$|\d+x (your|revenue|income)|testimonial|\"[^\"]{10,}\" ?[-—–] ?[A-Z]", re.I)


class Prospect(BaseDocument):
    handle: str
    reason: str
    created_at: datetime


class Draft(BaseDocument):
    _oid_fields = ("ref_id",)
    kind: str
    target: str
    ref_id: PyObjectId
    text: str
    status: str = "draft"
    model: str
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None


def oid(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(404, "not found")
    return ObjectId(value)


def base_url(request: Request) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{'http' if host.startswith(('localhost', '127.')) else 'https'}://{host}"


def parse_prospects(text: str) -> tuple[list[tuple[str, str]], int]:
    good, skipped = [], 0
    for line in text.splitlines():
        if not line.strip():
            continue
        handle, sep, reason = line.partition("|")
        if not sep or not handle.strip():
            skipped += 1
            continue
        good.append((handle.strip()[:120], reason.strip()[:500]))
    return good, skipped


async def generate(system: str, prompt: str, session_id: str) -> str:
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=session_id, system_message=system).with_model("anthropic", DRAFTS_MODEL)
    parts = []
    async for ev in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(ev, TextDelta):
            parts.append(ev.content)
        elif isinstance(ev, StreamDone):
            break
    return "".join(parts).strip()


async def write_checked(system: str, prompt: str, session_id: str, required: list[str], simulate_fail: bool) -> str:
    if simulate_fail:
        raise HTTPException(503, FAILED)
    for attempt in range(2):
        try:
            text = await generate(system, prompt, f"{session_id}:{attempt}")
        except Exception as exc:
            log.warning("draft generation failed: %s", exc)
            raise HTTPException(503, FAILED)
        missing = [r for r in required if r not in text]
        if text and not missing and not FORBIDDEN.search(text):
            return text
        log.info("draft rejected (missing=%s forbidden=%s); retrying", missing, bool(FORBIDDEN.search(text or "")))
        prompt += f"\n\nYour previous draft was rejected. It must contain these exact strings: {', '.join(required)}. It must not mention guarantees, income, results promises or testimonials."
    raise HTTPException(503, FAILED)


async def save_draft(kind: str, target: str, ref_id, text: str) -> dict:
    t = now()
    d = Draft(kind=kind, target=target, ref_id=str(ref_id), text=text, model=DRAFTS_MODEL, created_at=t, updated_at=t).to_mongo()
    await db.drafts.insert_one(d)
    return Draft.from_mongo(d).model_dump()


OUTREACH_SYSTEM = """You write short, honest, first-person cold outreach DMs for a solo operator. Plain text, no subject line, under 110 words, no emojis, no hashtags.
Hard rules:
- State the facts exactly as given: offer name, price, number of slots, store link.
- Never promise income, revenue, results, ROI or outcomes. Never use the word "guarantee".
- Never invent testimonials, clients, case studies, numbers or social proof.
- Personalise only from the prospect note provided; do not invent details about them.
- End with a low-pressure question. Output only the message text."""

DELIVERY_SYSTEM = """You write a short, warm, factual delivery note from a solo operator to a buyer who just paid. Plain text, under 120 words, no emojis.
Hard rules: include the certificate code and the certificate link exactly as given; thank them; say the operator will reach out personally to schedule the work.
Never promise outcomes or results, never invent details, never mention guarantees. Output only the message text."""


class ProspectsBody(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


@router.post("/prospects")
async def add_prospects(body: ProspectsBody):
    good, skipped = parse_prospects(body.text)
    t = now()
    docs = [Prospect(handle=h, reason=r, created_at=t).to_mongo() for h, r in good]
    if docs:
        await db.prospects.insert_many(docs)
    return {"created": [Prospect.from_mongo(d).model_dump() for d in docs], "skipped": skipped,
            "message": f"{len(docs)} saved · {skipped} lines skipped"}


@router.get("/prospects")
async def list_prospects():
    docs = await db.prospects.find({}).sort("created_at", -1).to_list(500)
    return {"prospects": [Prospect.from_mongo(d).model_dump() for d in docs]}


@router.delete("/prospects/{prospect_id}")
async def delete_prospect(prospect_id: str):
    await db.prospects.delete_one({"_id": oid(prospect_id)})
    return {"ok": True}


@router.post("/prospects/{prospect_id}/outreach")
async def write_outreach(prospect_id: str, request: Request, x_simulate_ai_failure: Optional[str] = Header(default=None)):
    p = await db.prospects.find_one({"_id": oid(prospect_id)})
    if not p:
        raise HTTPException(404, "prospect not found")
    ship = await db.ships.find_one({"slug": STORE_SLUG, "published": True})
    if not ship:
        raise HTTPException(409, "store ship not found")
    price = f"${ship['price_cents'] // 100:,}"
    link = f"{base_url(request)}/s/{STORE_SLUG}"
    slots = f"{ship['slots']} slots"
    prompt = (f"Offer: {ship['title']} — a done-with-you sprint to get the prospect's product ship-ready.\n"
              f"Price: {price} (write it exactly as {price}). Capacity: {slots} total (write \"{slots}\"); do not state how many are currently open.\n"
              f"Store link: {link}\nProspect handle: {p['handle']}\nWhy I'm reaching out (operator note): {p['reason'] or 'none given'}")
    text = await write_checked(OUTREACH_SYSTEM, prompt, f"outreach:{prospect_id}", [price, slots, link], bool(x_simulate_ai_failure))
    return await save_draft("outreach", p["handle"], p["_id"], text)


@router.post("/orders/{order_id}/delivery-note")
async def write_delivery_note(order_id: str, request: Request, x_simulate_ai_failure: Optional[str] = Header(default=None)):
    order = await db.orders.find_one({"_id": oid(order_id)}, {"state": 1, "cert_code": 1, "ship_title": 1})
    if not order:
        raise HTTPException(404, "order not found")
    if order["state"] not in ("paid", "disputed") or not order.get("cert_code"):
        raise HTTPException(409, f"order is {order['state']}; delivery notes are for paid orders")
    code = order["cert_code"]
    link = f"{base_url(request)}/p/{code}"
    prompt = f"Offer bought: {order['ship_title']} ({money.SLOTS} slots total).\nCertificate code: {code}\nCertificate link: {link}"
    text = await write_checked(DELIVERY_SYSTEM, prompt, f"delivery:{order_id}", [code, link], bool(x_simulate_ai_failure))
    return await save_draft("delivery", code, order["_id"], text)


@router.get("/drafts")
async def list_drafts(status: Optional[str] = None):
    q = {"status": status} if status in ("draft", "approved", "discarded") else {}
    docs = await db.drafts.find(q).sort("created_at", -1).to_list(500)
    return {"drafts": [Draft.from_mongo(d).model_dump() for d in docs]}


class DraftEdit(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


async def update_draft(draft_id: str, allowed: list[str], update: dict) -> dict:
    d = await db.drafts.find_one_and_update({"_id": oid(draft_id), "status": {"$in": allowed}},
                                            {"$set": {**update, "updated_at": now()}}, return_document=ReturnDocument.AFTER)
    if not d:
        existing = await db.drafts.find_one({"_id": oid(draft_id)})
        raise HTTPException(404 if not existing else 409, "draft not found" if not existing else f"draft is {existing['status']}")
    return Draft.from_mongo(d).model_dump()


@router.patch("/drafts/{draft_id}")
async def edit_draft(draft_id: str, body: DraftEdit):
    return await update_draft(draft_id, ["draft", "approved"], {"text": body.text.strip(), "status": "draft", "approved_at": None})


@router.post("/drafts/{draft_id}/approve")
async def approve_draft(draft_id: str):
    return await update_draft(draft_id, ["draft", "approved"], {"status": "approved", "approved_at": now()})


@router.post("/drafts/{draft_id}/discard")
async def discard_draft(draft_id: str):
    return await update_draft(draft_id, ["draft", "approved"], {"status": "discarded"})
