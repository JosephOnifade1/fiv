# Fiverr Niche Arbitrage Scout — PRD

## Original problem statement
Build a tool that scrapes deep into Fiverr to identify "Underserved High-Value Gigs".
- Total Service Count, Order Queue Depth (top10 / bottom10), Review Velocity, Price Floor/Ceiling
- Opportunity Score (0-100): Demand 40% + Competition 40% + Saturation Gap 20%
- Competition-to-Order Ratio = avg_orders_in_queue / (total_gigs / 100); gold when > 5
- Keyword expansion, cross-reference gig tags, week-over-week trends
- Distinguish Fiverr Pro vs standard sellers
- Playwright stealth scraping with anti-bot evasion
- AI niche-arbitrage specialist (Gemini 3 Flash)
- JWT auth, MongoDB persistence, CSV/JSON export

## Architecture
- Backend: FastAPI + Motor (async Mongo) + Playwright stealth + Emergent Gemini 3 Flash
- Frontend: React 19 + Tailwind + shadcn/ui + Phosphor icons + Recharts + Framer Motion
- Auth: bcrypt + JWT
- Storage: MongoDB collections — fs_users, fs_jobs, fs_watchlist, fs_trends

## Implemented (Feb 2026)
- JWT auth (register / login / me)
- Background scrape jobs; Playwright stealth attempt with deterministic seeded fallback (data_source labeled)
- Opportunity Score + Competition-to-Order Ratio (gold > 5) computation
- Top 10 / Bottom 10 gigs, gig tags, price floor/ceiling, review velocity, Fiverr Pro tracking
- Gemini 3 Flash AI: long-tail expansion, executive summary (verdict GO/HOLD/AVOID), pivot suggestions
- Watchlist with week-over-week % delta
- Trend snapshots + dashboard chart
- CSV + JSON export
- Swiss high-contrast dashboard, Cabinet Grotesk + IBM Plex Mono

## Testing (16/16 backend pass, 95% frontend pass — iteration_1.json)

## Gig Builder (Jun 2026) — iteration_5.json: 15/15 backend, frontend flows pass
- backend/gig_builder.py: POST /api/gigs/build (background, per-section progressive fill), GET /api/gigs, GET/PATCH/DELETE /api/gigs/{id}, POST /api/gigs/{id}/regenerate, GET /api/gigs/{id}/docx
- Sections: titles(3, ≤80 after "I will", coverage-ranked), category, tags(5×≤20), pricing (anchored to niche median/top decile, Fiverr-style rounding), description(≤1200, off-platform words stripped), FAQ 5-8, requirements 3-5, gallery 3 filenames; ranking checklist
- Free users: titles/tags/category only, other sections locked (402) + blurred upgrade UI; Pro/admin: everything incl. Word download; no scan credits used; stale (>7d) scan warning
- Collection: fs_gig_setups. Frontend: GigBuilder.jsx overlay, components/gig/*, GigSetupsDialog ("My Gigs"), Build Gig buttons on scan banner, AI panel, Live Niche Board rows
- Fixed: LLM calls blocked the event loop (all AI routes now run via ai_insights.run_chat in a thread)
- User decision: Claude integration CANCELLED — do not add or suggest it again

## Gig Audit (Jun 2026) — iteration_6.json: 9/9 backend, all frontend flows pass
- POST /api/gigs/audit {job_id (must be user's completed scan), original:{title, tags, description, packages, faq}} → saved as fs_gig_setups kind="audit" with original, before score (pasted sections only), AI issues list (5-8, severity + fix) and a full rewrite (same sections/access rules as Gig Builder)
- Frontend: GigAuditDialog (header "Gig Audit"), gig/AuditSummary (before→after on shared rules, title compare, issues); Audit badge in My Gigs
- Empty LLM sections retried once

## Open issue
- Dashboard scan calls both /api/scan and /api/scrape/search → each search may count as 2 scans of free quota (not yet fixed)

## Next Action Items / Backlog
- P0: Fix double quota count per dashboard scan
- P1: Gig Builder Phase 2 — side-by-side compare with top 3 gigs; inline editing with live checklist
- P2: Gig Builder Phase 3 — generated gallery images (Gig Audit DONE)
- P1: Captcha-solver integration so live scrape works without proxies
- P1: Scheduled re-scans for watchlist (cron) so week-over-week trends auto-populate
- P2: Multi-keyword batch scan with comparison view
- P2: Tag co-occurrence graph visualization
- P2: Migrate deprecated @app.on_event to lifespan context manager
- P3: Team workspaces / shared watchlists
