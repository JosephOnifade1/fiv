# Self-Hosted Production-Grade Fiverr Market Scraper - Operations Guide

## Overview
This application features a self-hosted, independent Fiverr market data scraper.
It collects publicly accessible gig search data directly from public Fiverr pages via server-side HTTP requests, parsing Server-Side Rendered (SSR) structured data (`__NEXT_DATA__` JSON blobs) without relying on Apify or any commercial/third-party scraping-as-a-service providers.

---

## Architecture & Data Flow

1. **Client Request**:
   - User initiates a scan via `/api/scrape/search` or `/api/scan`.
   - Free users have a plan quota enforced (`FREE_SCAN_LIMIT=5/month`). Admins and Pro users bypass quotas.
   - Active scans for the same keyword and user are deduplicated to prevent redundant network traffic.

2. **Scraper Execution (`backend/scraper.py`)**:
   - HTTP GET requests to `https://www.fiverr.com/search/gigs?query={keyword}&page={n}`.
   - Headers: Realistic non-spoofed standard desktop browser headers (`User-Agent`, `Accept`, `Accept-Language`).
   - Rate Limits: Enforces inter-page pacing (`INTER_PAGE_DELAY = 2.0s`), maximum page limits (`MAX_PAGES = 3`), and gig count cap (`MAX_GIGS = 60`).
   - Transient Retry: Automatically retries on 5xx or network transport errors with exponential back-off up to 3 times. Respects `Retry-After` headers on HTTP 429 / 503.
   - Non-Bypass Security Policy: No proxy rotation, no CAPTCHA solving, no stealth spoofing, and no automated session forgery.

3. **Parsing & Validation**:
   - Locates `<script id="__NEXT_DATA__" type="application/json">` inside the returned HTML.
   - Extracts gig cards, starting prices, seller levels, ratings, review counts, delivery times, and canonical gig URLs.
   - Deduplicates entries across paginated batches.
   - Assigns sequential positions and checks data integrity.

4. **Honest Reporting & Error Handling**:
   - If Fiverr responds with HTTP 403, redirects to a CAPTCHA/checkpoint, or provides a block page, the scraper explicitly halts and reports `data_source: "blocked"`.
   - If the page structure changes or `__NEXT_DATA__` is missing, it reports `data_source: "parse_error"`.
   - If no gigs exist for the term, it reports `data_source: "no_results"`.
   - **Zero Fake Data Guarantee**: Under no circumstance does the production scraper silently substitute simulated, synthetic, or cached stale data.

---

## Data Collection & Provenance

### Collected Live Fields:
- `title`: Extracted gig title
- `price_from`: Starting package / base price
- `seller_level`: Normalized level (`New Seller`, `Level 1`, `Level 2`, `Top Rated`, `Fiverr Pro`)
- `is_fiverr_pro`: Pro badge status
- `rating`: Overall gig rating score
- `reviews_count`: Total public review count
- `delivery_days`: Starting tier turnaround time in days
- `gig_url`: Canonical Fiverr gig link
- `total_services`: Total search results count reported by Fiverr
- `_source_url`: Full request URL fetched
- `_source_page`: Pagination index (1 to 3)
- `_fetched_at`: UTC ISO timestamp of retrieval

### Public Gaps (Explicitly `null` with Provenance Tagging):
- `orders_in_queue`: Only shown on individual gig pages. Setting this to `null` prevents performing 60+ individual gig page queries per scan.
- `reviews_last_7d`: Not published in public search card data.
- `favourites`: Not exposed on the public search results page.
- `is_promoted`: Captured only when an ad indicator flag is present in the page payload; otherwise `null`.

---

## Configuration Variables (`.env`)

| Variable | Description | Default / Example |
|---|---|---|
| `MONGO_URL` | MongoDB connection URI | `mongodb://localhost:27017` |
| `DB_NAME` | Database name | `fiverr_scout` |
| `JWT_SECRET` | Secret key for JWT generation | (Required secret string) |
| `ADMIN_EMAIL` | Admin account email with unlimited scans | `admin@example.com` |
| `FREE_SCAN_LIMIT` | Monthly scan allowance for free tier | `5` |
| `PRO_PRICE_USD` | Monthly subscription price | `29.00` |

---

## Worker Startup & Job Persistence

- Scrape jobs run as FastAPI asynchronous `BackgroundTasks`.
- Job records are maintained in MongoDB collections:
  - `fs_jobs`: User jobs, status (`running`, `complete`, `failed`), exportable payloads.
  - `fs_scan_tasks`: Pipeline tasks with live `progress` (`phase`, `pages_fetched`, `gigs_found`).
  - `market_insights`: Upserted niche overviews with opportunity scores, gold markers, and last data sources.
- Survives process restarts: Queries against `/api/scrape/jobs/{id}` and `/api/scan/{task_id}` read persisted database state.

---

## Testing & Quality Assurance

Comprehensive offline tests with zero external dependencies are located in `backend/tests/test_scraper_offline.py`.
Run tests via:
```bash
pytest backend/tests/test_scraper_offline.py -v
```

Features tested:
1. HTML fixture extraction and `__NEXT_DATA__` JSON parsing.
2. HTTP 403, CAPTCHA, and checkpoint block detection.
3. Pagination aggregation and item deduplication.
4. Transient failure retries and `Retry-After` adherence.
5. Absolute prevention of synthetic fallback data on failures.
6. Field provenance validation and NaN numeric guards.

