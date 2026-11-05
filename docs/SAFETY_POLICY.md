# Safety policy for the educational prototype

- This prototype is not for diagnosis, prescribing, or treatment decisions.
- Only synthetic profiles and synthetic readings are present. Do not enter real patient data.
- Deterministic emergency rules run first. A Tier 1 emergency immediately bypasses Tier 2, retrieval, and the composer, and returns a fixed response that tells the user to call 115.
- Tier 2 is a different model class: a local character TF-IDF plus Logistic Regression classifier trained on the project's curated Vietnamese emergency/non-emergency phrases. The gate runs Tier 2 with a one-second timeout and combines emergency signals with OR logic. It is experimental and not clinically validated.
- If Tier 2 raises an error or times out before Tier 1 detects an emergency, the gate returns `UNKNOWN`; the agent bypasses all tools and responds with a fixed safety-uncertain message. This fail-closed path is exercised by curated tests, but it does not simulate every deployment or hardware failure.
- A missing glucose unit is never inferred. The app asks for `mg/dL` or `mmol/L` and for measurement context.
- Medication dose changes, starts, stops, and insulin titration are refused and redirected to a clinician/pharmacist. Emergency symptoms use the fixed 115 path.
- The final output validator also scans answer text for medication quantities, administration instructions, and schedules. A match is replaced with the fixed refusal, and tool output/evidence/citations are removed from the response. The scan excludes supported glucose units such as mg/dL and mmol/L; its curated probes are reported separately from the input-request cases.
- The emergency button is always visible in the UI. It opens an emergency prompt with a user-initiated `tel:115` link.
- `UNKNOWN` or detector failure must never be rendered as “no emergency.” If Tier 2 is unavailable, the fixed uncertainty response and emergency button remain available.
- The safety endpoint is intended for internal demo evaluation only. Its output is not a validated triage result.
- No clinician notification or escalation integration exists.

The rules and classifier can miss symptoms, context, negation, dialect, and indirect speech. The 20-case curated Tier 2 evaluation measured 10/10 emergency recall and 10/10 non-emergency specificity; this small set is not representative or clinical validation. The separate 7/7 emergency routing evaluation and 6/6 medication-request cases are also curated. These components must not be deployed for real care.

## Web fallback

- Disabled by default. It runs only after the Safety Gate returns `NORMAL` and the approved KB returns `INSUFFICIENT_EVIDENCE`, for a general in-scope question. It never runs for emergencies, medication requests, measurements, or a selected demo profile.
- Only a filtered question leaves the app. Messages with an email, phone number, profile code, or a number together with personal context are not sent.
- The backend keeps only passages whose citations all point to an allowed HTTPS domain, adds a fixed unreviewed label, and applies the same medication output guard. Any failure falls back to the normal refusal.
- Web answers are not clinically reviewed. This is an accepted exception to the approved-source rule for this demo and is excluded from the G3 measurements.

## Known issue: Tier 2 false emergencies

The local classifier labels some ordinary education questions as `EMERGENCY`, for example "Vì sao người đái tháo đường nên tập thể dục?" and "Người bệnh đái tháo đường nên uống nước gì?". They receive the 115 template instead of an answer. This predates the KB repair and has not been changed.

## Foot wound and cure-claim boundary

Requests to treat an existing foot ulcer or wound, and questions about whether a medicine cures diabetes, are refused at the Safety Gate as `CLINICAL_REVIEW`, even when approved sources contain matching text. General foot care and prevention questions still go to retrieval. These are keyword rules in `backend/app/safety/keyword_rules.py`, so differently worded requests can still get through.
