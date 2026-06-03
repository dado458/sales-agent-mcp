# sales-agent-mcp

![Tests](https://github.com/dado458/sales-agent-mcp/actions/workflows/test.yml/badge.svg)

> **⚠️ ALPHA SOFTWARE — FOR DEVELOPMENT USE ONLY — v0.1.0**
>
> This package is intended for **development, prototyping, and research purposes only**.
> It is not a finished commercial product and is not suitable for production use without significant additional hardening.
>
> - APIs may change without notice between minor versions in the 0.x series.
> - This package has not been audited for security. Do not use it to store or process real customer data,
>   leads, or any personal information without your own thorough security and compliance review.
> - All LLM calls consume Anthropic API credits. Costs are your responsibility — monitor usage actively.
> - LLM outputs are non-deterministic. The agent may produce incorrect, incomplete, or inappropriate responses.
>   Do not rely on agent output for consequential business decisions without human review.
> - There is no guarantee of uptime, correctness, or fitness for any particular purpose.
> - **The authors accept no responsibility for any costs, data loss, security breaches, compliance violations,
>   missed sales, or damages of any kind arising from the use or misuse of this software.**
> - Use entirely at your own risk.

**Autonomous sales agent MCP server — stateful, multi-tenant, built on [edge-llm-core](https://pypi.org/project/edge-llm-core/).**

`sales-agent-mcp` implements the *Edge LLM Pattern*: an MCP server that contains its own internal Claude loop, a sales state machine, persistent memory per lead, and multi-tenant configuration. Instead of being a stateless API wrapper, it is a domain-specialist agent that reasons autonomously.

## Install

```bash
pip install sales-agent-mcp
```

## Quick start

### 1. Add to Claude config

**macOS** — `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows** — `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "sales": {
      "command": "uvx",
      "args": ["sales-agent-mcp"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "SALES_TENANT_ID":   "my-company"
      }
    }
  }
}
```

### 2. Register a tenant

```python
from edge_llm.core.tenants.local import LocalTenantStore

store = LocalTenantStore("data/tenants.json")
api_key = store.register(
    "my-company",
    name="Acme SaaS",
    plan="pro",
    meta={
        "agent_name":          "Alex",
        "company":             "Acme Corp",
        "product_description": "Project management platform for remote teams",
        "pricing":             "$49/mo Starter, $149/mo Pro, $399/mo Enterprise",
        "language":            "en",
    },
)
print(api_key)  # sk-...
```

### 3. Use from Claude

```
Send this message to the sales agent for lead "lead-42":
"Hi, I'm interested in your product. How much does it cost?"
```

Claude calls `handle_message` → the agent analyzes the message, picks a strategy, and replies — fully autonomously.

## MCP tools exposed

| Tool | Description |
|---|---|
| `handle_message` | Send a message → runs full internal agent loop → returns reply |
| `get_entity_state` | Current pipeline stage + metadata for a lead |
| `get_conversation` | Message history (last N messages) |
| `set_entity_stage` | Manually advance or reset the pipeline stage |
| `add_note` | Attach internal CRM note without triggering the loop |
| `get_usage` | Monthly calls, tokens, cost for a tenant |
| `list_entities` | All active leads in memory |

## Sales pipeline

```
COLD ──→ INTERESTED ──→ OBJECTION ──→ CLOSING ──→ WON
  │           │               │           │
  └───────────┴───────────────┴───────────┴──→ LOST
```

Each stage has a defined objective and recommended tools:

| Stage | Objective |
|---|---|
| COLD | Understand pain. Do not sell yet. |
| INTERESTED | Build specific value, propose demo/trial. |
| OBJECTION | Resolve objection with empathy first. |
| CLOSING | Propose a concrete next step, create urgency. |
| WON | Confirm and hand off to onboarding. |
| LOST | Close gracefully, leave the door open. |

## Domain-specific tools (internal agent loop)

These tools are used internally by Claude inside the agent loop — they are not exposed as MCP tools to the host agent.

| Tool | Description |
|---|---|
| `analyze_lead` | Analyze message, detect sentiment, objection type, pipeline fit |
| `get_reply_strategy` | Return the recommended strategy and key point for Claude to use when writing its reply |
| `update_crm` | Update stage and notes for a lead |
| `schedule_followup` | Write a pending follow-up marker in memory (requires a `BaseWorker` implementation to actually send it — see [edge-llm-core docs](https://github.com/dado458/edge-llm-core)) |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required.** Anthropic API key |
| `SALES_MODEL` | `claude-opus-4-8` | Model for the internal agent loop |
| `REDIS_URL` | — | If set, uses Redis for memory (production) |
| `MEMORY_DIR` | `data/memory` | Local memory directory (dev) |
| `TENANTS_PATH` | `data/tenants.json` | Local tenant store path (dev) |
| `USAGE_DIR` | `data/usage` | Local usage tracking directory (dev) |

## Production deployment (Redis)

```bash
pip install "sales-agent-mcp[redis]"
export REDIS_URL=redis://localhost:6379
export ANTHROPIC_API_KEY=sk-ant-...
sales-agent-mcp
```

With Redis, all lead state and conversation history survives restarts and scales across multiple instances.

## Multi-tenant SaaS

Each tenant gets:
- Isolated lead state and conversation history
- Custom agent persona (`agent_name`, `company`, `language`)
- Custom product description and pricing in the system prompt
- Independent usage metering per plan (basic: 500 calls/mo, pro: 5 000, enterprise: unlimited)

## Known limitations

| Limitation | Detail |
|---|---|
| **No API retry** | If the Anthropic API returns an error mid-loop, the exception propagates uncaught and the agent returns an error to the host. Wrap `handle_message` calls with retry logic at the integration layer if needed. |
| **Reply length capped at 1 024 tokens** | Each internal LLM call has a fixed `max_tokens=1024`. Very long agent replies (e.g. detailed proposals) will be silently truncated. Set `SALES_MODEL` to a model with higher throughput or subclass `SalesAgent` to override. |
| **`schedule_followup` is a marker, not a trigger** | The tool writes `pending_followup: true` in memory. Nothing happens automatically — a separate `BaseWorker` process must scan memory and act on it. |
| **Local memory not thread-safe** | `LocalMemoryStore` (default) is not safe for concurrent requests. Use `REDIS_URL` for any production or multi-instance deployment. |

## Architecture

```
Claude (central agent)
    │  calls handle_message
    ▼
SalesMCPServer (MCP over stdio)
    └── SalesAgent                  ← internal Claude Opus loop
         ├── SalesPipeline          ← state machine COLD → WON/LOST
         ├── Memory (Local/Redis)   ← persistent per-lead state + conversation
         ├── TenantStore            ← per-tenant config and API keys
         └── UsageTracker           ← billing-ready usage metering
```

Built on [edge-llm-core](https://pypi.org/project/edge-llm-core/) — the open framework for the Edge LLM Pattern.

## License

Apache 2.0 — free for commercial use, attribution required.
