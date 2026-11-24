# AllocateAI

AllocateAI is an independent CSE473 project inspired by SIH25033. It helps applicants find sourced internships and supports an institution's internal allocation round when the institution supplies authorization, eligibility rules and role-level capacity.

- **Recommendation:** sign up, build a manual profile, add skills and browse verified open roles. See weighted skill coverage, fit, gaps, unknowns, eligibility notes and the original application link. Resume upload is optional.
- **Allocation:** grant scope to verified staff, approve applicable rule coverage, declare the round's roles and authorize participants. Staff attest capacity, applicants submit their own ranked choices, and an authorized actor freezes the snapshot. CP-SAT maximizes placements and then submitted rank utility. An administrator approves the exact verified draft and separately publishes it.

No applicant records, employers, listings or capacity are seeded. The application sends no external applications or offers. The bundled public material includes ESCO and O*NET reference records and a historical PIB policy document.

## Start the PostgreSQL application

Run from this folder with Docker Desktop started. Copy .env.example to .env and set your own admin password and local database password. Do not use the example credentials on an exposed installation.

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
```

Dashboard: http://localhost:3000. FastAPI docs: http://localhost:8800/docs. Health: http://localhost:8800/api/health. Compose applies Alembic migrations on API startup. PostgreSQL and uploads stay in Compose volumes. Back up an existing database before migration. Legacy allocateai.db is not used by this stack and remains untouched.

The default application can use no paid APIs. Set EMBEDDING_MODE=keyword and ALLOW_MODEL_DOWNLOAD=0 to skip model weights. LLM_MODE=fixture enables deterministic suggestions and explanations. The UI and result metadata label them. A hosted model requires explicit authorization before redacted resume text can be sent. See [AI workflow](docs/AI_WORKFLOW.md).

## Run locally without Docker on Windows

This uses a new SQLite file and in-memory workflow checkpoints. Use this path for the manual workflow and local troubleshooting. Use PostgreSQL for durable checkpoints and vector retrieval.

```powershell
# From the project root, first terminal. Install if the project venv is absent.
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
$env:ALLOCATEAI_LOCAL_SQLITE = '1'
$env:DATABASE_URL = 'sqlite:///' + (Join-Path (Get-Location) 'allocateai-local.db').Replace('\','/')
$env:UPLOAD_DIR = Join-Path (Get-Location) 'private\local-uploads'
$env:LLM_MODE = 'fixture'
$env:EMBEDDING_MODE = 'keyword'
$env:ADMIN_PASSWORD = '<your own local password>'
.\.venv\Scripts\python.exe -m uvicorn app.server:app --app-dir backend --host 127.0.0.1 --port 8800
```

```powershell
# Second terminal, from the project root.
npm.cmd --prefix frontend ci
$env:API_INTERNAL_URL = 'http://127.0.0.1:8800'
npm.cmd --prefix frontend run dev
```

## Use actual records

The PostgreSQL API refreshes employer postings from Lever and Greenhouse and authorized listings from SWAYAM Plus on startup and every four hours. A public opening needs an identifiable employer, an original posting, a working listing-specific application form or control, and a recent check. Closed, unreachable, or stale records are removed from the applicant catalog. Successful checks expire after eight hours. See [sources and the live verification run](docs/SOURCES.md).

Applicants enter their education, qualification, academic branch, skills and preferences in **Applicant Workspace**, then select **Find matching internships**. Each result links to the original application. Public sources need no API key. Set `PUBLIC_INTERNSHIP_SYNC_ENABLED=0` to disable automatic refresh. For a one-time refresh and source report, set `DATABASE_URL` to the existing PostgreSQL connection and run `.\.venv\Scripts\python.exe scripts\sync_public_internships.py`.

1. Import the public skills catalog and historical corpus with the bundled script. Set ADMIN_PASSWORD to the password you configured for this installation. The historical corpus is an explanatory reference and has no executable eligibility coverage.
2. Ask an administrator to verify staff scope against an authorized reference. Applicant signup can submit an access request, and only the administrator can grant an organization or placement role.
3. For an authorized allocation round, import placements from employer or placement-cell records. Set the source-backed deadline or confirm the source explicitly accepts rolling applications, then have an administrator verify the listing version.
4. To allocate, approve a current rule configuration and declare the in-scope verified roles. Authorize each participant, record capacity with evidence and wait for ranked choices. Freeze before solving. A scoped placement user can prepare and freeze a round. The administrator verifies, approves and publishes the draft.

```powershell
.\.venv\Scripts\python.exe scripts\load_public_data.py --catalog --base http://127.0.0.1:8800
```

Use [SOURCES](docs/SOURCES.md) for source attribution and [API documentation](docs/API_DOCUMENTATION.md) for the request contracts. Withdraw or correct data only through the affected record's authorized workflow.

## Verify the implementation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\reproduce_paper.py --output docs\experiment
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:e2e
```

Set DASHBOARD_URL and ADMIN_PASSWORD for the browser checks. Enable ALLOCATEAI_E2E_FIXTURES=1 only against a disposable local SQLite application. The end-to-end test checks for that mode before it creates isolated synthetic records. Never enable it against a participant workspace.

- [Project audit](docs/PROJECT_AUDIT.md) and [repair plan](docs/REBUILD_PLAN.md)
- [Architecture](docs/ARCHITECTURE.md), [schema](docs/DATABASE_SCHEMA.md), [matching](docs/MATCHING.md) and [AI workflow](docs/AI_WORKFLOW.md)
- [Research alignment](docs/RESEARCH_ALIGNMENT.md), [test results](docs/TEST_RESULTS.md) and [implementation status](docs/IMPLEMENTATION_STATUS.md)

The 512-case experiment verifies the paper's optimization comparison. Real recommendation, live model quality, participant outcomes and operational fairness require the separate study described in the paper. See the current test results for which runtime paths were exercised.
