"""
Domain tool implementations for the SalesAgent internal loop.
These are called by EdgeAgent._execute_tools — they are NOT exposed via MCP.
"""
from datetime import datetime, timedelta

# ── analyze_lead: deterministic lexicon-based analysis ──────────────────────
# Bilingual (IT/EN) keyword lexicons. No second LLM call: the agent's own
# turn already reasons over the message, this tool only needs to surface
# structured signals it might miss (objection type, explicit buying intent).

_BUYING_SIGNAL_WORDS = [
    "prezzo", "costo", "quando", "iniziare", "quanto", "provare", "demo", "trial",
    "price", "cost", "start", "when can we", "sign up", "subscribe",
]
_POSITIVE_WORDS = [
    "ottimo", "perfetto", "interessante", "mi piace", "sì",
    "great", "perfect", "interested", "love it", "sounds good", "yes",
]
_NEGATIVE_WORDS = [
    "non sono sicuro", "troppo caro", "non mi convince", "no grazie",
    "not sure", "too expensive", "not convinced", "no thanks", "not interested",
]
_OBJECTION_LEXICON = {
    # Note: bare "prezzo"/"price"/"costo"/"cost" are NOT objection markers on their
    # own — asking about price is a buying signal. Only clearly negative-leaning
    # price language counts as an objection.
    "price":  ["costoso", "costa troppo", "troppo caro", "fuori budget",
               "too expensive", "expensive", "too much", "cheaper", "over budget"],
    "timing": ["non ora", "più avanti", "trimestre prossimo", "non è il momento",
               "not now", "later", "next quarter", "bad timing", "too busy"],
    "fit":    ["non fa per noi", "non si adatta", "soluzione diversa",
               "doesn't fit", "not what we need", "different solution", "not a good fit"],
    "trust":  ["non vi conosco", "sicurezza", "affidabile", "garanzie",
               "never heard of you", "security", "data privacy", "is this legit", "trustworthy"],
}


def _match_any(text: str, words: list[str]) -> list[str]:
    return [w for w in words if w in text]


def analyze_lead(message: str, current_stage: str,
                 history_summary: str = "") -> dict:
    msg = message.lower()

    buying_signals = _match_any(msg, _BUYING_SIGNAL_WORDS)
    objection_type = "none"
    for kind, words in _OBJECTION_LEXICON.items():
        if _match_any(msg, words):
            objection_type = kind
            break

    if objection_type != "none":
        sentiment = "negative"
        recommended_action = "address objection"
        hint = f"Lead raised a {objection_type} objection — address it directly before re-pitching."
    elif buying_signals:
        sentiment = "positive"
        recommended_action = "advance stage"
        hint = "Lead shows buying signals — consider advancing stage."
    elif _match_any(msg, _NEGATIVE_WORDS):
        sentiment = "negative"
        recommended_action = "slow down, ask discovery questions"
        hint = "Lead seems hesitant — slow down and ask discovery questions before pushing forward."
    elif _match_any(msg, _POSITIVE_WORDS):
        sentiment = "positive"
        recommended_action = "continue building value"
        hint = "Lead is receptive — keep building value and look for an opening to advance."
    else:
        sentiment = "neutral"
        recommended_action = "continue building value"
        hint = "Continue building value before proposing a step forward."

    return {
        "current_stage":      current_stage,
        "message_preview":    message[:120],
        "sentiment":          sentiment,
        "buying_signals":     buying_signals,
        "objection_type":     objection_type,
        "recommended_action": recommended_action,
        "hint":               hint,
    }


# ── get_reply_strategy: deterministic playbook ──────────────────────────────

_STRATEGY_PLAYBOOK = {
    "build_rapport": {
        "talking_points": [
            "Acknowledge their specific context before pitching anything.",
            "Find common ground (industry, team size, shared pain point).",
        ],
        "openings": {
            "warm":         "Really glad to connect on this —",
            "professional": "Thanks for taking the time to chat —",
            "urgent":       "Quick one before we dive in —",
        },
    },
    "discover_pain": {
        "talking_points": [
            "Ask an open question about their current workflow/bottleneck.",
            "Avoid pitching features until the pain is explicit.",
        ],
        "openings": {
            "warm":         "I'd love to understand your situation better —",
            "professional": "To make sure I point you in the right direction —",
            "urgent":       "Let's get straight to it —",
        },
    },
    "build_value": {
        "talking_points": [
            "Lead with the outcome, not the feature list.",
            "Tie it back to the pain point they already mentioned.",
        ],
        "openings": {
            "warm":         "Here's something that might really help —",
            "professional": "Based on what you've shared, this is relevant —",
            "urgent":       "Here's the key point —",
        },
    },
    "handle_objection": {
        "talking_points": [
            "Validate the concern before countering it.",
            "Use a concrete proof point (case study, number, guarantee).",
        ],
        "openings": {
            "warm":         "That's a fair point, and I want to be upfront —",
            "professional": "I understand the concern — here's some context —",
            "urgent":       "Let me address that directly —",
        },
    },
    "close": {
        "talking_points": [
            "Propose a clear, low-friction next step (call, trial, contract).",
            "Create gentle urgency only if it's genuinely true.",
        ],
        "openings": {
            "warm":         "I think we're in a great spot to move forward —",
            "professional": "Here's a simple way to move ahead —",
            "urgent":       "Let's lock this in —",
        },
    },
    "nurture": {
        "talking_points": [
            "No hard pitch — share something genuinely useful.",
            "Leave the door open without pressuring for a reply.",
        ],
        "openings": {
            "warm":         "Just thought of you when I saw this —",
            "professional": "Wanted to share something relevant —",
            "urgent":       "Quick thought, no pressure —",
        },
    },
}


def get_reply_strategy(strategy: str, key_point: str,
                       tone: str = "professional") -> dict:
    playbook = _STRATEGY_PLAYBOOK.get(strategy, {
        "talking_points": ["Use this context to craft your reply."],
        "openings": {},
    })
    opening = playbook["openings"].get(tone, playbook["openings"].get("professional", ""))
    talking_points = [*playbook["talking_points"], key_point]

    return {
        "strategy":          strategy,
        "key_point":         key_point,
        "tone":              tone,
        "talking_points":    talking_points,
        "suggested_opening": opening,
        "hint":              "Keep it under 4 sentences and lead with the key point.",
    }


def update_crm(lead_id: str, new_stage: str, notes: str = "",
               next_action: str = "", memory=None, webhook=None) -> dict:
    if memory:
        state = memory.get_entity_state(lead_id) or {}
        existing_notes = state.get("notes", [])
        if not isinstance(existing_notes, list):
            existing_notes = []
        if notes:
            existing_notes.append(notes)
        memory.update_entity_state(lead_id, stage=new_stage,
                                   notes=existing_notes, next_action=next_action)

    if webhook:
        webhook.post({
            "event":       "crm_update",
            "lead_id":     lead_id,
            "stage":       new_stage,
            "notes":       notes,
            "next_action": next_action,
        })

    return {"lead_id": lead_id, "stage": new_stage, "updated": True}


def search_product_catalog(
    query: str,
    catalog: str = "",
    catalog_store=None,
    tenant_id: str = "",
) -> dict:
    """
    Search the product catalog for chunks relevant to the query.

    Priority:
    1. Vector search via ChromaCatalogStore (semantic, if configured and has data).
    2. Keyword search over catalog text in meta (fast fallback, no embeddings).
    3. Empty response with a setup hint.
    """
    # 1 — vector search
    if catalog_store is not None and tenant_id:
        try:
            if catalog_store.count(tenant_id) > 0:
                results = catalog_store.search(tenant_id, query, n_results=3)
                if results:
                    return {"query": query, "results": results, "source": "vector"}
        except Exception:
            pass  # fall through to keyword search

    # 2 — keyword search over meta catalog text
    if catalog and catalog.strip():
        import re
        query_terms = set(query.lower().split())
        chunks = [c.strip() for c in re.split(r"\n{2,}|(?=#{1,3} )", catalog, flags=re.MULTILINE) if c.strip()]
        scored = sorted(
            ((len(set(c.lower().split()) & query_terms), c) for c in chunks),
            reverse=True,
        )
        top = [c for _, c in scored[:3] if _ > 0]
        if top:
            return {"query": query, "results": top, "source": "keyword"}

    # 3 — nothing available
    return {
        "query":   query,
        "results": [],
        "note":    "No product catalog found. Upload one via POST /tenants/me/catalog.",
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
