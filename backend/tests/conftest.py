"""
pytest conftest — adds backend/ to sys.path so tests can import scraper, auth, etc.
directly without a running server.
"""
import sys
import os
from pathlib import Path

# Make "backend/" importable
backend_dir = Path(__file__).parent.parent  # backend/tests/../ = backend/
sys.path.insert(0, str(backend_dir))

# Stub out motor (MongoDB async driver) so scraper.py can be imported without a DB
import types
motor_stub = types.ModuleType("motor")
motor_stub.motor_asyncio = types.ModuleType("motor.motor_asyncio")
motor_stub.motor_asyncio.AsyncIOMotorClient = object
sys.modules.setdefault("motor", motor_stub)
sys.modules.setdefault("motor.motor_asyncio", motor_stub.motor_asyncio)

# Stub out emergentintegrations if not installed
if "emergentintegrations" not in sys.modules:
    ei = types.ModuleType("emergentintegrations")
    ei.payments = types.ModuleType("emergentintegrations.payments")
    ei.payments.stripe = types.ModuleType("emergentintegrations.payments.stripe")
    ei.payments.stripe.checkout = types.ModuleType("emergentintegrations.payments.stripe.checkout")
    ei.llm = types.ModuleType("emergentintegrations.llm")
    ei.llm.chat = types.ModuleType("emergentintegrations.llm.chat")

    class _LlmChat:
        pass

    ei.llm.chat.LlmChat = _LlmChat

    class _CheckoutSession:
        pass

    ei.payments.stripe.checkout.StripeCheckout = _CheckoutSession
    ei.payments.stripe.checkout.CheckoutSessionRequest = _CheckoutSession
    ei.payments.stripe.checkout.CheckoutSessionResponse = _CheckoutSession
    ei.payments.stripe.checkout.CheckoutStatusResponse = _CheckoutSession
    sys.modules["emergentintegrations"] = ei
    sys.modules["emergentintegrations.payments"] = ei.payments
    sys.modules["emergentintegrations.payments.stripe"] = ei.payments.stripe
    sys.modules["emergentintegrations.payments.stripe.checkout"] = ei.payments.stripe.checkout
    sys.modules["emergentintegrations.llm"] = ei.llm
    sys.modules["emergentintegrations.llm.chat"] = ei.llm.chat

# Stub playwright if not installed (scraper.py no longer uses it, but guard just in case)
if "playwright" not in sys.modules:
    pw = types.ModuleType("playwright")
    pw.async_api = types.ModuleType("playwright.async_api")
    sys.modules.setdefault("playwright", pw)
    sys.modules.setdefault("playwright.async_api", pw.async_api)

# Provide minimal env vars that auth.py / billing.py expect at import time
os.environ.setdefault("JWT_SECRET", "test-secret-for-offline-tests")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("STRIPE_API_KEY", "sk_test_offline")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "test_db")

