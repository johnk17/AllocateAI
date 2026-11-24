# API and import contracts

Interactive schemas: **http://localhost:8800/docs**. All application endpoints begin `/api`. Authentication is an expiring opaque bearer token from `POST /auth/login`, sent as `Authorization: Bearer TOKEN`. Server-side role checks protect private records, review, configuration, allocation and publication. Next.js proxies the same contracts from port 3000.

| Group | Routes and access |
| --- | --- |
| Identity | `POST /auth/register` (applicant/company only), `POST /auth/login`, `GET /auth/me`, `POST /auth/logout` |
| Readiness | `GET /health` public; `GET /dashboard` authenticated aggregate data readiness |
| Skills | `GET /skills?q=&category=`; `GET /skills/{id}/related` proposes unverified semantic neighbors |
| Catalog administration | `POST /admin/skills`, `PUT /admin/skills/{id}`, `POST /admin/skills/{source}/merge/{target}`, `POST /admin/skills/import`, `POST /admin/occupations/import` |
| Listings | `GET /listings?q=&location=&skill_id=&source=` (company sees own records), `PUT /listings/{id}` (owner/admin), `POST /listings/analyze` (owner/admin; suggestions start as mentioned) |
| Listing imports | `POST /import/listings/preview` (JSON array), `/csv-preview` (multipart `file`), `/commit` (validated JSON array); employer/admin |
| Applicant | `GET/PUT /applicant/profile`, `POST /applicant/evidence`, `POST /applicant/documents` (multipart PDF/DOCX), `GET /applicant/documents/{id}` (owner/admin), `DELETE /applicant/data`, `GET /applicant/recommendations` |
| Grounded explanation | `POST /applicant/matches/{listing_id}/explanation`; owner-only current-profile facts; live LLM selects supported fact IDs, fixture mode renders deterministically |
| Authorized profile import | `POST /admin/participants/import`; admin only, consent and authorization required |
| Policy documents | `GET/POST /admin/policy-documents`, `POST /admin/policy-documents/reindex`; admin only |
| Rule configurations | `GET /policies`; `POST /admin/policies`; `POST /admin/policies/{id}/approve`; admin creates/approves immutable versions |
| Retrieval | `POST /policy/search` with question, policy_id and keyword/vector/hybrid mode; authenticated |
| Evaluation | `POST /admin/evaluate/retrieval` with labelled questions; `POST /admin/evaluate/extraction` with authorized de-identified examples |
| Rounds | `GET /rounds`; `POST /admin/rounds`; `PUT /rounds/{id}/capacity` owner/admin; `PUT /rounds/{id}/choices` applicant |
| Agent | `POST /agent/cases`, `GET /agent/cases`, `GET /agent/cases/{id}`; owner/admin. `POST /admin/agent/cases/{id}/resume` requires authorized completed review |
| Evidence review | `GET /admin/evidence`; `POST /admin/evidence/{id}/review` |
| Allocation | `POST /admin/rounds/{id}/allocate`; `GET /admin/drafts`; admin only |
| Approval/publication | `POST /admin/drafts/{id}/approve`, `/publish`; `GET /admin/drafts/{id}/export`; admin only |
| Outcomes | `GET /outcomes`: only currently published outcomes visible to each authorized role |

## Real listing import

`data/templates/listings.csv` is a header-only template. CSV `requirements` and `mandatory_qualifications` columns contain JSON arrays. Missing optional values become null, not invented values. JSON listing fields are:

```text
title, organization, source_name, source_url,
location?, work_mode? (onsite/hybrid/remote), sector?,
description, requirements_text,
requirements [{skill_id, classification: required/preferred/mentioned, excerpt}],
mandatory_qualifications [], stipend?, deadline?, last_verified?,
status (unverified/open/expired)
```

Unknown capacities are not part of listing import. `PUT /rounds/{id}/capacity` requires a listing ID, supplied nonnegative seats and a confirmation reference. A company can confirm only its own listings; a placement admin can confirm an authorized record. Zero confirmed seats is distinct from unknown capacity. A missing capacity never produces an assignment.

Preview returns row-level errors, duplicate URLs and missing-field warnings. Commit revalidates the same records inside the database transaction. Required technology excerpts must be present in source text. Expired deadlines override an `open` label; an open listing with no verification date is treated as unverified.

## Authorized profile import and activation

```json
{
  "authorized": true,
  "profiles": [{
    "email": "PARTICIPANT_SUPPLIED_EMAIL",
    "name": "PARTICIPANT_SUPPLIED_NAME",
    "profile": {"consent": true},
    "evidence": []
  }]
}
```

Replace placeholders with records the placement cell is authorized to use. Imports never scrape profiles or silently replace existing accounts. Imported claims are `needs_review`. The admin receives one-time activation tokens, one per participant, valid for 48 hours. They are shown only in the private import result and are not sent by email automatically. The participant registers as Applicant with the same email and their token (`activation_token`) to set a password. Token reuse is rejected. Do not put activation tokens or raw profiles in benchmarks/screenshots/Git.

## Evidence and review

Manual evidence contains `kind`, `value`, optional canonical `skill_id`, exact supporting `excerpt` and context. Document extraction stores an excerpt only if it occurs on the stated page. Skills can be verified by deterministic support checks; qualifications require an authorized reviewer.

Review payloads:

```json
{"status":"verified"}
```

or `{"status":"rejected"}` for unsupported evidence. Rejecting evidence leaves a missing required qualification **unverified**. Only an explicit `{"status":"not_held","note":"AUTHORIZED_REVIEW_BASIS"}` establishes the distinct confirmed-not-held outcome; it is qualification-specific and requires a review note.

Deletion removes uploaded files, extracted evidence, profile, ranked choices, agent checkpoints/activity and affected derived drafts. The login account is retained. Private documents are accessible only to the owner or an authorized admin.

## Policy retrieval and labels

Import dated documents with title, scope, effective date, source URL, version and section text. Each versioned rule configuration explicitly links explanatory document IDs. Its `config` is immutable and not inferred from those documents. Approval is a separate admin action.

```json
{"question":"YOUR_POLICY_QUESTION","policy_id":1,"mode":"hybrid"}
```

Retrieval returns actual mode, availability, retrieved passage IDs, an extractive answer or insufficiency message, and document/section/version/date/URL citations. Citation support uses conservative lexical coverage and exact source quotation; it is not an independent legal interpretation or a general entailment guarantee.

Evaluation labels are an array:

```json
[{"id":"question-1","question":"YOUR_LABELLED_QUESTION","policy_id":1,"relevant_passage_ids":[1],"supporting_passage_ids":[1]}]
```

An empty relevant-ID set marks a no-answer question. Recall@5 is averaged only across answerable questions. Citation support is checked against labelled supporting IDs, and no-answer abstention is reported separately. All three retrieval methods use the same labels and version filter. If vector embeddings are unavailable, vector/hybrid aggregate evaluation is not claimed.

Extraction evaluation takes `{"authorized":true,"deidentified":true,"records":[{"text":"AUTHORIZED_DEIDENTIFIED_TEXT","gold_skill_ids":[],"gold_qualifications":[]}]}`. It returns aggregate keyword/alias/live-LLM precision, recall, qualification exact-set accuracy and detected unsupported claims. No raw text/identifiers are returned or persisted. Fixture mode marks live LLM evaluation not run.

## Approval contract

The admin inspects a draft, then sends `{"approved":true,"digest":"EXACT_64_CHARACTER_DRAFT_DIGEST"}` to `/approve`. The LangGraph draft-review interrupt resumes with this exact digest. `/publish` is a separate action requiring that stored approval. It recomputes deterministic checks and verifies current revision, policy approval and draft integrity. Capacity/profile/ranking/catalog/evidence/policy changes invalidate older approvals. Repeating publication does not create duplicate outcomes.

Common responses: 401 session missing/expired; 403 forbidden role; 404 inaccessible/missing record; 409 stale or unapproved state; 413 oversized file; 422 invalid input, unsupported evidence, or missing confirmed inputs. Infeasibility is recorded as a draft with solver status and conflicts; it is never silently relaxed.
