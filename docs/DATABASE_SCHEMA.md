# Database schema

SQLAlchemy models live in backend/app/db.py. PostgreSQL is the target. Alembic revision 005_research_boundaries creates new tables alongside the existing 001–004 tables. It does not rewrite legacy rows, drop uploads or move existing SQLite data. Import no real legacy snapshot until field mapping, authorization and reconciliation are reviewed.

| Records | Key and invariants |
|---|---|
| ai_users, ai_sessions, ai_invitations | Accounts, hashed expiring tokens and single-use imported-applicant activation. |
| ai_staff_requests, ai_staff_grants | One request or verified role grant per account. The grant retains scope, evidence reference, verifier and time. |
| ai_profiles, ai_documents, ai_evidence | Owner-bound profile, private file and excerpt-bearing claims. Applicant decisions and authorized review remain distinct. |
| ai_skills, ai_skill_versions, ai_occupations | Stable canonical concepts, source versions, aliases and optional merge target. Additional source snapshots are retained without replacing the active vocabulary silently. |
| ai_listings, ai_listing_versions | Unique original URL, current JSON record, append-only content versions and source approval attached to the reviewed version. |
| ai_policy_documents, ai_policy_provenance, ai_passages, ai_policies | Dated and versioned document metadata, hash of ingested canonical input, passage anchors and embeddings. Scope-approved retrieval and executable rule coverage are separate. |
| ai_rounds, ai_round_controls, ai_round_participation | Policy version, approved scope, explicit role IDs, opaque tie seed, frozen input and hash, individual participation grants. |
| ai_capacities, ai_seat_evidence, ai_choices | Current counts with versioned attestations and revocations. Choices are ordered lists for that round and applicant. |
| ai_drafts, ai_state | Solver results with independent checks and approval digest. The revision row serializes relevant mutations. |
| ai_cases, ai_activity, ai_audit_events | Scoped graph status, bounded tool activity and administrative audit actions. Payloads in the operational audit contain IDs and action codes only. |

The PostgreSQL connection owns vector schema and LangGraph checkpoint persistence. Back up before updating a live deployment. Fresh local SQLite mode creates the current schema without Alembic and requires a separate database path. The application's local fallback refuses the original legacy allocateai.db.
