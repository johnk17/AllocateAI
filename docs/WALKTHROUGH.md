# Five-minute demo

Use the running Compose app at http://localhost:3000. The last live run verified 54 public internships. The catalog refreshes automatically, so use the current dashboard and the dated [source report](SOURCES.md#live-public-internship-verification) when presenting counts.

## 0:00–0:45 — Match a student to a public vacancy

Sign in as an applicant. In **Applicant Workspace**, enter your education, qualification, academic branch, and preferences. Save a skill you hold and select **Find matching internships**. Expand a match to show the employer, location, requirements, and verification time. Open **Apply on original site** to show the employer or portal application page.

The live run used a mechanical engineering profile to match the Gantham Ventures role in Chennai. Profiles without a relevant verified opening show **No currently verified matching internships found.**

## 0:45–1:30 — Show real catalog provenance and import readiness

Open **Skills Explorer**. Search JavaScript, Postgres and k8s. Explain exact aliases and show that Java/JavaScript, C/C++ and React/React Native remain distinct. Show ESCO/O*NET provenance, versions and occupational concepts. **Demand in Imported Listings** counts only the actual workspace listings; occupational mappings are not proof of Indian employer demand. Semantic neighbors are labelled unverified proposals.

Open **Data Imports**. Show the real listing form, header-only CSV template, preview errors/warnings and duplicate detection. Explain unknown values and separate round-specific capacity confirmation. No public scheme announcement is turned into an individual internship.

## 1:30–2:30 — Retrieve policy evidence and show measured results

Open **Policy Evidence**, select the historical public-reference benchmark configuration, and ask **“What is the one-time grant for incidentals?”** Show the extractive quote and dated PIB document/section/URL citation. Then ask **“Which employer guarantees me a confirmed job offer tomorrow?”** and show insufficient evidence.

“This is a historical corpus, not current eligibility. These passages explain; only a separately approved configuration constrains the solver.” Show `docs/retrieval-results.json`: the same 14 labelled questions, 12 answerable plus two no-answer cases, ten passages, and Recall@5 for keyword/vector/hybrid. State that the corpus is small and author-labelled, and retrieval recall is not answer accuracy. Show citation support and abstention rather than claiming a perfect answering system.

## 2:30–3:30 — Demonstrate durable pause and restart

With authorized participant records, open **Agent Activity** on an applicant round case. Show tool names, outcomes and next actions. A mandatory qualification without adequate evidence pauses at `review`. A team mention is not a held qualification. Rejected evidence remains unverified unless a separate authorized not-held decision is recorded.

Restart the API with `docker compose restart api`, refresh the same case, verify/reject the evidence as admin and resume the same thread. No raw résumé or hidden reasoning appears in the timeline.

**If real participant data is absent:** run `.\.venv\Scripts\python.exe scripts\verify_restart.py` beforehand and show its recorded `docs/checkpoint-verification.json`. It actually uses PostgreSQL and restarts an API process twice, but its fixtures are in a separate temporary database and are not real applicant/placement results. The script removes its container/database afterward. Do not present its fixture as a participant supplied by an employer.

## 3:30–4:30 — Separate recommendations, allocation and approval

Show **Allocation Rounds**: approved policy version, specific employer-confirmed capacity reference, and top-five choices. If seat data is missing, explain recommendation mode and show that no seat is assigned.

With authorized confirmed data, run CP-SAT, inspect the exact draft, solver statuses and deterministic checks. “The first objective is number placed. Only a proven maximum unlocks quality and ranked-preference optimization. The agent does not invoke this solver or publish.” Show greedy comparison and disclose group-minimum differences.

Tick exact-draft review, approve, then separately publish. Explain that data/capacity/rule changes make the old approval stale and require rerunning. If no real round is available, show the implemented controls and the isolated verifier results; label real allocation evaluation **not run**.

## 4:30–5:00 — Close the authorized loop

With real published data, sign in as the affected applicant and show their own role, policy version, solver status, matched/missing skills and explanation. An employer sees only its own authorized listings/results. Without real inputs, show the empty published-outcome state and the exact missing data needed to complete this demonstration.

End with: “Our verified achievements are the Docker stack, local policy retrieval, deterministic workflow safeguards and durable restart/resume. We have not claimed a live LLM evaluation, real placements or improved offer acceptance without the necessary data.”
