# Research alignment

The uploaded IEEE paper describes an architecture and reports a controlled solver experiment. Code and test evidence are tracked separately.

| Paper section | Requirement | Implementation | Evidence and limit |
|---|---|---|---|
| I–III | Separate recommendations from allocation and preserve provenance | main.py, db.py, imports.py, services.py | Isolated imports, source approval, stale listing and scoped authorization checks. No live listings or capacity were invented. |
| III-C | Shared searchable catalog with distinct source identities | skills.py, imports.py, scripts/load_public_data.py | Traceable ESCO and O*NET imports exercised locally. Exact aliases remain separate from related skills. |
| IV | Account ownership, optional resume and bounded agents | main.py, documents.py, llm.py, agent.py, Next.js workspace | Session and resource denial, resume accept and delete, hosted opt-out and graph review tested in fixture mode. Live provider evaluation is pending. |
| V-A | Approved applicable rules and three outcomes | engine.py and services.py | FAIL, PASS and REVIEW and the hypothetical approved NOC case tested. Historical policy ingestion does not set eligibility. |
| V-B | Weighted skill coverage, fit and evidence coverage | engine.py and applicant recommendation route | Provided skill weights 2 for required and 1 for preferred. Fit weights 50/20/15/15 are design defaults. Missing values are omitted, and records below 50% coverage appear after sufficient-evidence results. No field calibration. |
| V-C | One version-scoped retrieval service and read-only MCP | retrieval.py, mcp_policy.py, API policy endpoints | No-key lexical path and official historical corpus verified. PostgreSQL vector and hybrid results must be measured separately. |
| VI | Authorized frozen allocation with two-stage objective | app/services.py, app/engine.py and round endpoints | Verified draft and digest-bound publication tested on isolated cases. Rank utility uses L=5 and original positions. Deterministic tie order uses a seed stored when the round is created and opaque IDs. |
| VII | Exhaustive paper experiment | scripts/reproduce_paper.py and docs/experiment | 512 oracle agreements and exact regression totals reproduced with OR-Tools 9.15.6755. |
| VIII–IX | Authorized field study, data protection and deployment evidence | Tests, reference benchmarks, privacy gates and docs | No real participant or organization round was run. Fairness, live model quality, operational scalability and production retention remain deployment work. |

Operational choices that are outside official policy include 30-day listing freshness, fit weights and the 50% evidence threshold. They are application settings for the academic prototype, not government criteria.
