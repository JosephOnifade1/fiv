"""
Fiverr deep scraper.

Real Playwright stealth scraper + deterministic seeded simulator fallback.
Fiverr aggressively detects datacenter IPs / automation; without residential proxies
the live scrape will frequently hit captchas. When that happens we transparently
fall back to a deterministic data generator (seeded by keyword) so downstream
analytics and the Opportunity Score engine remain fully functional.

Every result is labeled with `data_source`: "live" or "simulated_fallback".
"""
from __future__ import annotations

import asyncio
import hashlib
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote_plus

# Playwright is optional at import time so the API stays up if browsers aren't installed
try:
    from playwright.async_api import async_playwright  # type: ignore
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

SELLER_LEVELS = ["New Seller", "Level 1", "Level 2", "Top Rated", "Fiverr Pro"]


def _seed(keyword: str) -> random.Random:
    h = int(hashlib.sha256(keyword.lower().encode()).hexdigest(), 16)
    return random.Random(h)


# ---------- LIVE PLAYWRIGHT SCRAPER ----------
async def _live_scrape(keyword: str, max_pages: int = 1) -> Optional[dict]:
    """Try real Fiverr scrape with stealth. Returns None if blocked."""
    if not PLAYWRIGHT_AVAILABLE:
        return None

    rnd = _seed(keyword)
    ua = rnd.choice(USER_AGENTS)
    search_url = f"https://www.fiverr.com/search/gigs?query={quote_plus(keyword)}"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )
            context = await browser.new_context(
                user_agent=ua,
                viewport={"width": 1366, "height": 850},
                locale="en-US",
            )
            # Stealth-ish: hide webdriver
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            page = await context.new_page()

            # Human-like: land on homepage first
            await page.goto("https://www.fiverr.com", timeout=20000, wait_until="domcontentloaded")
            await asyncio.sleep(rnd.uniform(0.8, 1.6))

            await page.goto(search_url, timeout=25000, wait_until="domcontentloaded")
            await asyncio.sleep(rnd.uniform(1.0, 2.0))

            html = await page.content()
            blocked = (
                "Verify you are human" in html
                or "captcha" in html.lower()
                or "/checkpoint/" in page.url
                or len(html) < 2000
            )
            if blocked:
                await browser.close()
                return None

            # Smooth scroll to trigger lazy load
            for _ in range(4):
                await page.mouse.wheel(0, 800)
                await asyncio.sleep(rnd.uniform(0.3, 0.7))

            # Total count — best effort
            total = None
            try:
                txt = await page.text_content("[data-testid='results-count']") or ""
                m = re.search(r"([\d,]+)", txt)
                if m:
                    total = int(m.group(1).replace(",", ""))
            except Exception:
                pass

            # Gig cards — best-effort generic selectors
            gigs = []
            cards = await page.query_selector_all("[data-testid*='gig-card'], .gig-card-layout, [class*='GigCard']")
            for card in cards[:20]:
                try:
                    title = (await card.text_content() or "").strip()[:140]
                    price_match = re.search(r"\$\s?(\d+)", title)
                    price = int(price_match.group(1)) if price_match else None
                    gigs.append({"title": title, "price_from": price})
                except Exception:
                    continue

            await browser.close()

            if not gigs:
                return None

            return {
                "data_source": "live",
                "total_services": total,
                "raw_gigs": gigs,
            }
    except Exception:
        return None


# ---------- DETERMINISTIC SIMULATOR (fallback) ----------
def _simulate(keyword: str) -> dict:
    """Realistic, deterministic data based on keyword hash."""
    rnd = _seed(keyword)

    word_count = len(keyword.split())
    # Long-tail keywords have less competition
    if word_count >= 4:
        total = rnd.randint(80, 900)
    elif word_count == 3:
        total = rnd.randint(400, 3500)
    elif word_count == 2:
        total = rnd.randint(1500, 12000)
    else:
        total = rnd.randint(5000, 60000)

    # Generate 20 gigs (top 10 + bottom 10 of first page)
    gigs = []
    title_templates = [
        f"I will create a professional {keyword}",
        f"I will design custom {keyword} for your business",
        f"I will deliver high quality {keyword} fast",
        f"I will be your {keyword} expert",
        f"I will provide premium {keyword} services",
        f"I will craft stunning {keyword} solutions",
        f"I will optimize your {keyword} workflow",
        f"I will build {keyword} that converts",
    ]
    now = datetime.now(timezone.utc)
    for i in range(20):
        position = i + 1
        is_top = position <= 10
        # Sellers distribution — algorithm "hungry for new talent" if niche is underserved
        if total < 2000:
            level_weights = [0.30, 0.30, 0.20, 0.15, 0.05]
        elif total < 8000:
            level_weights = [0.15, 0.25, 0.30, 0.25, 0.05]
        else:
            level_weights = [0.08, 0.18, 0.30, 0.36, 0.08]
        level = rnd.choices(SELLER_LEVELS, weights=level_weights, k=1)[0]
        is_pro = level == "Fiverr Pro"

        # Orders in queue — higher demand niches show higher queues
        base_demand = max(1, 16 - (total // 800))
        queue = max(0, int(rnd.gauss(base_demand if is_top else base_demand * 0.4, 4)))

        # Price — Pros/Top Rated charge more
        if level in ("Top Rated", "Fiverr Pro"):
            price = rnd.choice([50, 75, 100, 150, 200, 250])
        elif level == "Level 2":
            price = rnd.choice([25, 35, 50, 75])
        elif level == "Level 1":
            price = rnd.choice([15, 20, 25, 35])
        else:
            price = rnd.choice([5, 10, 15, 20])

        # Last review — top sellers receive more recent reviews
        if is_top:
            hours_ago = rnd.randint(1, 72)
        else:
            hours_ago = rnd.randint(24, 480)
        last_review = (now - timedelta(hours=hours_ago)).isoformat()

        rating = round(rnd.uniform(4.6, 5.0) if is_top else rnd.uniform(3.8, 5.0), 1)
        reviews_count = rnd.randint(50, 5000) if is_top else rnd.randint(0, 400)

        gigs.append({
            "position": position,
            "title": rnd.choice(title_templates),
            "seller_level": level,
            "is_fiverr_pro": is_pro,
            "price_from": price,
            "orders_in_queue": queue,
            "rating": rating,
            "reviews_count": reviews_count,
            "last_review_at": last_review,
            "delivery_days": rnd.choice([1, 2, 3, 5, 7]),
        })

    # Gig tags — base + niche slants
    tag_pool = [
        keyword, f"custom {keyword}", f"professional {keyword}",
        f"{keyword} design", f"{keyword} expert", "fast delivery",
        "premium quality", "unlimited revisions", "24 hour delivery",
        "high converting", "minimalist", "modern style", "business",
        "startup", "small business", "ecommerce", "saas",
    ]
    tags = rnd.sample(tag_pool, k=min(10, len(tag_pool)))

    return {
        "data_source": "simulated_fallback",
        "total_services": total,
        "gigs": gigs,
        "tags": tags,
    }


# ---------- ANALYTICS ----------
def compute_opportunity(keyword: str, payload: dict) -> dict:
    """Compute Opportunity Score, Ratio, and breakdown."""
    gigs = payload.get("gigs", []) or []
    total = payload.get("total_services") or 0

    top10 = [g for g in gigs if g.get("position", 99) <= 10]
    bot10 = [g for g in gigs if g.get("position", 0) > 10]

    avg_queue_top = sum(g.get("orders_in_queue", 0) for g in top10) / max(1, len(top10))
    avg_queue_bot = sum(g.get("orders_in_queue", 0) for g in bot10) / max(1, len(bot10))
    avg_queue_all = sum(g.get("orders_in_queue", 0) for g in gigs) / max(1, len(gigs))

    # Review velocity — hours since most recent review across top 10
    now = datetime.now(timezone.utc)
    velocities = []
    for g in top10:
        try:
            dt = datetime.fromisoformat(g["last_review_at"])
            velocities.append((now - dt).total_seconds() / 3600.0)
        except Exception:
            pass
    review_velocity_hours = min(velocities) if velocities else 999.0

    # Price floor/ceiling
    new_seller_prices = [g["price_from"] for g in gigs if g.get("seller_level") in ("New Seller", "Level 1") and g.get("price_from")]
    top_prices = [g["price_from"] for g in gigs if g.get("seller_level") in ("Top Rated", "Fiverr Pro") and g.get("price_from")]
    price_floor = min(new_seller_prices) if new_seller_prices else (min((g["price_from"] for g in gigs if g.get("price_from")), default=0))
    price_ceiling = max(top_prices) if top_prices else (max((g["price_from"] for g in gigs if g.get("price_from")), default=0))

    # Saturation gap — % of New + Level 1 in top 10
    low_tier = [g for g in top10 if g.get("seller_level") in ("New Seller", "Level 1")]
    saturation_gap_pct = (len(low_tier) / max(1, len(top10))) * 100

    pro_count = sum(1 for g in gigs if g.get("is_fiverr_pro"))

    # ---- Opportunity Score (0-100) ----
    # Demand (40%): avg queue >5 AND velocity <48h
    queue_score = min(1.0, avg_queue_all / 12.0)  # 12+ avg saturates
    velocity_score = 1.0 if review_velocity_hours < 48 else max(0.0, 1.0 - (review_velocity_hours - 48) / 240.0)
    demand_score = (queue_score * 0.6 + velocity_score * 0.4)
    # Boost if both thresholds met
    if avg_queue_all > 5 and review_velocity_hours < 48:
        demand_score = max(demand_score, 0.85)

    # Competition (40%): <2000 = great
    if total <= 0:
        competition_score = 0.5
    elif total < 500:
        competition_score = 1.0
    elif total < 2000:
        competition_score = 1.0 - ((total - 500) / 1500.0) * 0.3  # 1.0 -> 0.7
    elif total < 8000:
        competition_score = 0.7 - ((total - 2000) / 6000.0) * 0.5  # 0.7 -> 0.2
    else:
        competition_score = max(0.05, 0.2 - ((total - 8000) / 50000.0))

    # Saturation Gap (20%): high % new/L1 = algorithm hungry
    saturation_score = min(1.0, saturation_gap_pct / 60.0)

    opportunity_score = round(
        demand_score * 40 + competition_score * 40 + saturation_score * 20, 1
    )

    # Competition-to-Order Ratio = avg_orders / (total / 100)
    if total > 0:
        ratio = round(avg_queue_all / (total / 100.0), 2)
    else:
        ratio = 0.0

    return {
        "opportunity_score": opportunity_score,
        "breakdown": {
            "demand": round(demand_score * 40, 1),
            "competition": round(competition_score * 40, 1),
            "saturation_gap": round(saturation_score * 20, 1),
        },
        "competition_to_order_ratio": ratio,
        "ratio_is_gold": ratio > 5,
        "metrics": {
            "total_services": total,
            "avg_orders_in_queue": round(avg_queue_all, 2),
            "avg_queue_top10": round(avg_queue_top, 2),
            "avg_queue_bottom10": round(avg_queue_bot, 2),
            "review_velocity_hours": round(review_velocity_hours, 1),
            "review_velocity_active": review_velocity_hours < 48,
            "price_floor": price_floor,
            "price_ceiling": price_ceiling,
            "saturation_gap_pct": round(saturation_gap_pct, 1),
            "fiverr_pro_count": pro_count,
            "pro_percentage": round((pro_count / max(1, len(gigs))) * 100, 1),
        },
    }


async def deep_scrape(keyword: str, try_live: bool = True) -> dict:
    """Main entry point. Try live, fall back to simulator."""
    payload = None
    if try_live:
        try:
            payload = await asyncio.wait_for(_live_scrape(keyword), timeout=45)
        except (asyncio.TimeoutError, Exception):
            payload = None

    if not payload or not payload.get("gigs"):
        # If live succeeded partial (only raw_gigs without queue), still fall back to simulator
        # so the analytics layer has the full schema. We label as simulated_fallback.
        payload = _simulate(keyword)

    analytics = compute_opportunity(keyword, payload)
    return {
        "keyword": keyword,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "data_source": payload["data_source"],
        "total_services": payload["total_services"],
        "gigs": payload.get("gigs", []),
        "tags": payload.get("tags", []),
        **analytics,
    }
