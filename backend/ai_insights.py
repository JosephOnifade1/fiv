"""Gemini insights — Niche Arbitrage Specialist (Google Gemini + Emergent support)."""
import os
import json
import uuid
import asyncio
import re

SYSTEM = (
    "You are a Niche Arbitrage Specialist for the Fiverr marketplace in 2026. "
    "You reverse-engineer Fiverr's algorithm to find Market Gaps where demand outweighs "
    "supply by 3:1 or better. You understand the 2026 algorithm prioritizes Recent Order "
    "Velocity and Conversion Efficiency. You are aware of 2026 tech trends: Physical AI, "
    "Neuromorphic Computing, Agentic AI workflows, On-device LLMs, Synthetic Biology, "
    "Spatial Computing, Quantum-resilient cryptography, Carbon accounting, Bio-hacking, "
    "Vertical SaaS, GPT Actions, AI agents for SMBs. "
    "Be sharp, specific, actionable. Output STRICT JSON when asked."
)


async def run_chat_prompt(system_prompt: str, user_text: str) -> str:
    """Call Gemini using either direct google.generativeai or emergentintegrations."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY", "")

    # 1. Native Google Gemini SDK (google-generativeai)
    if api_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            for m_name in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-pro"]:
                try:
                    model = genai.GenerativeModel(
                        model_name=m_name,
                        system_instruction=system_prompt
                    )
                    res = await asyncio.to_thread(model.generate_content, user_text)
                    if res and res.text:
                        return res.text
                except Exception:
                    continue
        except Exception:
            pass

    # 2. EmergentIntegrations LlmChat fallback
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=api_key,
            session_id=f"fiverr-{uuid.uuid4()}",
            system_message=system_prompt,
        ).with_model("gemini", "gemini-3-flash-preview")
        return await asyncio.to_thread(lambda: asyncio.run(chat.send_message(UserMessage(text=user_text))))
    except Exception as e:
        raise RuntimeError(f"Gemini call failed. Ensure GEMINI_API_KEY is set: {e}") from e


async def run_chat(chat_obj_or_sys, text: str) -> str:
    """Compatibility layer with existing codebase."""
    if isinstance(chat_obj_or_sys, str):
        sys_p = chat_obj_or_sys
    else:
        sys_p = getattr(chat_obj_or_sys, "system_message", SYSTEM)
    return await run_chat_prompt(sys_p, text)


def _chat():
    class DummyChat:
        system_message = SYSTEM
    return DummyChat()


def _parse_json(text: str, default):
    if not text:
        return default
    text = text.strip()
    if "```json" in text:
        m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if m:
            text = m.group(1).strip()
    elif "```" in text:
        m = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if m:
            text = m.group(1).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
    return default




# ─────────────────────────────────────────────────────────────────────────────
# Deterministic (no-LLM) fallback implementations
# ─────────────────────────────────────────────────────────────────────────────

def _algo_expand_keywords(base_keyword: str, gig_titles: list) -> dict:
    """Return heuristic long-tail keyword expansions from the title pool."""
    words = set()
    for t in gig_titles[:30]:
        for w in t.lower().split():
            if len(w) > 3 and w not in base_keyword.lower().split():
                words.add(w)
    extra = list(words)[:6]
    suffixes = ["for small businesses", "for startups", "for ecommerce",
                "with fast delivery", "expert freelancer", "professional service",
                "for agencies", "affordable"]
    expansions = []
    for i, suf in enumerate(suffixes):
        kw = f"{base_keyword} {suf}"
        target = extra[i % len(extra)] if extra else base_keyword
        expansions.append({
            "keyword": kw,
            "rationale": f"Adds '{suf}' qualifier to reach a narrower buyer segment.",
            "target_audience": f"Buyers searching for {target}-related {base_keyword} services.",
        })
    return {"expansions": expansions[:8]}


def _algo_summarize_report(keyword: str, analytics: dict, gigs: list) -> dict:
    """Algorithmic niche summary from analytics metrics."""
    metrics = analytics.get("metrics") or {}
    median_price = metrics.get("median_price", 0)
    avg_rating = metrics.get("avg_rating", 0)
    total = metrics.get("total_gigs", len(gigs))
    velocity = analytics.get("velocity_score", 0)
    saturation = analytics.get("saturation_index", 0)
    pro_pct = metrics.get("pro_seller_pct", 0)

    if saturation and saturation < 30 and velocity and velocity > 60:
        verdict = "GO"
        reason = f"Low saturation ({saturation:.0f}) and high velocity ({velocity:.0f}) — good entry window."
    elif saturation and saturation > 70:
        verdict = "AVOID"
        reason = f"High saturation index ({saturation:.0f}) signals an overcrowded niche."
    else:
        verdict = "HOLD"
        reason = f"Moderate competition ({total} gigs). Entry is viable with strong differentiation."

    entry_price = max(5, round(median_price * 0.8)) if median_price else 25

    return {
        "verdict": verdict,
        "verdict_reason": reason,
        "opportunity_bullets": [
            f"Median price ${median_price:.0f} — room to compete on quality above avg rating {avg_rating:.1f}.",
            f"Pro sellers make up {pro_pct:.0f}% — lower entry bar for non-pro sellers.",
            f"Velocity score {velocity:.0f} — niche is {'active' if velocity > 50 else 'slow'} right now.",
        ],
        "risk_bullets": [
            f"{total} existing gigs — differentiation required.",
            f"Saturation index {saturation:.0f} — monitor for rapid crowding.",
        ],
        "recommended_entry_price": entry_price,
        "recommended_positioning": (
            "Niche specialist with fast delivery and unlimited revisions"
            if verdict == "GO" else "Generalist with competitive pricing"
        ),
        "_generated_by": "algorithmic_fallback",
    }


def _algo_suggest_pivots(keyword: str, analytics: dict, tags: list) -> dict:
    """Heuristic pivot suggestions based on tags and metrics."""
    metrics = analytics.get("metrics") or {}
    median_price = metrics.get("median_price", 25)
    pivots = []
    qualifiers = ["for SaaS companies", "for real estate agents", "for coaches",
                  "for non-profits", "for e-commerce brands"]
    for i, q in enumerate(qualifiers[:5]):
        tag_hint = tags[i] if i < len(tags) else keyword
        pivots.append({
            "angle": f"{keyword} {q}",
            "why_it_works": (
                f"Vertical specialisation signals expertise to '{q.replace('for ', '')}' buyers "
                f"who pay premium prices (above ${median_price:.0f} median)."
            ),
            "suggested_title": f"{keyword} specialist {q}, fast delivery, expert results",
        })
    return {"pivots": pivots}


def _algo_trend_verdict(keyword: str, analytics: dict) -> dict:
    """Simple heuristic trend verdict."""
    velocity = analytics.get("velocity_score", 0)
    saturation = analytics.get("saturation_index", 0)
    kw_lower = keyword.lower()

    trend_keywords = {
        "ai": ("Agentic AI & LLMs", "LONG_TERM_SURGE", 36),
        "llm": ("Large Language Models", "LONG_TERM_SURGE", 30),
        "automation": ("Workflow Automation", "LONG_TERM_SURGE", 24),
        "web3": ("Web3 / Blockchain", "NEUTRAL", 12),
        "nft": ("NFT Market", "FLASH_IN_PAN", 6),
        "crypto": ("Cryptocurrency", "NEUTRAL", 12),
        "video": ("Video Content Creation", "LONG_TERM_SURGE", 36),
        "logo": ("Brand Identity Design", "LONG_TERM_SURGE", 48),
        "seo": ("Search Engine Optimisation", "LONG_TERM_SURGE", 36),
    }
    for kw, (trend, verdict, horizon) in trend_keywords.items():
        if kw in kw_lower:
            return {
                "verdict": verdict,
                "matched_trend": trend,
                "horizon_months": horizon,
                "reasoning": (
                    f"'{keyword}' maps to '{trend}'. "
                    f"Velocity {velocity:.0f}, saturation {saturation:.0f}."
                ),
                "_generated_by": "algorithmic_fallback",
            }

    # Default
    if velocity and velocity > 70:
        return {"verdict": "LONG_TERM_SURGE", "matched_trend": "General Freelancing Demand",
                "horizon_months": 18,
                "reasoning": f"High velocity ({velocity:.0f}) with no specific hype cycle detected.",
                "_generated_by": "algorithmic_fallback"}
    return {"verdict": "NEUTRAL", "matched_trend": "General Freelancing",
            "horizon_months": 12,
            "reasoning": "Insufficient trend signal — stable but undifferentiated.",
            "_generated_by": "algorithmic_fallback"}


def _algo_proximity_map(keyword: str, autocomplete_suggestions: list, metrics: dict) -> dict:
    """Heuristic proximity map from autocomplete suggestions."""
    suggestions = autocomplete_suggestions or []
    sidesteps = []
    distances = ["NEAR", "NEAR", "MID", "MID", "FAR"]
    for i, sug in enumerate(suggestions[:5]):
        sidesteps.append({
            "term": sug,
            "distance": distances[i % len(distances)],
            "opportunity_hypothesis": (
                f"'{sug}' is a closely related search phrase — "
                "targeting it directly could capture buyers not finding the base keyword."
            ),
        })
    if not sidesteps:
        sidesteps = [
            {"term": f"{keyword} expert", "distance": "NEAR",
             "opportunity_hypothesis": "Adding 'expert' signals authority to higher-budget buyers."},
            {"term": f"professional {keyword}", "distance": "NEAR",
             "opportunity_hypothesis": "Buyers using 'professional' have higher intent and budgets."},
            {"term": f"{keyword} for beginners", "distance": "MID",
             "opportunity_hypothesis": "Underserved entry-level segment with lower competition."},
            {"term": f"custom {keyword}", "distance": "FAR",
             "opportunity_hypothesis": "Custom framing opens premium pricing headroom."},
        ]
    return {"sidesteps": sidesteps[:4]}

async def expand_keywords(base_keyword: str, gig_titles: list[str]) -> dict:
    titles_block = "\n".join(f"- {t}" for t in gig_titles[:50])
    prompt = (
        f"Base keyword: \"{base_keyword}\"\n\n"
        f"Top gig titles on first page:\n{titles_block}\n\n"
        "Generate 8 specific long-tail keyword variations that pivot into underserved "
        "sub-niches. Favor industry/vertical mashups with 2026 trends.\n\n"
        "STRICT JSON: {\"expansions\": [{\"keyword\": \"...\", \"rationale\": \"...\", \"target_audience\": \"...\"}]}"
    )
    try:
        result = _parse_json(await run_chat(SYSTEM, prompt), {})
        if result and result.get("expansions"):
            return result
    except Exception:
        pass
    return _algo_expand_keywords(base_keyword, gig_titles)


async def summarize_report(keyword: str, analytics: dict, gigs: list[dict]) -> dict:
    sample = [{
        "title": g.get("title", "")[:80], "level": g.get("seller_level"),
        "pro": g.get("is_fiverr_pro"), "price": g.get("price_from"),
        "queue": g.get("orders_in_queue"), "rating": g.get("rating"),
        "reviews": g.get("reviews_count"),
    } for g in gigs[:10]]
    prompt = (
        f"Keyword: \"{keyword}\"\n"
        f"Analytics summary:\n{json.dumps(analytics, indent=2)}\n\n"
        f"Sample of top gigs:\n{json.dumps(sample, indent=2)}\n\n"
        "Produce an executive summary for a seller evaluating this niche.\n"
        "STRICT JSON: {\n"
        "  \"verdict\": \"GO\" | \"HOLD\" | \"AVOID\",\n"
        "  \"verdict_reason\": \"...\",\n"
        "  \"opportunity_bullets\": [\"...\", \"...\", \"...\"],\n"
        "  \"risk_bullets\": [\"...\", \"...\"],\n"
        "  \"recommended_entry_price\": 0,\n"
        "  \"recommended_positioning\": \"...\"\n"
        "}"
    )
    try:
        result = _parse_json(await run_chat(SYSTEM, prompt), {})
        if result and result.get("verdict"):
            return result
    except Exception:
        pass
    return _algo_summarize_report(keyword, analytics, gigs)


async def suggest_pivots(keyword: str, analytics: dict, tags: list[str]) -> dict:
    prompt = (
        f"Keyword: \"{keyword}\"\n"
        f"Metrics: {json.dumps(analytics)}\n"
        f"Cross-reference tags from competitors: {json.dumps(tags[:25])}\n\n"
        "Suggest 5 creative pivot angles to enter this market with an unfair advantage.\n"
        "STRICT JSON: {\"pivots\": [{\"angle\": \"...\", \"why_it_works\": \"...\", \"suggested_title\": \"...\"}]}"
    )
    try:
        result = _parse_json(await run_chat(SYSTEM, prompt), {})
        if result and result.get("pivots"):
            return result
    except Exception:
        pass
    return _algo_suggest_pivots(keyword, analytics, tags)


async def trend_verdict_2026(keyword: str, analytics: dict) -> dict:
    prompt = (
        f"Keyword: \"{keyword}\"\n"
        f"Snapshot: {json.dumps(analytics.get('metrics', {}))}\n"
        f"Velocity Score: {analytics.get('velocity_score')}\n"
        f"Saturation Index: {analytics.get('saturation_index')}\n"
        f"Promoted CPA signal: {analytics.get('promoted_cpa_signal')}\n\n"
        "Determine if this niche is a flash-in-the-pan hype cycle or a multi-year secular surge in 2026.\n"
        "STRICT JSON: {\n"
        "  \"verdict\": \"FLASH_IN_PAN\" | \"LONG_TERM_SURGE\" | \"NEUTRAL\",\n"
        "  \"matched_trend\": \"...\",\n"
        "  \"horizon_months\": 0,\n"
        "  \"reasoning\": \"...\"\n"
        "}"
    )
    try:
        result = _parse_json(await run_chat(SYSTEM, prompt), {})
        if result and result.get("verdict"):
            return result
    except Exception:
        pass
    return _algo_trend_verdict(keyword, analytics)


async def proximity_map(keyword: str, autocomplete_suggestions: list[str], metrics: dict) -> dict:
    prompt = (
        f"Base keyword: \"{keyword}\"\n"
        f"Fiverr autocomplete pushes: {json.dumps(autocomplete_suggestions[:12])}\n"
        f"Niche metrics: {json.dumps(metrics)}\n\n"
        "Generate an algorithmic proximity map: 4 sidestep opportunities.\n"
        "STRICT JSON: {\"sidesteps\": [{\"term\": \"...\", \"distance\": \"NEAR\"|\"MID\"|\"FAR\", \"opportunity_hypothesis\": \"...\"}]}"
    )
    try:
        result = _parse_json(await run_chat(SYSTEM, prompt), {})
        if result and result.get("sidesteps"):
            return result
    except Exception:
        pass
    return _algo_proximity_map(keyword, autocomplete_suggestions, metrics)
