# Revision 2 validation

Verified on 17 November 2026. Application runtime: Docker Compose, PostgreSQL 16 with pgvector, Python 3.12 API image, LangGraph with PostgresSaver, local CPU MiniLM, Next.js 16/TypeScript/Tailwind. Host-side unit checks use Python 3.14; browser checks use installed Microsoft Edge.

## Executed checks

- **27 backend engine/API/evidence/authorization tests passed**, using isolated test databases rather than application seed data. These include the supported-fact explanation safeguard.
- TypeScript checking and the Next.js production build pass. Docker builds and runs all three services locally.
- Three browser checks cover readiness/fixture labelling, Skills Explorer distinction/provenance/demand, policy citations/insufficiency and 390px mobile navigation. Screenshots are local test artifacts and contain no participant résumés.
- Real PostgreSQL restart/resume verification passes in a separate disposable verification database/container. See `checkpoint-verification.json`. The same evidence-review thread resumes after an API process restart, and the draft-review interrupt resumes after a second restart. Unverified allocation, unauthorized approval and publication before approval are blocked; publication is idempotent. Verification fixtures are deleted afterward and never enter the main application dataset.

## Actual public-policy retrieval evaluation

Source: dated seven-page PIB reference *Skilling India: Empowering the Workforce*, 11 October 2024. Ten passages, selected configuration document filter, 14 identical labelled questions across all methods: 12 answerable plus two no-answer cases. Labels use author-inspected source markers, not generated retrieval rankings. Full records: `retrieval-results.json` and `data/public/retrieval-labels.json`.

| Retrieval method | Mean Recall@5 on 12 answerable questions |
| --- | ---: |
| PostgreSQL keyword full-text search | 0.3333 |
| pgvector + real all-MiniLM-L6-v2 embeddings | 1.0000 |
| Reciprocal-rank hybrid fusion | 1.0000 |

Keyword retrieval uses the documented PostgreSQL web-search query semantics; it can require all non-stopword query terms, so paraphrases without matching words often retrieve nothing. Vector/hybrid ranking retrieves the labelled relevant passages in this small historical corpus. This does not establish general superiority, legal accuracy or production reliability.

Citation support is evaluated separately against supporting passage labels. Answers are conservative source quotes, not unrestricted generated policy conclusions. Both no-answer questions abstained in the recorded run. Some answerable questions also abstain because the conservative lexical support gate cannot establish enough coverage; perfect retrieval recall is **not** perfect answering. Check the final JSON for answer coverage and each citation/abstention outcome after any gate/corpus changes.

The final support-gated run answered **3/12 answerable questions with keyword retrieval and 6/12 with vector or hybrid retrieval**. All returned citations were in the author-labelled supporting passage sets; both no-answer cases abstained under all three methods. This measures labelled citation support and conservative coverage, not independent expert entailment or policy advice.

## Real source data used

- 112 ESCO skill concepts and 30 occupational concepts from a bounded official API sample, with source URIs and request-version metadata.
- 8,932 distinct O*NET 30.0 technology records from the official archive.
- 184 separately labelled project-curated technology names, initially pending review.
- Historical policy reference and author-labelled retrieval questions.

No real participant profiles, internship opportunities or employer-confirmed allocation capacities were supplied. The application shows zero/missing inputs for these records and provides import/upload controls. It does not fabricate them.

## Explicitly not run

- Live LLM extraction or live LLM tool-calling evaluation: no capable provider/model/API key supplied. Fixture behavior is not counted as live LLM evaluation.
- Skill precision/recall or qualification accuracy on real authorized résumé examples: no such examples supplied. The API supports de-identified labelled evaluation; unit examples establish implementation behavior only.
- Recommendation evaluation on real participant/listing pairs: those inputs were not supplied.
- Real-data allocation comparison or placements: no employer-confirmed capacity dataset and participating applicants supplied. CP-SAT/greedy and approval safeguards are verified with isolated tests, not presented as real placements.
- National-scale performance, causal fairness, real offer acceptance or external application submission.

## Important safeguards exercised

Capacity/one-placement constraints; ranked-only pairs; placement-count priority; preference tie-breaks; unverified qualification pause; explicit relocation restriction versus preference; unknown capacities; expired listings; infeasible group minimums; independent tamper checks; exact-draft approval; stale-input publication blocking; role/owner isolation (including indirect catalog/round reads); unsupported qualification rejection; distinction between rejected evidence and confirmed-not-held credentials; private derived-data deletion; authorized import and one-time account activation; conservative policy abstention; labelled fallback/no-live-model behavior.
