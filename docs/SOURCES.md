# Real data, provenance and attribution

The application does not seed fictional applicants, companies, internships or capacities. Unit/integration fixtures are separate from application data and explicitly labelled.

## Skills and occupational references

- **ESCO:** [official download portal](https://esco.ec.europa.eu/en/use-esco/download) and [official web-service API](https://esco.ec.europa.eu/en/use-esco/use-esco-services-api/esco-web-service-api). The included API sample requests `v1.2.0`, retains canonical concept URIs, English labels, original source payloads for occupations, request-version and retrieval-date metadata. It contains 112 skill concepts and 30 occupational concepts, not the complete ESCO dataset. ESCO version selection is retained as requested API metadata rather than asserted as a verified complete release snapshot. Follow the original source's reuse and attribution terms for any redistribution.
- **O*NET:** [official database portal](https://www.onetcenter.org/database.html), [30.0 original TSV archive](https://www.onetcenter.org/dl_files/database/db_30_0_text.zip), [license and attribution](https://www.onetcenter.org/license_db.html). The converter reads `Technology Skills.txt` and deduplicates commodity-code + example combinations, yielding 8,932 technology records in this download. This project contains information from O*NET Database 30.0 by the U.S. Department of Labor, Employment and Training Administration, used under the O*NET database's CC BY 4.0 terms. AllocateAI transforms/selects records; this is not an endorsement by USDOL/ETA. Technology occupation associations are source references, not measured Indian employer demand.
- **Curated supplement:** 184 real technology/skill names across the requested domains. Source is explicitly `AllocateAI project-curated…`, version 2026-11-17, initially pending administrator review. These are not misattributed to ESCO/O*NET. Admin corrections and explicit merges are supported. Related concepts are never silently equated to exact aliases.

`data/public/` contains original downloads, converted source payloads and the historical policy labels. No participant résumé is placed there. The main application may import these public records through authenticated admin paths; the repository's source files do not contain participant records.

## Policy retrieval corpus

[Skilling India: Empowering the Workforce — PIB, 11 October 2024](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2024/oct/doc20241011415001.pdf) is a dated, public, seven-page reference. It discusses several skilling initiatives and the 2024-25 PMIS pilot launched on 3 October 2024. The imported metadata records that pilot date and separately labels the reference publication/version as 11 October 2024. It is explicitly historical, not a claim of current eligibility. Page labels remain in passage sections. Chunking produces ten overlapping passages.

The author inspected source markers to label 12 answerable questions and two no-answer questions. The corpus includes broader skilling material as distractors. Retrieval is filtered to the selected configuration's linked documents. The benchmark configuration is **unapproved**, with neutral defaults; importing it does not enforce historical rules or infer quotas.

## Live public internship verification

On **23 November 2026 at 05:45 IST**, the startup refresh verified **54 India openings in PostgreSQL** across five sources. The refresh checks the vacancy’s application form or enabled application control and uses the original source’s deadline when one is published. The database records the last check and last successful verification. This snapshot describes availability at the time checked.

| Source checked | Verified India openings |
|---|---:|
| [SWAYAM Plus public internship directory](https://swayamplus.education.gov.in/internships), Ministry of Education and IIT Madras | 46 |
| [Rubrik Greenhouse board](https://boards-api.greenhouse.io/v1/boards/rubrik/jobs) | 4 |
| [Merkle Science Lever board](https://api.lever.co/v0/postings/merklescience?mode=json) | 2 |
| [Hevo Data Lever board](https://api.lever.co/v0/postings/hevodata?mode=json) | 1 |
| [Stripe Greenhouse board](https://boards-api.greenhouse.io/v1/boards/stripe/jobs) | 1 |
| [InMobi Greenhouse board](https://boards-api.greenhouse.io/v1/boards/inmobi/jobs) | 0 |

The employer integrations use the [Lever Postings API](https://github.com/lever/postings-api) and the [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html). SWAYAM Plus provides public individual posting pages with structured posting details and an application control. Applicants may need an account on the original portal to apply. [SWAYAM Plus programme information](https://swayamplus.education.gov.in/about)

| Academic field signals | Openings |
|---|---:|
| Computer Science and IT | 18 |
| Electronics and Communication | 2 |
| Mechanical Engineering | 4 |
| Civil Engineering | 0 |
| Electrical Engineering | 1 |
| Commerce and Finance | 5 |
| Management and Business | 21 |
| Agriculture | 0 |
| Food Technology | 2 |
| Design and Media | 3 |
| Health and Social Sciences | 2 |
| Education | 1 |
| No clear field signal | 2 |

Field counts can overlap because the same listing can be relevant to several branches. Tags describe fit signals from posting titles and requirements. The original employer requirements govern eligibility. The locations cover Tamil Nadu (26), Karnataka (13), Uttar Pradesh (2), Andhra Pradesh (1), Bihar (1), Delhi (1), Punjab (1), and remote roles in India (9).

Examples include [Stripe’s Software Engineer Intern in Bengaluru](https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=8031833), [Gantham Ventures’ Mechanical Manufacturing and Tool Room Coordination Intern in Chennai](https://swayamplus.education.gov.in/internships/613c8b71-0863-43e5-a217-19832172a309), [Chess Gaja’s Accounts and HR Internship in Madurai](https://swayamplus.education.gov.in/internships/47ce892c-bcd2-4bba-9399-8517cf7094b6), and [NSIC Technical Services Centre’s Industrial Automation Intern in Chennai](https://swayamplus.education.gov.in/internships/4a74c7d3-c677-4369-9cb1-15b45a112d77). The feed created zero capacity records.

The running dashboard matched a mechanical engineering profile to Gantham Ventures and opened the original SWAYAM Plus page with its Apply Now control. Live API checks also returned the Accounts and HR role for a commerce profile, showed Python skill evidence for a computer science profile, and returned the empty-match message for a profile with no relevant openings.

### Source-access limits

- AICTE’s public page returned a directory shell and its robots file disallows automated access to API and student paths. No vacancy from that portal was verified in this run. [AICTE directory](https://internship.aicte-india.org/internships) · [AICTE robots file](https://internship.aicte-india.org/robots.txt)
- The public PM Internship Scheme page did not expose a verifiable anonymous vacancy listing in this environment. [PM Internship Scheme](https://pminternship.mca.gov.in/)
- ASAP Kerala published civil engineering notices, but the linked Careerlink pages returned an application shell and the vacancy status could not be confirmed in the browser. [ASAP Kerala careers](https://asapkerala.gov.in/careers/) · [Careerlink application example](https://careerlink.asapkerala.gov.in/internships/list/IN26111800194)
- The MANAGE agriculture notice and NHAI civil-infrastructure call had expired application windows. [MANAGE updates](https://www.manage.gov.in/MANAGECAEIRA/RecentUpdates.aspx) · [NHAI application notice](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2299419&lang=1&reg=3)
- SmartRecruiters was excluded because its API host disallows general automated access. [SmartRecruiters robots file](https://api.smartrecruiters.com/robots.txt)

## Participant inputs

Participants provide their own résumés, or an authorized placement cell imports consented records. No profiles are collected from social media, random résumé websites or data dumps. Private files stay in the private upload volume and are excluded from Git, graph checkpoints, source reports and screenshots. Deletion removes raw files, extracted evidence, choices, case checkpoints/activity and affected derived drafts. Direct identifiers are omitted from benchmark and allocation CSV exports.

## Technical implementation references

[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence), [interrupt/resume semantics](https://docs.langchain.com/oss/python/langgraph/interrupts), [pgvector](https://github.com/pgvector/pgvector), [Sentence Transformers similarity](https://www.sbert.net/docs/sentence_transformer/usage/semantic_textual_similarity.html), [OR-Tools CP-SAT](https://developers.google.com/optimization/cp/cp_solver).
