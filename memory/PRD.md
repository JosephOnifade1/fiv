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

## Next Action Items / Backlog
- P1: Captcha-solver integration so live scrape works without proxies
- P1: Scheduled re-scans for watchlist (cron) so week-over-week trends auto-populate
- P2: Multi-keyword batch scan with comparison view
- P2: Tag co-occurrence graph visualization
- P2: Migrate deprecated @app.on_event to lifespan context manager
- P3: Team workspaces / shared watchlists
