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
        raise RuntimeError(f"Gemini call failed. Ensure GEMINI_API_KEY is set: {e}")


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


async def expand_keywords(base_keyword: str, gig_titles: list[str]) -> dict:
    titles_block = "\n".join(f"- {t}" for t in gig_titles[:50])
    prompt = (
        f"Base keyword: \"{base_keyword}\"\n\n"
        f"Top gig titles on first page:\n{titles_block}\n\n"
        "Generate 8 specific long-tail keyword variations that pivot into underserved "
        "sub-niches. Favor industry/vertical mashups with 2026 trends.\n\n"
        "STRICT JSON: {\"expansions\": [{\"keyword\": \"...\", \"rationale\": \"...\", \"target_audience\": \"...\"}]}"
    )
    return _parse_json(await run_chat(SYSTEM, prompt), {"expansions": []})


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
    return _parse_json(await run_chat(SYSTEM, prompt), {
        "verdict": "HOLD", "verdict_reason": "Could not summarize report",
        "opportunity_bullets": [], "risk_bullets": [], "recommended_entry_price": 25,
        "recommended_positioning": "Generalist",
    })


async def suggest_pivots(keyword: str, analytics: dict, tags: list[str]) -> dict:
    prompt = (
        f"Keyword: \"{keyword}\"\n"
        f"Metrics: {json.dumps(analytics)}\n"
        f"Cross-reference tags from competitors: {json.dumps(tags[:25])}\n\n"
        "Suggest 5 creative pivot angles to enter this market with an unfair advantage.\n"
        "STRICT JSON: {\"pivots\": [{\"angle\": \"...\", \"why_it_works\": \"...\", \"suggested_title\": \"...\"}]}"
    )
    return _parse_json(await run_chat(SYSTEM, prompt), {"pivots": []})


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
    return _parse_json(await run_chat(SYSTEM, prompt), {
        "verdict": "NEUTRAL", "matched_trend": "General freelancing",
        "horizon_months": 12, "reasoning": "Insufficient trend signal.",
    })


async def proximity_map(keyword: str, autocomplete_suggestions: list[str], metrics: dict) -> dict:
    prompt = (
        f"Base keyword: \"{keyword}\"\n"
        f"Fiverr autocomplete pushes: {json.dumps(autocomplete_suggestions[:12])}\n"
        f"Niche metrics: {json.dumps(metrics)}\n\n"
        "Generate an algorithmic proximity map: 4 sidestep opportunities.\n"
        "STRICT JSON: {\"sidesteps\": [{\"term\": \"...\", \"distance\": \"NEAR\"|\"MID\"|\"FAR\", \"opportunity_hypothesis\": \"...\"}]}"
    )
    return _parse_json(await run_chat(SYSTEM, prompt), {"sidesteps": []})
