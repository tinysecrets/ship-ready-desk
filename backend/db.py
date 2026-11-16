import logging
import os
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from pymongo import ASCENDING, DESCENDING, IndexModel

import config  # noqa: F401  loads .env

client = AsyncIOMotorClient(os.environ["MONGO_URL"], tz_aware=True)
db = client[os.environ["DB_NAME"]]

INDEXES: dict[str, list[IndexModel]] = {
    "ships": [IndexModel([("slug", ASCENDING)], name="slug_u", unique=True)],
    "orders": [
        IndexModel([("idem_key", ASCENDING)], name="idem_key_u", unique=True),
        IndexModel([("payment_intent", ASCENDING)], name="pi"),
        IndexModel([("session_id", ASCENDING)], name="session"),
        IndexModel([("state", ASCENDING), ("hold_expires_at", ASCENDING)], name="state_hold"),
        IndexModel([("mode", ASCENDING), ("created_at", DESCENDING)], name="mode_created"),
        IndexModel([("slot_pending", ASCENDING)], name="slot_pending"),
    ],
    "ledger": [
        IndexModel([("op_key", ASCENDING)], name="op_key_u", unique=True),
        IndexModel([("mode", ASCENDING), ("kind", ASCENDING)], name="mode_kind"),
        IndexModel([("order_id", ASCENDING)], name="order"),
    ],
    "webhook_inbox": [
        IndexModel([("event_id", ASCENDING)], name="event_id_u", unique=True),
        IndexModel([("status", ASCENDING), ("received_at", DESCENDING)], name="status_received"),
    ],
    "certificates": [
        IndexModel([("code", ASCENDING)], name="code_u", unique=True),
        IndexModel([("order_id", ASCENDING)], name="order_u", unique=True),
        IndexModel([("issued_at", DESCENDING)], name="issued_desc"),
    ],
    "refund_requests": [IndexModel([("key", ASCENDING)], name="key_u", unique=True)],
    "webhook_sig_failures": [IndexModel([("at", DESCENDING)], name="at_desc")],
    "prospects": [IndexModel([("created_at", DESCENDING)], name="created_desc")],
    "drafts": [
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)], name="status_created"),
        IndexModel([("kind", ASCENDING), ("ref_id", ASCENDING)], name="kind_ref"),
    ],
}


async def ensure_indexes() -> None:
    for collection, models in INDEXES.items():
        for model in models:
            try:
                await db[collection].create_indexes([model])
            except Exception as exc:
                logging.getLogger(__name__).error("ensure_indexes(%s.%s): %s", collection, model.document["name"], exc)


def now() -> datetime:
    return datetime.now(timezone.utc)


PyObjectId = Annotated[str, BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)]


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    _oid_fields: tuple = ()

    @classmethod
    def from_mongo(cls, doc: Optional[dict]):
        return cls.model_validate(doc) if doc else None

    def to_mongo(self) -> dict[str, Any]:
        d = self.model_dump(by_alias=True)
        d["_id"] = ObjectId(d["_id"]) if d.get("_id") else ObjectId()
        for f in self._oid_fields:
            if d.get(f):
                d[f] = ObjectId(d[f])
        return d


class Ship(BaseDocument):
    slug: str
    title: str
    price_cents: int
    compute_cents: int
    currency: str
    slots: int
    published: bool = True
    counters: dict = Field(default_factory=dict)


class Order(BaseDocument):
    _oid_fields = ("ship_id",)
    ship_id: PyObjectId
    ship_slug: str
    ship_title: str
    mode: str
    namespace: str
    idem_key: str
    state: str
    slot: str = "none"
    slot_pending: Optional[str] = None
    amount_cents: int
    currency: str
    origin: str
    hold_expires_at: datetime
    created_at: datetime
    session_id: Optional[str] = None
    session_url: Optional[str] = None
    payment_intent: Optional[str] = None
    refunded_cents: int = 0
    disputed_cents: int = 0
    dispute_status: Optional[str] = None
    applied_ops: list[str] = Field(default_factory=list)
    cert_code: Optional[str] = None
    fee_actual_cents: Optional[int] = None
    over_capacity: bool = False
    paid_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    expire_reason: Optional[str] = None


class LedgerEntry(BaseDocument):
    _oid_fields = ("order_id", "ship_id")
    op_key: str
    kind: str
    order_id: PyObjectId
    ship_id: PyObjectId
    mode: str
    amount_cents: int
    fee_est_cents: int = 0
    compute_cents: int = 0
    currency: str
    stripe_ref: str
    event_id: Optional[str] = None
    created_at: datetime


class Certificate(BaseDocument):
    _oid_fields = ("order_id", "ship_id")
    code: str
    order_id: PyObjectId
    ship_id: PyObjectId
    ship_title: str
    mode: str
    amount_cents: int
    currency: str
    revoked: bool = False
    revoked_at: Optional[datetime] = None
    issued_at: datetime
