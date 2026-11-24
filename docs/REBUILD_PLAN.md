# Controlled repair plan

Reuse the existing FastAPI / SQLAlchemy / Alembic backend, Next.js UI, public vocabulary assets and LangGraph. Repair the full application in place. The other backend directory and legacy SQLite file are outside the migration. Record behavior changes in implementation status.

The verified source baseline archive resides in the Codex workspace. To recover, review and selectively extract files by their repository-relative paths. No reset, production migration, data copy or volume deletion is part of the source repair. Existing PostgreSQL migrations remain intact. Test schema changes on isolated data before deployment. Do not migrate legacy SQLite data until a separately authorized mapping and reconciliation exist.

1. Confirm current behavior with isolated backend tests, frontend build and available local services.
2. Close role and source approval gaps, align deterministic matching and preserve the manual journey.
3. Add compatible migrations for genuine model changes. Wire versioned retrieval and applicant-controlled resume evidence.
4. Establish round scope, frozen input and digest binding. Align two-stage optimization and verify before release.
5. Reproduce the paper experiment outside the application database and run regression tests.
6. Record actual runtime, distinct from fixture, hosted model and field evaluation.
