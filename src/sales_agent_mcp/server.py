"""
Entry point — run as MCP server via stdio.

Install:  pip install sales-agent-mcp
Run:      sales-agent-mcp
Config:
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
"""
import os

from edge_llm.core.mcp_server import BaseEdgeMCPServer
from edge_llm.core.memory.local import LocalMemoryStore
from edge_llm.core.memory.redis_store import RedisMemoryStore
from edge_llm.core.tenants.local import LocalTenantStore
from edge_llm.core.usage.local import LocalUsageTracker
from edge_llm.core.agent import EdgeAgent

from .agent import SalesAgent


class SalesMCPServer(BaseEdgeMCPServer):

    SERVER_NAME    = "sales-agent"
    SERVER_VERSION = "0.1.0"

    def create_memory(self):
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            return RedisMemoryStore(redis_url)
        return LocalMemoryStore(os.getenv("MEMORY_DIR", "data/memory"))

    def create_tenants(self):
        return LocalTenantStore(os.getenv("TENANTS_PATH", "data/tenants.json"))

    def create_tracker(self):
        return LocalUsageTracker(os.getenv("USAGE_DIR", "data/usage"))

    def create_agent(self) -> EdgeAgent:
        return SalesAgent(
            memory=self._memory,
            tenants=self._tenants,
            tracker=self._tracker,
            model=os.getenv("SALES_MODEL", "claude-opus-4-8"),
        )


def main():
    SalesMCPServer().run()


if __name__ == "__main__":
    main()
