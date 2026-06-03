from pathlib import Path

from edge_llm.core.agent import EdgeAgent
from edge_llm.core.state_machine import StateMachine, StageContext
from edge_llm.core.tenants.base import TenantConfig

from .pipeline import SalesPipeline
from .tools.definitions import SALES_TOOLS
from .tools.implementations import analyze_lead, get_reply_strategy, update_crm, schedule_followup

_PROMPT_TEMPLATE = (Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8")

_DEFAULT_META = {
    "agent_name":          "Alex",
    "company":             "Acme Corp",
    "product_description": "a SaaS platform that helps teams work more efficiently",
    "pricing":             "$49/month Starter, $149/month Pro, $399/month Enterprise. Free 14-day trial.",
    "language":            "en",
}


class SalesAgent(EdgeAgent):

    def get_state_machine(self) -> StateMachine:
        return SalesPipeline()

    def build_system_prompt(self, tenant_cfg: TenantConfig, stage_ctx: StageContext) -> str:
        m = {**_DEFAULT_META, **tenant_cfg.meta}
        base = _PROMPT_TEMPLATE.format(**m)
        return (
            f"{base}\n\n"
            f"# Current lead state\n"
            f"- Stage: {stage_ctx.stage}\n"
            f"- Objective now: {stage_ctx.objective}\n"
            f"- Recommended tools: {', '.join(stage_ctx.recommended_tools)}\n"
            f"- Possible next stages: {', '.join(stage_ctx.possible_next_stages)}\n"
        )

    def get_tools(self) -> list[dict]:
        return SALES_TOOLS

    def get_tool_map(self) -> dict[str, callable]:
        mem    = self._memory
        client = self._client
        return {
            "analyze_lead":       lambda **kw: analyze_lead(**kw, client=client),
            "get_reply_strategy": lambda **kw: get_reply_strategy(**kw, client=client),
            "update_crm":         lambda **kw: update_crm(**kw, memory=mem),
            "schedule_followup":  lambda **kw: schedule_followup(**kw, memory=mem),
        }

    def initial_entity_state(self) -> dict:
        return {"stage": "COLD", "interactions": 0, "notes": [], "pending_followup": False}
