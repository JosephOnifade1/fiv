"""Billing — Stripe checkout for Pro tier + plan enforcement."""
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest, CheckoutSessionResponse, CheckoutStatusResponse,
)

from auth import get_current_user

STRIPE_API_KEY = os.environ['STRIPE_API_KEY']
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', '').lower().strip()
FREE_SCAN_LIMIT = int(os.environ.get('FREE_SCAN_LIMIT', '5'))
PRO_PRICE_USD = float(os.environ.get('PRO_PRICE_USD', '29.00'))

# Fixed server-side packages — never trust frontend amounts
PACKAGES = {
    "pro_monthly": {"amount": PRO_PRICE_USD, "currency": "usd", "duration_days": 30, "label": "Pro Monthly"},
}

billing_router = APIRouter(prefix="/api/billing")
webhook_router = APIRouter(prefix="/api")


class CheckoutIn(BaseModel):
    package_id: str = "pro_monthly"
    origin_url: str


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def is_pro(user_doc: dict) -> bool:
    """Admin override OR active subscription."""
    if not user_doc:
        return False
    if ADMIN_EMAIL and (user_doc.get("email", "").lower() == ADMIN_EMAIL):
        return True
    if user_doc.get("plan") != "pro":
        return False
    exp = user_doc.get("plan_expires_at")
    if not exp:
        return False
    try:
        if isinstance(exp, str):
            exp_dt = datetime.fromisoformat(exp)
        else:
            exp_dt = exp
        return exp_dt > datetime.now(timezone.utc)
    except Exception:
        return False


async def get_plan_status(user_doc: dict, jobs_col) -> dict:
    """Return current plan, scans used this month, remaining."""
    pro = is_pro(user_doc)
    now = datetime.now(timezone.utc)
    month = _month_key(now)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    scans_used = await jobs_col.count_documents({
        "user_id": user_doc["id"],
        "created_at": {"$gte": month_start},
    })
    return {
        "plan": "pro" if pro else "free",
        "is_admin": ADMIN_EMAIL and user_doc.get("email", "").lower() == ADMIN_EMAIL,
        "scans_used_this_month": scans_used,
        "free_limit": FREE_SCAN_LIMIT,
        "scans_remaining": max(0, FREE_SCAN_LIMIT - scans_used) if not pro else None,
        "plan_expires_at": user_doc.get("plan_expires_at") if not is_pro(user_doc) or ADMIN_EMAIL == user_doc.get("email", "").lower() else user_doc.get("plan_expires_at"),
        "price_usd": PRO_PRICE_USD,
        "current_month": month,
    }


async def assert_can_scan(user_doc: dict, jobs_col):
    """Raise 402 if user is out of free scans and not pro."""
    if is_pro(user_doc):
        return
    status = await get_plan_status(user_doc, jobs_col)
    if status["scans_used_this_month"] >= FREE_SCAN_LIMIT:
        raise HTTPException(
            status_code=402,
            detail={
                "message": f"Free plan limit reached ({FREE_SCAN_LIMIT}/month). Upgrade to Pro for unlimited scans.",
                "code": "PAYMENT_REQUIRED",
                "scans_used": status["scans_used_this_month"],
                "limit": FREE_SCAN_LIMIT,
            },
        )


def make_billing_routes(users_col, payments_col, jobs_col):
    @billing_router.get("/me")
    async def billing_me(user=Depends(get_current_user)):
        doc = await users_col.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})
        if not doc:
            raise HTTPException(404, "User not found")
        return await get_plan_status(doc, jobs_col)

    @billing_router.post("/checkout")
    async def checkout(body: CheckoutIn, http_request: Request, user=Depends(get_current_user)):
        pkg = PACKAGES.get(body.package_id)
        if not pkg:
            raise HTTPException(400, "Invalid package")
        origin = body.origin_url.rstrip("/")
        host_url = str(http_request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
        success_url = f"{origin}/?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = origin + "/"
        req = CheckoutSessionRequest(
            amount=pkg["amount"],
            currency=pkg["currency"],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_id": user["id"],
                "user_email": user["email"],
                "package_id": body.package_id,
            },
        )
        session: CheckoutSessionResponse = await stripe.create_checkout_session(req)
        await payments_col.insert_one({
            "id": str(uuid.uuid4()),
            "session_id": session.session_id,
            "user_id": user["id"],
            "user_email": user["email"],
            "package_id": body.package_id,
            "amount": pkg["amount"],
            "currency": pkg["currency"],
            "status": "initiated",
            "payment_status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": req.metadata or {},
        })
        return {"url": session.url, "session_id": session.session_id}

    @billing_router.get("/status/{session_id}")
    async def status(session_id: str, http_request: Request, user=Depends(get_current_user)):
        tx = await payments_col.find_one({"session_id": session_id, "user_id": user["id"]}, {"_id": 0})
        if not tx:
            raise HTTPException(404, "Transaction not found")

        # Idempotent: if already processed, return current state
        if tx.get("payment_status") == "paid" and tx.get("plan_applied"):
            return {"payment_status": "paid", "status": tx.get("status"), "plan_applied": True}

        host_url = str(http_request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
        st: CheckoutStatusResponse = await stripe.get_checkout_status(session_id)

        new_status = st.status
        new_payment_status = st.payment_status
        update = {
            "status": new_status,
            "payment_status": new_payment_status,
            "amount_total": st.amount_total,
            "currency": st.currency,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        plan_applied = bool(tx.get("plan_applied"))
        if new_payment_status == "paid" and not plan_applied:
            # Grant Pro
            pkg = PACKAGES.get(tx.get("package_id", "pro_monthly"), PACKAGES["pro_monthly"])
            new_expiry = datetime.now(timezone.utc) + timedelta(days=pkg["duration_days"])
            await users_col.update_one(
                {"id": user["id"]},
                {"$set": {"plan": "pro", "plan_expires_at": new_expiry.isoformat()}},
            )
            update["plan_applied"] = True
            plan_applied = True

        await payments_col.update_one({"session_id": session_id}, {"$set": update})
        return {
            "payment_status": new_payment_status,
            "status": new_status,
            "plan_applied": plan_applied,
        }

    @webhook_router.post("/webhook/stripe")
    async def stripe_webhook(request: Request):
        body = await request.body()
        sig = request.headers.get("Stripe-Signature", "")
        host_url = str(request.base_url).rstrip("/")
        webhook_url = f"{host_url}/api/webhook/stripe"
        stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
        try:
            evt = await stripe.handle_webhook(body, sig)
        except Exception:
            raise HTTPException(400, "Invalid webhook")

        if evt.payment_status == "paid" and evt.session_id:
            tx = await payments_col.find_one({"session_id": evt.session_id})
            if tx and not tx.get("plan_applied"):
                pkg = PACKAGES.get(tx.get("package_id", "pro_monthly"), PACKAGES["pro_monthly"])
                new_expiry = datetime.now(timezone.utc) + timedelta(days=pkg["duration_days"])
                await users_col.update_one(
                    {"id": tx["user_id"]},
                    {"$set": {"plan": "pro", "plan_expires_at": new_expiry.isoformat()}},
                )
                await payments_col.update_one(
                    {"session_id": evt.session_id},
                    {"$set": {"payment_status": "paid", "plan_applied": True,
                              "webhook_at": datetime.now(timezone.utc).isoformat()}},
                )
        return {"received": True}

    return billing_router, webhook_router
