"""
Tests for sales-agent-mcp.
Run: pytest tests/
"""
import pytest

from edge_llm.core.memory.local import LocalMemoryStore
from edge_llm.core.tenants.local import LocalTenantStore
from edge_llm.core.tenants.base import TenantConfig
from edge_llm.core.usage.local import LocalUsageTracker

from sales_agent_mcp.pipeline import SalesPipeline
from sales_agent_mcp.agent import SalesAgent
from sales_agent_mcp.tools.implementations import (
    analyze_lead, generate_reply, update_crm, schedule_followup,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def agent(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-fake")
    return SalesAgent(
        memory=LocalMemoryStore(tmp_path / "memory"),
        tenants=LocalTenantStore(tmp_path / "tenants.json"),
        tracker=LocalUsageTracker(tmp_path / "usage"),
    )


# ── SalesPipeline ─────────────────────────────────────────────────────────────

def test_pipeline_validate():
    SalesPipeline().validate()


def test_pipeline_stages():
    assert SalesPipeline().stages == ["COLD", "INTERESTED", "OBJECTION", "CLOSING", "WON", "LOST"]


def test_pipeline_terminal_stages():
    sm = SalesPipeline()
    assert sm.is_terminal("WON")
    assert sm.is_terminal("LOST")
    assert not sm.is_terminal("COLD")
    assert not sm.is_terminal("CLOSING")


def test_pipeline_transitions_valid():
    sm = SalesPipeline()
    assert sm.can_transition("COLD", "INTERESTED")
    assert sm.can_transition("COLD", "LOST")
    assert sm.can_transition("INTERESTED", "OBJECTION")
    assert sm.can_transition("INTERESTED", "CLOSING")
    assert sm.can_transition("CLOSING", "WON")
    assert sm.can_transition("CLOSING", "LOST")


def test_pipeline_transitions_invalid():
    sm = SalesPipeline()
    assert not sm.can_transition("COLD", "WON")
    assert not sm.can_transition("COLD", "CLOSING")
    assert not sm.can_transition("WON", "COLD")
    assert not sm.can_transition("LOST", "INTERESTED")


def test_pipeline_initial_stage():
    assert SalesPipeline().initial_stage() == "COLD"


def test_pipeline_all_stages_have_context():
    sm = SalesPipeline()
    for stage in sm.stages:
        ctx = sm.get_context(stage)
        assert ctx.stage == stage
        assert ctx.objective, f"Stage {stage} has no objective"


# ── Tool: analyze_lead ────────────────────────────────────────────────────────

def test_analyze_lead_no_signal():
    result = analyze_lead(message="Raccontami di più sul prodotto", current_stage="COLD")
    assert result["current_stage"] == "COLD"
    assert "Continue building" in result["hint"]


def test_analyze_lead_italian_buying_signal():
    result = analyze_lead(message="Qual è il prezzo del piano pro?", current_stage="INTERESTED")
    assert "buying signals" in result["hint"]


def test_analyze_lead_english_buying_signal():
    result = analyze_lead(message="What does it cost to start?", current_stage="COLD")
    assert "buying signals" in result["hint"]


def test_analyze_lead_truncates_preview():
    result = analyze_lead(message="x" * 200, current_stage="COLD")
    assert len(result["message_preview"]) == 120


def test_analyze_lead_with_history():
    result = analyze_lead(
        message="Interessante", current_stage="INTERESTED",
        history_summary="Lead asked about pricing in previous turn"
    )
    assert "current_stage" in result


# ── Tool: generate_reply ──────────────────────────────────────────────────────

def test_generate_reply_required_fields():
    result = generate_reply(strategy="build_value", key_point="reduces work by 60%")
    assert result["strategy"] == "build_value"
    assert result["key_point"] == "reduces work by 60%"
    assert result["tone"] == "professional"
    assert "hint" in result


def test_generate_reply_custom_tone():
    result = generate_reply(strategy="close", key_point="offer expires Friday", tone="urgent")
    assert result["tone"] == "urgent"


def test_generate_reply_all_strategies():
    for strategy in ["build_rapport", "discover_pain", "build_value",
                     "handle_objection", "close", "nurture"]:
        result = generate_reply(strategy=strategy, key_point="test")
        assert result["strategy"] == strategy


# ── Tool: update_crm ──────────────────────────────────────────────────────────

def test_update_crm_without_memory():
    result = update_crm(lead_id="lead-1", new_stage="INTERESTED")
    assert result["updated"] is True
    assert result["stage"] == "INTERESTED"
    assert result["lead_id"] == "lead-1"


def test_update_crm_appends_notes_not_overwrites(tmp_path):
    """Regression: update_crm was replacing notes list with a string."""
    mem = LocalMemoryStore(tmp_path)
    mem.save_entity_state("lead-1", {"stage": "COLD", "notes": ["first note"]})

    update_crm(lead_id="lead-1", new_stage="INTERESTED", notes="second note", memory=mem)

    state = mem.get_entity_state("lead-1")
    assert isinstance(state["notes"], list)
    assert "first note" in state["notes"]
    assert "second note" in state["notes"]


def test_update_crm_empty_note_not_appended(tmp_path):
    mem = LocalMemoryStore(tmp_path)
    mem.save_entity_state("lead-1", {"notes": ["only note"]})

    update_crm(lead_id="lead-1", new_stage="INTERESTED", notes="", memory=mem)

    assert mem.get_entity_state("lead-1")["notes"] == ["only note"]


def test_update_crm_recovers_corrupted_notes(tmp_path):
    """If notes was previously stored as a string, reset to list."""
    mem = LocalMemoryStore(tmp_path)
    mem.save_entity_state("lead-1", {"stage": "COLD", "notes": "corrupted string"})

    update_crm(lead_id="lead-1", new_stage="INTERESTED", notes="clean note", memory=mem)

    state = mem.get_entity_state("lead-1")
    assert isinstance(state["notes"], list)
    assert "clean note" in state["notes"]


def test_update_crm_sets_next_action(tmp_path):
    mem = LocalMemoryStore(tmp_path)
    mem.save_entity_state("lead-1", {"notes": []})

    update_crm(lead_id="lead-1", new_stage="CLOSING",
               notes="ready to close", next_action="send proposal", memory=mem)

    state = mem.get_entity_state("lead-1")
    assert state["next_action"] == "send proposal"
    assert state["stage"] == "CLOSING"


# ── Tool: schedule_followup ───────────────────────────────────────────────────

def test_schedule_followup_default_delay():
    result = schedule_followup(lead_id="lead-1")
    assert result["delay_hours"] == 48
    assert "T" in result["scheduled_at"]


def test_schedule_followup_custom_delay():
    result = schedule_followup(lead_id="lead-1", delay_hours=24)
    assert result["delay_hours"] == 24


def test_schedule_followup_persists_to_memory(tmp_path):
    mem = LocalMemoryStore(tmp_path)
    schedule_followup(lead_id="lead-1", delay_hours=72, followup_context="send demo link", memory=mem)

    state = mem.get_entity_state("lead-1")
    assert state["pending_followup"] is True
    assert state["followup_context"] == "send demo link"
    assert "followup_due" in state


def test_schedule_followup_without_memory():
    result = schedule_followup(lead_id="lead-1", delay_hours=48)
    assert result["lead_id"] == "lead-1"
    assert result["scheduled_at"]


# ── SalesAgent ────────────────────────────────────────────────────────────────

def test_agent_initial_state(agent):
    state = agent.initial_entity_state()
    assert state["stage"] == "COLD"
    assert state["interactions"] == 0
    assert state["notes"] == []
    assert state["pending_followup"] is False


def test_agent_system_prompt_defaults(agent):
    ctx = SalesPipeline().get_context("COLD")
    cfg = TenantConfig(tenant_id="test")
    prompt = agent.build_system_prompt(cfg, ctx)
    assert "Alex" in prompt
    assert "Acme Corp" in prompt
    assert "COLD" in prompt
    assert "Objective" in prompt


def test_agent_system_prompt_tenant_override(agent):
    ctx = SalesPipeline().get_context("INTERESTED")
    cfg = TenantConfig(
        tenant_id="t1",
        meta={
            "agent_name": "Giulia", "company": "Beta Corp",
            "product_description": "HR platform", "pricing": "€99/mo", "language": "en",
        },
    )
    prompt = agent.build_system_prompt(cfg, ctx)
    assert "Giulia" in prompt
    assert "Beta Corp" in prompt
    assert "Alex" not in prompt


def test_agent_system_prompt_contains_stage_context(agent):
    sm = SalesPipeline()
    for stage in ["COLD", "INTERESTED", "OBJECTION", "CLOSING"]:
        ctx = sm.get_context(stage)
        cfg = TenantConfig(tenant_id="test")
        prompt = agent.build_system_prompt(cfg, ctx)
        assert stage in prompt
        assert ctx.objective in prompt


def test_agent_tools_have_required_fields(agent):
    for tool in agent.get_tools():
        assert "name" in tool, f"Tool missing 'name': {tool}"
        assert "description" in tool, f"Tool missing 'description': {tool}"
        assert "input_schema" in tool, f"Tool missing 'input_schema': {tool}"


def test_agent_tool_map_complete(agent):
    expected = {"analyze_lead", "generate_reply", "update_crm", "schedule_followup"}
    assert set(agent.get_tool_map().keys()) == expected


def test_agent_tool_map_all_callable(agent):
    for name, fn in agent.get_tool_map().items():
        assert callable(fn), f"Tool '{name}' is not callable"
