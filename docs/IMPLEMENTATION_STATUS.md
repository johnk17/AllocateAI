# Implementation status

- **Baseline and preservation:** read the IEEE paper and audited the existing full-stack project. Verified a recoverable source archive. Kept legacy SQLite data, existing migrations, public source assets and the Next.js interface.
- **Manual workflow:** applicant-only public registration, expiring server sessions, editable manual profile, accepted self-reported skills, versioned listing review, weighted fit, original links and evidence notes.
- **Scoped records:** staff requests and administrator grants, permission-scoped round setup, per-participant authorization, capacity evidence versions and revocation, frozen choices and evidence.
- **AI and policy:** private optional resume suggestions, consent before provider transfer, correction/rejection and per-file deletion. One LangGraph workflow with bounded preparation and policy evidence review. Scoped policy search, exact passages, abstention and read-only MCP.
- **Allocation:** certified cardinality and rank utility, repeatable tie resolution, independent checks and frozen hashes. Administrator approval and publication are separate. The 512-case solver experiment ran in isolation.
- **Integration verified:** migration on a disposable PostgreSQL database, keyword and hybrid retrieval over public references, and a LangGraph checkpoint resumed after an API restart. The existing data volume still needs its own authorized deployment and migration review.
- **Pending field validation:** hosted or local chat-model reliability requires an authorized compatible provider. Real recommendations and rounds need open sourced listings, approved applicable rules, consenting participants and verified capacities. Field relevance, outcomes and fairness were not measured.

See [test results](TEST_RESULTS.md) for the verified environments and [research alignment](RESEARCH_ALIGNMENT.md) for section-by-section scope.
