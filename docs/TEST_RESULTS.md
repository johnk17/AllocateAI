# Test results

Verification date 22 November 2026.

| Verification | Evidence |
|---|---|
| Existing application baseline | 27 backend tests passed using isolated SQLite and fixture mode. Next.js typecheck and production build passed. Baseline PostgreSQL startup first timed out with Docker stopped. |
| Updated backend | 34 pytest tests passed with 13 upstream LangSmith deprecation warnings. The suite covers typed requests, ownership, grants, listing versions, evidence, frozen choices, solver constraints and publication. |
| Updated browser | 4 Playwright tests passed, including the manual applicant-to-recommendation journey and an isolated reviewed and published assignment. Runs use real Next.js and FastAPI processes against a separate SQLite file with official public reference assets. Initial runs exposed shared SQLite connection misuse and fragile selectors. |
| PostgreSQL schema | Alembic upgrade reached 005_research_boundaries (head) on a disposable pgvector PostgreSQL container. Existing project database volumes were not mounted. |
| PostgreSQL checkpoint restart | Prepared an evidence case that interrupted. Restarted the API process with the same database, verified its pending node and resumed the same thread to ready after an authorized evidence review. Deterministic fixture mode. |
| Public catalog | Imported 112 ESCO skills, 8,932 O*NET technology concepts and 30 occupational reference concepts using the existing attributed public assets. |
| Historical policy retrieval | Ten PIB passages and 14 labeled queries. On PostgreSQL, lexical Recall@5 was 0.3333, dense and hybrid were 1.0 over the 12 answerable entries. In the separate SQLite lexical implementation, Recall@5 was 1.0 on the same entries. The scoring methods differ. These results measure passage retrieval on a small author-labeled corpus, rather than current eligibility or answer quality. |
| MCP | Actual MCP stdio initialization, discovery of the single policy tool, a PostgreSQL hybrid citation and policy-scope denial. SQLite lexical tool use also passed. No chat model ran. |
| Paper experiment | OR-Tools 9.15.6755 on Python 3.14.5 agreed with independent enumeration on all 512 cases. Greedy lost one seat in 95 cases and rank utility at equal count in 14. Both objectives tied in 403. Totals were 1,236 and 1,141 placements across isolated cases. |
| Legacy data | allocateai.db SHA-256 60981891E2B14DADDEAF376A3BBF295EC2313FC715ED5E42AC9D006A5DCDFC72 before and after verification. No migration or write was applied to it. |

The benchmark files are in [experiment](experiment/). The checkpoint command now has prepare and check stages. Run it only against a disposable PostgreSQL application, with --isolated, --base and a --receipt path, then restart that test API between the two stages.

Tests labeled fixture use deterministic code or test-specific mocked failures. No live hosted or local chat-model evaluation ran. Field recommendation relevance, private participant data, officially confirmed seats, external submissions and real allocation outcomes were outside the verification dataset.
