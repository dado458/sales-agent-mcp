"""
Domain tool implementations for the SalesAgent internal loop.
These are called by EdgeAgent._execute_tools — they are NOT exposed via MCP.
"""
from datetime import datetime, timedelta


def analyze_lead(message: str, current_stage: str, history_summary: str = "") -> dict:
    return {
        "current_stage":   current_stage,
        "message_preview": message[:120],
        "hint": (
            "Lead shows buying signals — consider advancing stage."
            if any(w in message.lower() for w in ["prezzo", "costo", "quando", "iniziare", "price", "cost", "start"])
            else "Continue building value before proposing a step forward."
        ),
    }


def generate_reply(strategy: str, key_point: str, tone: str = "professional") -> dict:
    return {
        "strategy":   strategy,
        "key_point":  key_point,
        "tone":       tone,
        "hint": "Use this context to craft your reply. Keep it under 4 sentences.",
    }


def update_crm(lead_id: str, new_stage: str, notes: str = "", next_action: str = "",
               memory=None) -> dict:
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


def schedule_followup(lead_id: str, delay_hours: int = 48,
                      followup_context: str = "", memory=None) -> dict:
    due_at = (datetime.now() + timedelta(hours=delay_hours)).isoformat()
    if memory:
        memory.update_entity_state(lead_id,
                                   pending_followup=True,
                                   followup_due=due_at,
                                   followup_context=followup_context)
    return {"lead_id": lead_id, "scheduled_at": due_at, "delay_hours": delay_hours}
