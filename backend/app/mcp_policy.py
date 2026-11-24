"""Stdio MCP adapter for the same approved policy retrieval service as FastAPI."""

import os
from typing import Any, Literal

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import ValidationError

from .schemas import RetrievalQuestion

mcp = FastMCP("AllocateAI policy evidence")


@mcp.tool(
    structured_output=True,
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True
    )
)
def search_policy(
    policy_id: int,
    question: str,
    mode: Literal["keyword", "vector", "hybrid"] = "keyword",
) -> dict[str, Any]:
    """Find approved policy passages and cite their exact source anchors."""
    try:
        query = RetrievalQuestion(policy_id=policy_id, question=question, mode=mode)
    except ValidationError:
        raise ValueError("Invalid policy search request") from None
    allow = {
        int(i) for i in os.environ.get("MCP_POLICY_IDS", "").split(",") if i.strip()
    }
    if query.policy_id not in allow:
        raise ValueError("This policy version is outside the MCP scope")
    token = os.environ.get("MCP_POLICY_TOKEN")
    if not token:
        raise RuntimeError("Configure a policy-only MCP token in the environment")
    base = os.environ.get("MCP_API_URL", "http://127.0.0.1:8800").rstrip("/")
    try:
        result = httpx.post(
            f"{base}/api/mcp/policy/search",
            headers={"Authorization": f"Bearer {token}"},
            json=query.model_dump(),
            timeout=45,
        )
        result.raise_for_status()
    except httpx.HTTPError:
        raise RuntimeError("Scoped policy search is unavailable") from None
    return result.json()


if __name__ == "__main__":
    mcp.run(transport="stdio")
