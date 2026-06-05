from edge_llm.core.state_machine import StateMachine, StageContext


class SalesPipeline(StateMachine):
    stages          = ["COLD", "INTERESTED", "OBJECTION", "CLOSING", "WON", "LOST"]
    terminal_stages = ["WON", "LOST"]
    transitions = {
        "COLD":       ["INTERESTED", "LOST"],
        "INTERESTED": ["OBJECTION", "CLOSING", "LOST"],
        "OBJECTION":  ["INTERESTED", "CLOSING", "LOST"],
        "CLOSING":    ["WON", "LOST"],
        "WON":        [],
        "LOST":       [],
    }
    _context_map = {
        "COLD": StageContext(
            stage="COLD",
            objective="Understand the lead's pain point. Do not sell yet.",
            recommended_tools=["analyze_lead"],
            possible_next_stages=["INTERESTED", "LOST"],
        ),
        "INTERESTED": StageContext(
            stage="INTERESTED",
            objective="Build specific value tied to their problem. Propose demo or trial.",
            recommended_tools=["get_reply_strategy", "analyze_lead", "search_product_catalog"],
            possible_next_stages=["OBJECTION", "CLOSING", "LOST"],
        ),
        "OBJECTION": StageContext(
            stage="OBJECTION",
            objective="Resolve the objection without contradicting. Empathize first.",
            recommended_tools=["analyze_lead", "get_reply_strategy", "search_product_catalog"],
            possible_next_stages=["INTERESTED", "CLOSING", "LOST"],
        ),
        "CLOSING": StageContext(
            stage="CLOSING",
            objective="Propose a concrete next step. Create real urgency.",
            recommended_tools=["generate_reply"],
            possible_next_stages=["WON", "LOST"],
        ),
        "WON": StageContext(
            stage="WON",
            objective="Confirm and hand off to onboarding.",
            recommended_tools=["update_crm"],
            possible_next_stages=[],
        ),
        "LOST": StageContext(
            stage="LOST",
            objective="Close gracefully, leave the door open.",
            recommended_tools=["update_crm"],
            possible_next_stages=[],
        ),
    }
