# API documentation

Use the generated OpenAPI at http://localhost:8800/docs. The API checks typed request bodies before applying state changes. Except for signup, login, health and the separately authorized MCP endpoint, use the bearer token returned by login.

| Workflow | Requests |
|---|---|
| Account and sessions | POST /api/auth/register with name, email and password. Applicant only. POST /api/auth/login. GET /api/auth/me. POST /api/auth/logout. |
| Staff access | POST /api/staff/request with scope and an evidence reference. GET /api/staff/status. Admin reviews GET /api/admin/staff/requests and grants or revokes using PUT or DELETE /api/admin/staff/{user_id}. |
| Applicant profile | GET or PUT /api/applicant/profile. POST /api/applicant/evidence for self-report. GET /api/applicant/recommendations. POST /api/applicant/matches/{listing_id}/explanation. |
| Resume | POST multipart /api/applicant/documents with file. POST /api/applicant/suggestions/{evidence_id} with action accept, edit or reject. DELETE /api/applicant/documents/{document_id}. DELETE /api/applicant/data removes derived participant data. |
| Skills and listings | GET /api/skills with q, GET /api/skills/{id}/versions, GET /api/listings. Staff can preview and commit JSON or preview CSV under /api/import/listings. Editors use PUT /api/listings/{id}. Admin approves with POST /api/admin/listings/{id}/approve, including expected_version and verification_reference. |
| Policy | Admin imports dated sources through POST /api/admin/policy-documents, creates an explicit rule configuration with POST /api/admin/policies, then approves it. POST /api/policy/search takes policy_id, question and mode. |
| Round scope and choices | POST /api/admin/rounds includes name, policy_id, scope and listing_ids. PUT /api/admin/rounds/{id}/participation gives an applicant ID an explicit grant. PUT /api/rounds/{id}/capacity accepts listing_id, seats and confirmation_reference. PUT /api/rounds/{id}/choices accepts explicitly ranked listing_ids. |
| Freeze and release | POST /api/admin/rounds/{id}/freeze and then /allocate. POST /api/admin/drafts/{id}/approve with approved:true and exact digest. Separate POST /api/admin/drafts/{id}/publish. GET /api/outcomes limits results to the current actor's scope. |
| MCP | POST /api/mcp/policy/search accepts the same retrieval query using a separate policy-only bearer token and allowlisted policy IDs. MCP transports this request via stdio. |
| Audit | GET /api/admin/audit returns recent action codes, timestamps and scoped record IDs. |

A missing or out-of-scope record can return 404. Insufficient authority returns 403. Stale versions, frozen edits and missing draft prerequisites return 409 where handled as a state conflict. Malformed requests and some invalid round input return 422. Policy abstention is a valid response with supported:false and no citations.

Applicant profiles accept `academic_branch` alongside the existing education, course and qualification fields. The applicant catalog and recommendations require a recent successful check of an original public application. Verified public records include `application_url`, `source_board_url` and `source_verified_at`. Recommendations return an empty array and the message `No currently verified matching internships found.` when the profile has no relevant verified openings. Applicant `GET /api/rounds` includes `choice_listings` for rounds in which the applicant has authorized participation.
