import os
from pathlib import Path

import stripe
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

NAMESPACE = os.environ["SHIPREADY_NAMESPACE"]
OPERATOR_HMAC_SECRET = os.environ["OPERATOR_HMAC_SECRET"]
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PREVIEW_WEBHOOK_SECRET = os.environ.get("STRIPE_PREVIEW_WEBHOOK_SECRET", "")
STRIPE_ACCOUNT_WEBHOOK_SECRET = os.environ.get("STRIPE_ACCOUNT_WEBHOOK_SECRET", "")
STRIPE_WEBHOOK_ENDPOINT_ID = os.environ.get("STRIPE_WEBHOOK_ENDPOINT_ID", "")
SWEEP_INTERVAL_SECONDS = int(os.environ["SWEEP_INTERVAL_SECONDS"])

stripe.api_key = STRIPE_SECRET_KEY
stripe.max_network_retries = 2

PAYMENTS_CONFIGURED = STRIPE_SECRET_KEY.startswith(("sk_live_", "sk_test_", "rk_live_", "rk_test_"))
MODE = "live" if STRIPE_SECRET_KEY.startswith(("sk_live_", "rk_live_")) else "test"
SECRET_SOURCES = [("sandbox", "STRIPE_WEBHOOK_SECRET", STRIPE_WEBHOOK_SECRET),
                  ("preview", "STRIPE_PREVIEW_WEBHOOK_SECRET", STRIPE_PREVIEW_WEBHOOK_SECRET),
                  ("account", "STRIPE_ACCOUNT_WEBHOOK_SECRET", STRIPE_ACCOUNT_WEBHOOK_SECRET)]
WEBHOOK_SECRETS = [(label, value) for label, _, value in SECRET_SOURCES if value]
EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
DRAFTS_MODEL = os.environ["DRAFTS_MODEL"]
