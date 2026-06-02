SALES_TOOLS = [
    {
        "name": "analyze_lead",
        "description": "Analyze the lead's message and context to determine phase, sentiment, and objection type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message":      {"type": "string", "description": "The lead's latest message"},
                "current_stage":{"type": "string", "description": "Current pipeline stage"},
                "history_summary": {"type": "string", "description": "Brief summary of conversation so far"},
            },
            "required": ["message", "current_stage"],
        },
    },
    {
        "name": "get_reply_strategy",
        "description": "Get the recommended strategy and key point to use when crafting your reply for the current stage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "strategy": {
                    "type": "string",
                    "enum": ["build_rapport", "discover_pain", "build_value",
                             "handle_objection", "close", "nurture"],
                    "description": "Sales strategy to apply",
                },
                "key_point":    {"type": "string", "description": "Main point to convey"},
                "tone":         {"type": "string", "description": "Tone: warm | professional | urgent"},
            },
            "required": ["strategy", "key_point"],
        },
    },
    {
        "name": "update_crm",
        "description": "Update the lead's stage and notes in the CRM.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id":    {"type": "string"},
                "new_stage":  {"type": "string", "description": "New pipeline stage"},
                "notes":      {"type": "string", "description": "Internal notes to append"},
                "next_action":{"type": "string", "description": "Planned next action"},
            },
            "required": ["lead_id", "new_stage"],
        },
    },
    {
        "name": "schedule_followup",
        "description": "Schedule an automatic follow-up message for a silent lead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id":          {"type": "string"},
                "delay_hours":      {"type": "integer", "description": "Hours until follow-up (24/48/72)", "default": 48},
                "followup_context": {"type": "string", "description": "Context for the follow-up message"},
            },
            "required": ["lead_id"],
        },
    },
]
