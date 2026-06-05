"""
Domain tool implementations for the SalesAgent internal loop.
These are called by EdgeAgent._execute_tools — they are NOT exposed via MCP.
"""
import json
from datetime import datetime, timedelta

_ANALYSIS_MODEL  = "claude-haiku-4-5-20251001"
_STRATEGY_MODEL  = "claude-haiku-4-5-20251001"


def analyze_lead(message: str, current_stage: str,
                 history_summary: str = "", client=None) -> dict:
    if client is None:
        return _analyze_lead_fallback(message, current_stage)

    prompt = f"""You are a sales analyst. Analyze the lead message below and return ONLY a JSON object with these keys:
- "sentiment": "positive" | "neutral" | "negative"
- "buying_signals": list of strings (signals detected, empty list if none)
- "objection_type": "price" | "timing" | "fit" | "trust" | "none"
- "recommended_action": short string describing what the sales agent should do next
- "hint": one actionable sentence for the agent

Current pipeline stage: {current_stage}
Conversation summary: {history_summary or "first interaction"}
Lead message: {message}

Return only valid JSON, no markdown, no explanation."""

    try:
        resp = client.messages.create(
            model=_ANALYSIS_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        result = json.loads(raw)
        result["current_stage"] = current_stage
        return result
    except Exception:
        return _analyze_lead_fallback(message, current_stage)


def _analyze_lead_fallback(message: str, current_stage: str) -> dict:
    has_signal = any(
        w in message.lower()
        for w in ["prezzo", "costo", "quando", "iniziare", "price", "cost", "start", "quanto"]
    )
    return {
        "current_stage":    current_stage,
        "message_preview":  message[:120],
        "sentiment":        "positive" if has_signal else "neutral",
        "buying_signals":   ["price inquiry"] if has_signal else [],
        "objection_type":   "none",
        "recommended_action": "advance stage" if has_signal else "continue building value",
        "hint": (
            "Lead shows buying signals — consider advancing stage."
            if has_signal
            else "Continue building value before proposing a step forward."
        ),
    }


def get_reply_strategy(strategy: str, key_point: str,
                       tone: str = "professional", client=None) -> dict:
    if client is None:
        return _strategy_fallback(strategy, key_point, tone)

    prompt = f"""You are a sales coach. Generate a reply strategy for a sales agent and return ONLY a JSON object with these keys:
- "strategy": the strategy name (use the one provided)
- "key_point": the core message to convey
- "tone": the tone to use
- "talking_points": list of 2-3 short bullet points to include in the reply
- "suggested_opening": one sentence to open the reply naturally
- "hint": one sentence of coaching advice

Strategy: {strategy}
Key point to convey: {key_point}
Tone: {tone}

Return only valid JSON, no markdown, no explanation."""

    try:
        resp = client.messages.create(
            model=_STRATEGY_MODEL,
            max_tokens=350,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        return json.loads(raw)
    except Exception:
        return _strategy_fallback(strategy, key_point, tone)


def _strategy_fallback(strategy: str, key_point: str, tone: str) -> dict:
    return {
        "strategy":          strategy,
        "key_point":         key_point,
        "tone":              tone,
        "talking_points":    [],
        "suggested_opening": "",
        "hint":              "Use this context to craft your reply. Keep it under 4 sentences.",
    }


def update_crm(lead_id: str, new_stage: str, notes: str = "",
               next_action: str = "", memory=None) -> dict:
    if memory:
        state = memory.get_entity_state(lead_id)
        existing_notes = state.get("notes", [])
        if not isinstance(existing_notes, list):
            existing_notes = []
        if notes:
            existing_notes.append(notes)
        memory.update_entity_state(lead_id, stage=new_stage,
                                   notes=existing_notes, next_action=next_action)
    return {"lead_id": lead_id, "stage": new_stage, "updated": True}


def search_product_catalog(query: str, catalog: str = "") -> dict:
    """
    Keyword search over the tenant's product catalog text.
    Splits by paragraphs/sections, scores by term overlap, returns top 3 chunks.
    Falls back gracefully when no catalog is configured.
    """
    if not catalog or not catalog.strip():
        return {
            "query":   query,
            "results": [],
            "note":    "No product catalog configured. Ask the tenant to upload one via PATCH /tenants/me/config.",
        }

    query_terms = set(query.lower().split())
    # Split on double newlines (paragraphs) or markdown headers
    import re
    chunks = [c.strip() for c in re.split(r"\n{2,}|(?=^#{1,3} )", catalog, flags=re.MULTILINE) if c.strip()]

    scored: list[tuple[int, str]] = []
    for chunk in chunks:
        chunk_words = set(chunk.lower().split())
        score = len(query_terms & chunk_words)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(reverse=True)
    top = [chunk for _, chunk in scored[:3]]

    return {
        "query":   query,
        "results": top if top else ["No specific information found for this query."],
    }


def schedule_followup(lead_id: str, delay_hours: int = 48,
                      followup_context: str = "", memory=None) -> dict:
    due_at = (datetime.now() + timedelta(hours=delay_hours)).isoformat()
    if memory:
        memory.update_entity_state(lead_id,
                                   pending_followup=True,
                                   followup_due=due_at,
                                   followup_context=followup_context)
    return {"lead_id": lead_id, "scheduled_at": due_at, "delay_hours": delay_hours}
