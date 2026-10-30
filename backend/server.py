"""Fiverr Niche Arbitrage SaaS — FastAPI backend."""
import os
import csv
import io
import json
import uuid
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from auth import (
    hash_password, verify_password, create_token, get_current_user,
)
from scraper import deep_scrape, compute_opportunity, fetch_autocomplete
from ai_insights import (
    expand_keywords, summarize_report, suggest_pivots,
    trend_verdict_2026, proximity_map,
)
from billing import make_billing_routes, assert_can_scan
from live_pipeline import make_live_routes
from gig_builder import make_gig_routes

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("fiverr-scout")

# --- Mongo ---
try:
    import certifi
    CA_FILE = certifi.where()
except Exception:
    CA_FILE = None

mongo_url = os.environ['MONGO_URL']
if CA_FILE and ('mongodb.net' in mongo_url or 'ssl=true' in mongo_url.lower()):
    client = AsyncIOMotorClient(mongo_url, tlsCAFile=CA_FILE)
else:
    client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]
users_col = db.fs_users
jobs_col = db.fs_jobs
watch_col = db.fs_watchlist
trend_col = db.fs_trends
payments_col = db.fs_payments
market_col = db.market_insights
tasks_col = db.fs_scan_tasks
referral_col = db.fs_referrals

app = FastAPI(title="Fiverr Niche Arbitrage Scout")
api = APIRouter(prefix="/api")


# ============ MODELS ============
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: Optional[str] = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class AuthOut(BaseModel):
    token: str
    user: dict


class SearchIn(BaseModel):
    keyword: str = Field(min_length=2, max_length=120)


class WatchlistIn(BaseModel):
    keyword: str
    note: Optional[str] = None


class ExpandIn(BaseModel):
    keyword: str
    gig_titles: list[str] = []


class SummarizeIn(BaseModel):
    job_id: str


class PivotIn(BaseModel):
    job_id: str


class AutocompleteIn(BaseModel):
    query: str
    proxy_region: Optional[str] = None


class ProximityIn(BaseModel):
    job_id: str


# ============ AUTH ============
@api.post("/auth/register", response_model=AuthOut)
async def register(body: RegisterIn):
    existing = await users_col.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    uid = str(uuid.uuid4())
    doc = {
        "id": uid,
        "email": body.email.lower(),
        "name": body.name or body.email.split("@")[0],
        "password_hash": hash_password(body.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await users_col.insert_one(doc)
    token = create_token(uid, doc["email"])
    return {"token": token, "user": {"id": uid, "email": doc["email"], "name": doc["name"]}}


@api.post("/auth/login", response_model=AuthOut)
async def login(body: LoginIn):
    doc = await users_col.find_one({"email": body.email.lower()}, {"_id": 0})
    if not doc or not verify_password(body.password, doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(doc["id"], doc["email"])
    return {"token": token, "user": {"id": doc["id"], "email": doc["email"], "name": doc.get("name")}}


@api.get("/auth/me")
async def me(user=Depends(get_current_user)):
    doc = await users_col.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="User not found")
    return doc


# ============ SCRAPE JOBS ============
async def _run_scrape(job_id: str, keyword: str, user_id: str):
    try:
        # Pull prior median price for inflation tracking
        prior = await trend_col.find(
            {"user_id": user_id, "keyword": keyword.lower()}, {"_id": 0, "median_price": 1}
        ).sort("captured_at", -1).limit(1).to_list(1)
        prior_median = (prior[0].get("median_price") if prior else None)

        result = await deep_scrape(keyword, prior_median_price=prior_median)
        await trend_col.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "keyword": keyword.lower(),
            "total_services": result["total_services"],
            "avg_orders_in_queue": result["metrics"]["avg_orders_in_queue"],
            "opportunity_score": result["opportunity_score"],
            "velocity_score": result.get("velocity_score", 0),
            "median_price": result["metrics"].get("median_price", 0),
            "saturation_index": result.get("saturation_index", 0),
            "captured_at": datetime.now(timezone.utc).isoformat(),
        })
        await jobs_col.update_one(
            {"id": job_id},
            {"$set": {"status": "complete", "result": result,
                      "completed_at": datetime.now(timezone.utc).isoformat()}},
        )
    except Exception as e:
        logger.exception("scrape failed")
        await jobs_col.update_one(
            {"id": job_id},
            {"$set": {"status": "failed", "error": str(e),
                      "completed_at": datetime.now(timezone.utc).isoformat()}},
        )


@api.post("/scrape/search")
async def start_search(body: SearchIn, bg: BackgroundTasks, user=Depends(get_current_user)):
    # Plan enforcement
    user_doc = await users_col.find_one({"id": user["id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(404, "User not found")
    await assert_can_scan(user_doc, jobs_col)

    job_id = str(uuid.uuid4())
    doc = {
        "id": job_id,
        "user_id": user["id"],
        "keyword": body.keyword.strip(),
        "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": None,
    }
    await jobs_col.insert_one(doc)
    bg.add_task(_run_scrape, job_id, body.keyword.strip(), user["id"])
    return {"job_id": job_id, "status": "running"}


@api.get("/scrape/jobs/{job_id}")
async def get_job(job_id: str, user=Depends(get_current_user)):
    doc = await jobs_col.find_one({"id": job_id, "user_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Job not found")
    return doc


@api.get("/scrape/jobs")
async def list_jobs(user=Depends(get_current_user)):
    docs = await jobs_col.find(
        {"user_id": user["id"]}, {"_id": 0, "result.gigs": 0, "result.tags": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    return docs


@api.get("/scrape/jobs/{job_id}/export")
async def export_job(job_id: str, format: str = "csv", user=Depends(get_current_user)):
    doc = await jobs_col.find_one({"id": job_id, "user_id": user["id"]}, {"_id": 0})
    if not doc or not doc.get("result"):
        raise HTTPException(status_code=404, detail="Job not found or not complete")

    result = doc["result"]
    filename_base = f"fiverr_scout_{doc['keyword'].replace(' ', '_')}_{job_id[:8]}"

    if format == "json":
        buf = io.BytesIO(json.dumps(result, indent=2).encode())
        return StreamingResponse(
            buf, media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.json"'},
        )

    # CSV
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "position", "title", "seller_level", "is_fiverr_pro", "price_from",
        "orders_in_queue", "favourites", "rating", "reviews_count",
        "last_review_at", "delivery_days",
    ])
    for g in result.get("gigs", []):
        writer.writerow([
            g.get("position"), g.get("title"), g.get("seller_level"),
            g.get("is_fiverr_pro"), g.get("price_from"), g.get("orders_in_queue"),
            g.get("favourites"), g.get("rating"), g.get("reviews_count"),
            g.get("last_review_at"), g.get("delivery_days"),
        ])
    writer.writerow([])
    writer.writerow(["KEYWORD", doc["keyword"]])
    writer.writerow(["OPPORTUNITY_SCORE", result.get("opportunity_score")])
    writer.writerow(["COMPETITION_TO_ORDER_RATIO", result.get("competition_to_order_ratio")])
    writer.writerow(["TOTAL_SERVICES", result.get("total_services")])
    writer.writerow(["DATA_SOURCE", result.get("data_source")])

    return StreamingResponse(
        io.BytesIO(out.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename_base}.csv"'},
    )


# ============ WATCHLIST ============
@api.post("/watchlist")
async def add_watch(body: WatchlistIn, user=Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "keyword": body.keyword.strip(),
        "note": body.note or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await watch_col.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.get("/watchlist")
async def list_watch(user=Depends(get_current_user)):
    items = await watch_col.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    # Attach latest trend data
    for it in items:
        latest = await trend_col.find(
            {"user_id": user["id"], "keyword": it["keyword"].lower()},
            {"_id": 0},
        ).sort("captured_at", -1).limit(2).to_list(2)
        it["latest_snapshot"] = latest[0] if latest else None
        if len(latest) >= 2:
            cur = latest[0]["total_services"] or 0
            prev = latest[1]["total_services"] or 0
            it["week_over_week_pct"] = round(((cur - prev) / max(1, prev)) * 100, 2) if prev else 0
        else:
            it["week_over_week_pct"] = None
    return items


@api.delete("/watchlist/{wid}")
async def del_watch(wid: str, user=Depends(get_current_user)):
    res = await watch_col.delete_one({"id": wid, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"deleted": True}


# ============ TRENDS ============
@api.get("/focus-keywords")
async def focus_keywords(user=Depends(get_current_user), sort_by: str = "opportunity_score"):
    """Top focus keywords across all completed jobs for the user.

    sort_by: opportunity_score | orders | favourites | reviews
    """
    docs = await jobs_col.find(
        {"user_id": user["id"], "status": "complete"}, {"_id": 0}
    ).sort("created_at", -1).limit(100).to_list(100)

    # Deduplicate by keyword keeping most recent
    seen = {}
    for d in docs:
        kw = d["keyword"].lower()
        if kw in seen:
            continue
        r = d.get("result") or {}
        gigs = r.get("gigs", []) or []
        seen[kw] = {
            "keyword": d["keyword"],
            "job_id": d["id"],
            "scanned_at": d.get("created_at"),
            "opportunity_score": r.get("opportunity_score", 0),
            "competition_to_order_ratio": r.get("competition_to_order_ratio", 0),
            "ratio_is_gold": r.get("ratio_is_gold", False),
            "total_services": (r.get("metrics") or {}).get("total_services", 0),
            "avg_orders": sum(g.get("orders_in_queue", 0) for g in gigs) / max(1, len(gigs)),
            "total_favourites": sum(g.get("favourites", 0) for g in gigs),
            "total_reviews": sum(g.get("reviews_count", 0) for g in gigs),
            "data_source": r.get("data_source"),
        }

    items = list(seen.values())
    key_map = {
        "opportunity_score": "opportunity_score",
        "orders": "avg_orders",
        "favourites": "total_favourites",
        "reviews": "total_reviews",
    }
    key = key_map.get(sort_by, "opportunity_score")
    items.sort(key=lambda x: x.get(key, 0), reverse=True)
    return {"sort_by": sort_by, "items": items[:25]}


@api.get("/trends/{keyword}")
async def get_trends(keyword: str, user=Depends(get_current_user)):
    snaps = await trend_col.find(
        {"user_id": user["id"], "keyword": keyword.lower()}, {"_id": 0},
    ).sort("captured_at", 1).to_list(200)
    return {"keyword": keyword, "snapshots": snaps}


# ============ AI ============
@api.post("/ai/expand")
async def ai_expand(body: ExpandIn, user=Depends(get_current_user)):
    return await expand_keywords(body.keyword, body.gig_titles)


@api.post("/ai/summarize")
async def ai_summarize(body: SummarizeIn, user=Depends(get_current_user)):
    doc = await jobs_col.find_one({"id": body.job_id, "user_id": user["id"]}, {"_id": 0})
    if not doc or not doc.get("result"):
        raise HTTPException(status_code=404, detail="Job not ready")
    r = doc["result"]
    analytics = {
        "opportunity_score": r["opportunity_score"],
        "breakdown": r["breakdown"],
        "competition_to_order_ratio": r["competition_to_order_ratio"],
        "metrics": r["metrics"],
    }
    return await summarize_report(doc["keyword"], analytics, r.get("gigs", []))


@api.post("/ai/pivots")
async def ai_pivots(body: PivotIn, user=Depends(get_current_user)):
    doc = await jobs_col.find_one({"id": body.job_id, "user_id": user["id"]}, {"_id": 0})
    if not doc or not doc.get("result"):
        raise HTTPException(status_code=404, detail="Job not ready")
    r = doc["result"]
    analytics = {
        "competition_to_order_ratio": r["competition_to_order_ratio"],
        "metrics": r["metrics"],
    }
    return await suggest_pivots(doc["keyword"], analytics, r.get("tags", []))


@api.post("/ai/trend-verdict")
async def ai_trend_verdict(body: PivotIn, user=Depends(get_current_user)):
    doc = await jobs_col.find_one({"id": body.job_id, "user_id": user["id"]}, {"_id": 0})
    if not doc or not doc.get("result"):
        raise HTTPException(status_code=404, detail="Job not ready")
    r = doc["result"]
    return await trend_verdict_2026(doc["keyword"], r)


@api.post("/autocomplete")
async def autocomplete(body: AutocompleteIn, user=Depends(get_current_user)):
    if not body.query or len(body.query) < 2:
        return {"source": "skip", "suggestions": []}
    return await fetch_autocomplete(body.query, proxy_region=body.proxy_region)


@api.post("/ai/proximity")
async def ai_proximity(body: ProximityIn, user=Depends(get_current_user)):
    doc = await jobs_col.find_one({"id": body.job_id, "user_id": user["id"]}, {"_id": 0})
    if not doc or not doc.get("result"):
        raise HTTPException(status_code=404, detail="Job not ready")
    r = doc["result"]
    auto = await fetch_autocomplete(doc["keyword"])
    return {
        "autocomplete": auto,
        "map": await proximity_map(doc["keyword"], auto.get("suggestions", []), r.get("metrics", {})),
    }


@api.get("/")
async def root():
    return {"name": "Fiverr Niche Arbitrage Scout", "ok": True}


app.include_router(api)
billing_router, webhook_router = make_billing_routes(users_col, payments_col, jobs_col)
app.include_router(billing_router)
app.include_router(webhook_router)
niches_router, referral_router = make_live_routes(users_col, jobs_col, market_col, tasks_col, referral_col)
app.include_router(niches_router)
app.include_router(referral_router)
app.include_router(make_gig_routes(users_col, jobs_col, db.fs_gig_setups))
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown():
    client.close()
