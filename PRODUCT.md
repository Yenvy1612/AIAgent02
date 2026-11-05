# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Students and instructors using a course prototype to explore an AI-agent architecture for Vietnamese-language type 2 diabetes education. Their job is to understand how requests pass through safety checks, routing, tools, knowledge retrieval, and answer validation.

## Product Purpose

DiaCare AI is an educational course prototype for learning about an AI-agent architecture around type 2 diabetes. Its success is helping students and instructors inspect the agent workflow and its safety boundaries. It is not a clinical guidance product.

## Positioning

The prototype makes the agent pipeline observable through a chat and synthetic-history demo: a local safety gate routes requests through deterministic tools and an approved-source knowledge path, followed by citation and output checks. Its purpose is to teach that architecture, not to make care decisions.

## Operating Context

- Used locally in a browser as a course demonstration.
- Learners can explore chat, synthetic profiles, and synthetic health history.
- Chat messages stay in the current browser session and are not persisted by the backend.
- The app has no authentication, patient import, or patient editing.
- Local setup uses a React/Vite frontend and FastAPI backend. SQLite is the local default; Docker Compose provides a PostgreSQL option. Neural retrieval and external answer composition are optional integrations.

## Capabilities and Constraints

- Provides synthetic profile/history browsing, deterministic BMI calculation, reference-only lab-rule interpretation, and deterministic risk screening.
- The optional risk model is research-only, is not clinically validated, and returns unavailable when no local artifact is present. It does not forecast glucose.
- Knowledge retrieval uses only chunks marked approved for both content review and licensing. Optional pgvector/BGE retrieval has a local fallback.
- Optional Claude composition is disabled by default. When enabled, it receives a masked question and approved, redacted knowledge excerpts, not profile or tool data. The optional web fallback is also disabled by default; its results are labeled unreviewed.
- Use synthetic examples only. Do not enter real patient or identifying health data.
- The app does not diagnose, prescribe, recommend treatment decisions, or change medication. Medication changes are refused and redirected to a clinician or pharmacist.
- The emergency phrase detector is experimental and not clinically validated. It may miss emergencies; an unknown detector result must not be presented as reassurance. The UI provides an emergency action for Vietnam's 115 service.
- Missing glucose units are never inferred; the app asks for the unit and measurement context.
- Lab thresholds are educational references only. The prototype is not validated for real care or clinical triage.

## Evidence on Hand

- `data/kb/index.json` contains 665 chunks from 16 sources approved by the project owner. The owner is not a healthcare professional, so this knowledge base is not clinically validated.
- `docs/EVALUATION_REPORT.md` records current evaluation scope and results. The README reports citation accuracy at 0.27 against a 0.95 target; this is below the project's stated G3 target and must not be represented as a validated performance claim.
- The risk model has no approved research CSV available for training. Synthetic demo data must not be used to train or validate it.
- No clinical validation, real-patient evidence, testimonials, or outcome claims are established for the product.

## Product Principles

- Make the agent architecture understandable through observable request flows.
- Preserve clear safety boundaries; never present the prototype as a substitute for clinical judgment.
- Use synthetic data only and avoid collecting or persisting chat health details.
- Ground health information in approved sources and do not fabricate citations or unavailable model results.
- Keep optional integrations visibly bounded by their review and evaluation limits.
