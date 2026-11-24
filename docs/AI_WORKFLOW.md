# AI workflow

AllocateAI uses one configurable OpenAI-compatible transport with LangChain Core prompt templates and Pydantic contracts. LangGraph orchestrates case preparation and policy evidence review. The provider can select among four allowlisted tools. Arguments that try to change the case scope are rejected. Retrieved text and résumé text remain untrusted data. No agent tool can grant a role, modify a confirmed profile, approve policy, attest seats, solve an allocation or publish it.

Preparation uses counts and case state. Policy review receives only the public excerpts returned for the approved policy version. The server resolves IDs and exact citation spans and uses conservative extractive answers. Ambiguous or overlapping versions can trigger abstention. The model never supplies executable rules. Raw policy questions are passed through runtime context and do not enter graph checkpoints.

Resume transfer requires separate profile authorization. PDFs and DOCX documents are validated, extracted and stored privately. If live processing is absent, declined or fails, local catalog matching creates suggestions. The applicant may accept, edit or reject a suggestion. An edit beyond the citation becomes self-reported. An authorized reviewer confirms claims separately. Per-file deletion removes the file, excerpts and active linked claims. Production backups need a deployment retention policy.

## Modes

- LLM_MODE=fixture: deterministic path, including catalog extraction and fact templates. No live model use.
- LLM_MODE=live: configurable LLM_BASE_URL and LLM_MODEL, with an optional LLM_API_KEY. The adapter probes structured output and tool calling with public diagnostic input before it sends any authorized resume data. The current validation used no hosted or local live model.
- EMBEDDING_MODE=keyword: lexical queries only. PostgreSQL uses FTS. The SQLite local runtime uses an explicit lexical fallback.
- EMBEDDING_MODE=sentence_transformers: PostgreSQL retrieval can use stored normalized MiniLM vectors with cosine similarity. Hybrid search uses reciprocal rank fusion. Missing vectors produce a labeled downgrade.

## MCP

Set MCP_POLICY_TOKEN to a generated secret of at least 32 characters and MCP_POLICY_IDS to a comma-separated allowlist on the API server. Give the stdio process the same dedicated credential and set MCP_API_URL to the running backend. From backend, start the client-configured command ../.venv/Scripts/python.exe -m app.mcp_policy. One tool, search_policy, returns approved passages and citations. A normal applicant session token does not authorize this endpoint. The PostgreSQL endpoint executes its search in a read-only transaction. The protocol behavior follows the [MCP tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

Resume suggestion decision and publication gates remain server-enforced. Ragas and other course experiments are separate from these paths.
