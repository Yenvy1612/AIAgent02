# KB source review log

Review date: 2026-11-03. Rights review and clinical/content review are separate decisions. A `license_status=approved` entry below covers only the stated text-only reuse scope; it does not approve the medical content for answers. The 2026-11-04 owner decision at the end of this file supersedes the status columns below.

| Source | Local copy | Source/version review | License review | Content review | RAG status |
|---|---|---|---|---|---|
| KB-01 — QĐ 5481/QĐ-BYT | `data/kb/candidates/A_Bo_Y_Te_Viet_Nam/BYT_KB-01_QD5481_2020_Huong_dan_DTD_typ2.pdf` (source retained at `Tài liệu/5481.pdf`) | Local 77-page copy visually confirms QĐ 5481, dated 30/12/2020; PDF text extraction succeeded. The diagnostic criteria are on PDF page 11 (printed page 9). Official KCB portal marks the guidance as intended for health professionals. Current-validity status not established: the KCB clinical-process page still links a 2017 QĐ 3319 text, while some later official material cites 5481 | Unknown | Candidate; clinician-facing, current-validity, and clinical update review still required | Not ingested |
| KB-01A — QĐ 1353/QĐ-BYT | `data/kb/candidates/A_Bo_Y_Te_Viet_Nam/BYT_KB-01A_QD1353_2021_Sua_doi_QD5481.pdf` | One-page local copy downloaded from the official Tuyên Quang Sở Y tế record; visually confirms decision no. 1353/QĐ-BYT, dated 23/02/2021, effective on signing; modifies the 5481 guidance, including one insulin-treatment passage. PDF text extraction succeeded | Unknown | Candidate; must be resolved together with KB-01 | Not ingested |
| KB-25 — CDC Diabetes Meal Planning | `data/kb/candidates/D_Dinh_duong_cho_nguoi_mac_dai_thao_duong/CDC_KB-25_Diabetes_Meal_Planning_2026-11-03.md` | Official page snapshot; dated May 15, 2024 | Approved for text-only reuse with CDC attribution and prominent no-endorsement disclaimer | Candidate; English/U.S.-context guidance needs scope review | Not ingested |
| KB-27 — CDC Manage Blood Sugar | `data/kb/candidates/D_Dinh_duong_cho_nguoi_mac_dai_thao_duong/CDC_KB-27_Diabetes_Treatment_and_Glucose_Management_2026-11-03.md` | Official page snapshot; dated May 15, 2024 | Approved for text-only reuse with CDC attribution and prominent no-endorsement disclaimer | Candidate; includes glucose targets and clinical advice that need review before use | Not ingested |
| KB-28 — NIDDK Low Blood Glucose | None | Official page observed; last reviewed July 2021 | Under review: NIDDK permits reuse of most content but warns against use to recommend specific medical advice/treatments/referrals; intended chatbot use needs clarification | Candidate; stale review date | Not ingested |
| KB-29 — NIDDK Diabetes & Foot Problems | None | Official page observed; last reviewed January 2017 | Under review for the same NIDDK reuse caveat | Candidate; stale review date | Not ingested |
| KB-18 — WHO Package of Essential NCD Interventions (PEN) | `data/kb/candidates/C_WHO/WHO_2020_PEN_Essential_NCD_Interventions_Primary_Health_Care.pdf` | Official 2020 publication downloaded from WHO; 85 PDF pages with 77 numbered content pages | Page 2 states CC BY-NC-SA 3.0 IGO; approved for WHO-owned text in the non-commercial course-demo scope with attribution/share-alike; third-party material excluded | Candidate; primary-care guidance includes clinical targets and pathways and needs qualified review | Not ingested |
| KB-30A — WHO Healthy diet | `data/kb/candidates/C_WHO/WHO_KB-30A_Healthy_Diet_2026-11-03.md` | Official fact sheet snapshot dated 26 January 2026 | Approved for WHO-authored text under CC BY-NC-SA 3.0 IGO in the non-commercial course-demo scope; attribution and share-alike required; third-party media excluded | Candidate; broad nutrition guidance needs review for diabetes-specific and Vietnamese context | Not ingested |
| KB-30B — WHO Physical activity | `data/kb/candidates/C_WHO/WHO_KB-30B_Physical_Activity_2026-11-03.md` | Official fact sheet snapshot dated 26 June 2024 | Approved for WHO-authored text under CC BY-NC-SA 3.0 IGO in the non-commercial course-demo scope; attribution and share-alike required; third-party media excluded | Candidate; broad activity guidance covers several populations and needs review for scope | Not ingested |
| Other manifest sources | No verified local corpus supplied | Candidate/reference only | Unknown; ADA rows explicitly reference-only | Candidate | Not ingested |

## Rights evidence and scope

- CDC's [Use of Agency Materials](https://www.cdc.gov/Other/imagereuse.html) says most CDC information is public domain, with exceptions for contractor, grantee, and third-party material. It requires attribution and a prominent disclaimer that reuse does not imply CDC/ATSDR/HHS/U.S. Government endorsement. The CDC pages above are text-only source candidates; images, logos, and linked third-party content are excluded from the approved scope.
- NIDDK's [Copyright policy](https://www.niddk.nih.gov/copyright) says most site information may be reproduced with attribution, but identifies exceptions and says NIDDK content must not be used to imply endorsement or recommend specific medical advice, treatments, or referrals. Because DiaCare is an educational medical Q&A demo, these two entries stay out of the index until that intended use is resolved.
- WHO's [Copyright, Licensing and Permissions policy](https://www.who.int/about/policies/publishing/copyright) states WHO publications issued since 12 November 2016 use CC BY-NC-SA 3.0 IGO. KB-18's downloaded PDF states that license directly on page 2; it is a 2020 publication with 77 numbered content pages. KB-30A and KB-30B are 2026 and 2024 official fact sheets covered by the policy. WHO-authored text is cleared for this non-commercial course-demo scope with attribution and share-alike; third-party credited components remain excluded. WHO material must not be used to suggest endorsement.
- Rights approval does not equal clinical review. CDC content remains `review_status=candidate`; NIDDK content remains both `license_review` and `candidate`. Local snapshots exist for KB-25, KB-27, KB-30A, and KB-30B, but all are candidate files and none has been indexed or approved for answers.
- The official [Cục Quản lý Khám, chữa bệnh page](https://daithaoduong.kcb.vn/huong-dan-chan-doan-dieu-tri-dai-thao-duong-tip-2) links both QĐ 5481 and its amendment, and explicitly labels the guidance for health professionals. The included 77-page PDF's first page shows QĐ 5481 dated 30/12/2020 and says it replaces QĐ 3319. The official [Tuyên Quang Sở Y tế record](https://soyte.tuyenquang.gov.vn/van-ban/1353-qd-byt.doc) identifies QĐ 1353 as the amendment; its linked [one-page decision](https://soyte.tuyenquang.gov.vn/download-van-ban.htm?id=971) confirms it changes content in the 5481 guide. The supplied 5481 copy has not been merged with that amendment. Both remain out of the index because current clinical applicability, intended-user scope, and rights for the full guideline are unresolved.
- A freshness check on 2026-11-03 did not establish whether 5481 plus 1353 remains the current applicable guidance. The official KCB [clinical-process page](https://daithaoduong.kcb.vn/quy-trinh-lam-sang-dieu-tri-dai-thao-duong) links a 2017 QĐ 3319 document, and its [drafts page](https://daithaoduong.kcb.vn/du-thao) lists a diabetes type 2 guidance entry; later official references to QĐ 5481 do not establish that no newer or superseding instrument exists. Treat both local files as historical candidates pending confirmation by an authorized clinical/legal reviewer. The amendment copy's SHA-256 is `404beba5811b8894b0164ef4a926989b26d84d2c4099dc82d688a8fcf70595ae`.

Update `sources.csv` and this log after verifying each exact document, version, intended population, and permission to index it. Both approval fields must be `approved`; an exact local copy must also be indexed by `scripts/ingest_kb.py` before retrieval can use a source.

## P0 content-review checklist — reviewer completion required

The boxes below are intentionally unsigned. For each source, a reviewer must record evidence for the author/organization, exact version and effective/current status, license and permitted AI/indexing use, and intended population. `review_status` remains `candidate` until the reviewer completes and signs the row.

| Source | Author / organization verified | Version / effective status verified | License / indexing permission verified | Population / scope reviewed | Reviewer signature | Date | Decision |
|---|---|---|---|---|---|---|---|
| KB-01 QĐ 5481 | [ ] | [ ] | [ ] | [ ] | Nguyen Vy | 2026-11-04 | Approved by owner instruction; checklist not completed |
| KB-01A QĐ 1353 | [ ] | [ ] | [ ] | [ ] | Nguyen Vy | 2026-11-04 | Approved by owner instruction; checklist not completed |
| KB-18 WHO PEN | [ ] | [ ] | [ ] | [ ] | Nguyen Vy | 2026-11-04 | Approved by owner instruction; checklist not completed |
| KB-25 CDC Diabetes Meal Planning | [ ] | [ ] | [ ] | [ ] | Nguyen Vy | 2026-11-04 | Approved by owner instruction; checklist not completed |
| KB-27 CDC Manage Blood Sugar | [ ] | [ ] | [ ] | [ ] | Nguyen Vy| 2026-11-04 | Approved by owner instruction; checklist not completed |
| KB-30A WHO Healthy diet | [ ] | [ ] | [ ] | [ ] | Nguyen Vy| 2026-11-04 | Approved by owner instruction; checklist not completed |
| KB-30B WHO Physical activity | [ ] | [ ] | [ ] | [ ] | Nguyen Vy| 2026-11-04 | Approved by owner instruction; checklist not completed |
| KB-16 WHO Classification | [ ] | [ ] | [ ] | [ ] | Nguyen Vy| 2026-11-04 | Approved by owner instruction; checklist not completed |
| KB-31 QĐ 1530 loét bàn chân | [ ] | [ ] | [ ] | [ ] | Nguyen Vy| 2026-11-04 | Approved by owner instruction; checklist not completed |
| KB-32 QĐ 3087 tiền ĐTĐ | [ ] | [ ] | [ ] | [ ] | Nguyen Vy| 2026-11-04 | Approved by owner instruction; checklist not completed |
| KB-33 QĐ 2558 võng mạc | [ ] | [ ] | [ ] | [ ] | Nguyen Vy| 2026-11-04 | Approved by owner instruction; checklist not completed |
| KB-34 WHO Type 2 Diabetes | [ ] | [ ] | [ ] | [ ] | Nguyen Vy| 2026-11-04 | Approved by owner instruction; checklist not completed |
| KB-36 WHO medicines and insulin | [ ] | [ ] | [ ] | [ ] | Nguyen Vy| 2026-11-04 | Approved by owner instruction; checklist not completed |
| KB-37 QĐ 2557 chụp ảnh đáy mắt | [ ] | [ ] | [ ] | [ ] | Nguyen Vy| 2026-11-04 | Approved by owner instruction; checklist not completed |
| KB-38 WHO hypertension | [ ] | [ ] | [ ] | [ ] | Nguyen Vy| 2026-11-04 | Approved by owner instruction; checklist not completed |
| KB-39 WHO global monitoring | [ ] | [ ] | [ ] | [ ] | Nguyen Vy| 2026-11-04 | Approved by owner instruction; checklist not completed |
| KB-35 QĐ 1470 thai kỳ | [ ] | [ ] | [ ] | [ ] | Nguyen Vy |  | Not approved: pregnancy out of scope; `.docx` not readable by ingest |
## Local file fingerprints

| Source | Local path | SHA-256 | Extraction status |
|---|---|---|---|
| KB-01 | `data/kb/candidates/A_Bo_Y_Te_Viet_Nam/BYT_KB-01_QD5481_2020_Huong_dan_DTD_typ2.pdf` | `305fc9c51d54418f5798e7691d59f94d24545e0dd728945e2225794730694486` | Text extracted; OCR not needed |
| KB-01A | `data/kb/candidates/A_Bo_Y_Te_Viet_Nam/BYT_KB-01A_QD1353_2021_Sua_doi_QD5481.pdf` | `404beba5811b8894b0164ef4a926989b26d84d2c4099dc82d688a8fcf70595ae` | Text extracted; OCR not needed |

The QĐ 5481/1353 relationship is partial: QĐ 1353 changes a treatment passage identified as page 37 in the printed guide; it does not replace the entire 5481 document. The ingest metadata records the affected PDF page (39) as amended and answers citing that page must name QĐ 1353. Ingest replaces the old sentence on PDF page 39 with the QĐ 1353 wording through `text_replacements`. The reviewer must verify this replacement before approval.

## Reorganization decisions, 2026-11-04

Reviewer: project owner (signature rows above remain empty until each source is decided). Files below are kept in `data/kb/rejected/`, which Git and the Docker build context ignore.

| Files | Location | Reason |
|---|---|---|
| 12 ADA Standards of Care 2026 PDFs | `rejected/license_blocked/` | First page of each states the work may not be used for text or data mining, machine learning, or similar technologies without prior written permission. KB-06 to KB-15 and KB-23 stay `reference_only`. |
| Diabetes Plate flyer | `rejected/license_blocked/` | No license statement in the file; refers to Diabetes Food Hub and the American Diabetes Association. KB-25 covers the Plate Method. |
| ADA 2022 Introduction | `rejected/out_of_scope/` | Historical methodology text; no clinical content needed. |
| QĐ 3319 decision and the 2017 guide | `rejected/superseded/` | Article 3 of QĐ 5481 replaces QĐ 3319. The QĐ 3319 file is a one-page decision with garbled extracted text, not the guide. |
| QĐ 3280/2011, QT 3798/2017 | `rejected/superseded/` | **Needs reviewer confirmation:** older material, but the local files do not state its repeal. |
| WHO PEN duplicate, unsigned QĐ 2558 copy | `rejected/duplicate/` | Same SHA-256 as the kept PEN file; near-identical text to the signed QĐ 2558 copy. |

KB-35 (QĐ 1470, replaces QĐ 6173/2018), KB-36, KB-37, KB-38, and KB-39 stay in `candidates/` as deferred. Pregnancy remains out of scope; KB-01 PDF pages 54-57 are excluded for that reason, while PDF page 12 mixes general and gestational screening text and needs reviewer attention. `exclude_pages` and `topic_by_page` in `document_metadata.json` are proposals taken from each document's contents page, for the reviewer to confirm. `source_url` is empty for KB-31 to KB-39 until an official URL is verified.

## Extraction notes for the reviewer, 2026-11-04

- KB-18 (WHO PEN): many pages are rotated flowcharts. PDF pages 20, 23, 27, 49, 50, 53, 54, 55, and 60 use a font without a Unicode map, and thresholds disappear from the text ("%3ȲPP+J" for "BP ≥ mmHg"), so they are skipped. Other PEN pages may still contain isolated runs below the skip threshold. Section labels on later PEN chunks can be wrong. Citations by page are correct.
- Image-only pages skipped: KB-01 page 23, KB-18 page 11, KB-32 pages 15-16. Transcribe into a reviewed Markdown file only if the content is needed.
- KB-31 and KB-33 carry a diagonal digital-signature stamp on every page; extraction removes it.
- `scripts/dry_run_kb.py` writes `tmp/kb_dry_run/review_chunks.md` for reading every chunk before signing.

## Approval decision, 2026-11-04

The project owner, as reviewer, instructed approval of all files in `data/kb/candidates/` except KB-35. QT 3798/2017 was dropped by the owner the same day and is back in `rejected/superseded/`. `review_status` and `license_status` were set by Claude on that instruction.

- This is a blanket decision. The per-source checklist above was not completed, and the signature cells await the owner's name. The chunks were not read individually as part of this decision.
- The owner states they are not a healthcare professional, so the KB is a demo that has **not been clinically validated**.
- WHO files carry CC BY-NC-SA 3.0 IGO: non-commercial use, attribution, share-alike. The Bộ Y tế files state no license; `license_status=approved` for them rests on the owner's decision alone.
- KB-35 stays `candidate`. Files in `data/kb/rejected/`, including ADA, are not approved.
