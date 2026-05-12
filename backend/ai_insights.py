"""Gemini 3 Flash niche-arbitrage AI insights via emergentintegrations."""
import os
import json
import uuid
from emergentintegrations.llm.chat import LlmChat, UserMessage

EMERGENT_LLM_KEY = os.environ['EMERGENT_LLM_KEY']

SYSTEM = (
    "You are a Niche Arbitrage Specialist for the Fiverr marketplace. Your job is to "
    "analyze scraped Fiverr gig data and identify Market Gaps where demand outweighs "
    "seller supply by at least a 3:1 ratio. Be sharp, specific, and actionable. "
    "Never invent numbers; only reference data the user provides. Output STRICT JSON when asked."
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
        "sub-niches. Favor industry/vertical mashups (e.g., 'Minimalist Logo for Bio-Hacking Startups').\n\n"
        "Return STRICT JSON only, no markdown fences:\n"
        "{\"expansions\": [{\"keyword\": \"...\", \"rationale\": \"one sentence\", \"target_audience\": \"...\"}]}"
    )
    resp = await _chat().send_message(UserMessage(text=prompt))
    return _parse_json(resp, default={"expansions": []})


async def summarize_report(keyword: str, analytics: dict, gigs: list[dict]) -> dict:
    sample = [
        {
            "title": g.get("title", "")[:80],
            "level": g.get("seller_level"),
            "pro": g.get("is_fiverr_pro"),
            "price": g.get("price_from"),
            "queue": g.get("orders_in_queue"),
            "rating": g.get("rating"),
        }
        for g in gigs[:15]
    ]
    prompt = (
        f"Keyword: \"{keyword}\"\n"
        f"Analytics: {json.dumps(analytics)}\n"
        f"Top gigs sample: {json.dumps(sample)}\n\n"
        "Write a 3-bullet executive briefing for a freelancer evaluating this niche. "
        "Each bullet ≤ 28 words. First bullet = the headline opportunity or risk. "
        "Second = what data backs it up. Third = recommended action.\n\n"
        "Return STRICT JSON: {\"bullets\": [\"...\", \"...\", \"...\"], \"verdict\": \"GO|HOLD|AVOID\"}"
    )
    resp = await _chat().send_message(UserMessage(text=prompt))
    return _parse_json(resp, default={"bullets": [], "verdict": "HOLD"})


async def suggest_pivots(keyword: str, analytics: dict, tags: list[str]) -> dict:
    prompt = (
        f"Keyword: \"{keyword}\"\n"
        f"Total services: {analytics.get('metrics', {}).get('total_services')}\n"
        f"Avg orders in queue: {analytics.get('metrics', {}).get('avg_orders_in_queue')}\n"
        f"Competition-to-Order Ratio: {analytics.get('competition_to_order_ratio')}\n"
        f"Related tags: {tags}\n\n"
        "If this niche is saturated, suggest 5 'side-step' pivots that reuse the same skill "
        "but target a less competitive audience. Each pivot must explain WHY demand outpaces supply.\n\n"
        "Return STRICT JSON: {\"pivots\": [{\"pivot\": \"...\", \"why\": \"...\", \"estimated_demand_supply_ratio\": \"e.g. 4:1\"}]}"
    )
    resp = await _chat().send_message(UserMessage(text=prompt))
    return _parse_json(resp, default={"pivots": []})


def _parse_json(text: str, default: dict) -> dict:
    text = (text or "").strip()
    # Strip code fences
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(l for l in lines if not l.strip().startswith("```"))
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except Exception:
        return default
