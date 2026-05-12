"""Gemini 3 Flash insights — Niche Arbitrage Specialist (2026 edition)."""
import os
import json
import uuid
from emergentintegrations.llm.chat import LlmChat, UserMessage

EMERGENT_LLM_KEY = os.environ['EMERGENT_LLM_KEY']

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


def _chat() -> LlmChat:
    return LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"fiverr-{uuid.uuid4()}",
        system_message=SYSTEM,
    ).with_model("gemini", "gemini-3-flash-preview")


async def expand_keywords(base_keyword: str, gig_titles: list[str]) -> dict:
    titles_block = "\n".join(f"- {t}" for t in gig_titles[:50])
    prompt = (
        f"Base keyword: \"{base_keyword}\"\n\n"
        f"Top gig titles on first page:\n{titles_block}\n\n"
        "Generate 8 specific long-tail keyword variations that pivot into underserved "
        "sub-niches. Favor industry/vertical mashups with 2026 trends.\n\n"
        "STRICT JSON: {\"expansions\": [{\"keyword\": \"...\", \"rationale\": \"...\", \"target_audience\": \"...\"}]}"
    )
    return _parse_json(await _chat().send_message(UserMessage(text=prompt)), {"expansions": []})


async def summarize_report(keyword: str, analytics: dict, gigs: list[dict]) -> dict:
    sample = [{
        "title": g.get("title", "")[:80], "level": g.get("seller_level"),
        "pro": g.get("is_fiverr_pro"), "price": g.get("price_from"),
        "queue": g.get("orders_in_queue"), "rating": g.get("rating"),
        "promoted": g.get("is_promoted"),
    } for g in gigs[:15]]
    prompt = (
        f"Keyword: \"{keyword}\"\nAnalytics: {json.dumps(analytics)}\n"
        f"Sample gigs: {json.dumps(sample)}\n\n"
        "Write a 3-bullet executive briefing. ≤28 words each. "
        "First = headline opportunity/risk. Second = data backing. Third = action.\n\n"
        "STRICT JSON: {\"bullets\": [\"...\", \"...\", \"...\"], \"verdict\": \"GO|HOLD|AVOID\"}"
    )
    return _parse_json(await _chat().send_message(UserMessage(text=prompt)), {"bullets": [], "verdict": "HOLD"})


async def suggest_pivots(keyword: str, analytics: dict, tags: list[str]) -> dict:
    prompt = (
        f"Keyword: \"{keyword}\"\n"
        f"Total: {analytics.get('metrics', {}).get('total_services')}, "
        f"AvgQueue: {analytics.get('metrics', {}).get('avg_orders_in_queue')}, "
        f"Ratio: {analytics.get('competition_to_order_ratio')}\n"
        f"Tags: {tags}\n\n"
        "Suggest 5 side-step pivots reusing the same skill but targeting less competitive audiences. "
        "Each must explain WHY demand outpaces supply.\n\n"
        "STRICT JSON: {\"pivots\": [{\"pivot\": \"...\", \"why\": \"...\", \"estimated_demand_supply_ratio\": \"e.g. 4:1\"}]}"
    )
    return _parse_json(await _chat().send_message(UserMessage(text=prompt)), {"pivots": []})


async def trend_verdict_2026(keyword: str, analytics: dict) -> dict:
    """Cross-reference with 2026 tech trends to label flash-in-pan vs long-term surge."""
    metrics = analytics.get("metrics", {})
    prompt = (
        f"Keyword: \"{keyword}\"\n"
        f"Velocity Score: {analytics.get('velocity_score')}\n"
        f"Saturation Index: {analytics.get('saturation_index')}\n"
        f"Promoted CPA %: {metrics.get('promoted_pct')}\n"
        f"Avg queue: {metrics.get('avg_orders_in_queue')}\n"
        f"Reviews last 7d / total: {metrics.get('reviews_last_7d')} / {metrics.get('total_reviews')}\n"
        f"High-Ticket Vacuum: {analytics.get('high_ticket_vacuum')}\n\n"
        "Cross-reference with 2026 macro tech trends (Physical AI, Neuromorphic, Agentic AI, "
        "Spatial Computing, Synthetic Biology, Bio-hacking, Vertical SaaS, On-device LLMs, etc). "
        "Decide if this niche is a FLASH_IN_PAN (≤3 month half-life) or LONG_TERM_SURGE (>12 months).\n\n"
        "STRICT JSON: {\"verdict\": \"FLASH_IN_PAN|LONG_TERM_SURGE|NEUTRAL\", "
        "\"matched_trend\": \"the closest 2026 trend or null\", "
        "\"horizon_months\": 0-24, \"reasoning\": \"≤40 words\"}"
    )
    return _parse_json(await _chat().send_message(UserMessage(text=prompt)),
                       {"verdict": "NEUTRAL", "matched_trend": None, "horizon_months": 0, "reasoning": ""})


async def proximity_map(base_keyword: str, suggestions: list[str], known_metrics: dict) -> dict:
    """Map which low-comp keywords sit next to high-demand ones in the autocomplete tree."""
    prompt = (
        f"Base: \"{base_keyword}\"\n"
        f"Live autocomplete neighbors (high-demand signals from Fiverr engine):\n"
        f"{json.dumps(suggestions)}\n\n"
        f"Base niche metrics: {json.dumps(known_metrics)}\n\n"
        "For each neighbor, estimate whether it is LOW_COMPETITION sitting adjacent to "
        "HIGH_DEMAND (a true side-step). Pick the 5 strongest side-steps. "
        "Explain audience overlap with the base keyword.\n\n"
        "STRICT JSON: {\"sidesteps\": [{\"keyword\": \"...\", "
        "\"competition_estimate\": \"LOW|MID|HIGH\", "
        "\"demand_estimate\": \"LOW|MID|HIGH\", "
        "\"audience_overlap_pct\": 0-100, "
        "\"rationale\": \"≤30 words\"}]}"
    )
    return _parse_json(await _chat().send_message(UserMessage(text=prompt)), {"sidesteps": []})


def _parse_json(text: str, default: dict) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = "\n".join(l for l in text.splitlines() if not l.strip().startswith("```"))
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1:
        text = text[s:e + 1]
    try:
        return json.loads(text)
    except Exception:
        return default
