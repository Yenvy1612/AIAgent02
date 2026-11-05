# DiaCare AI v1.1 — local educational prototype

DiaCare AI is a Vietnamese-language course demo for learning about an AI-agent architecture around type 2 diabetes. It contains 24 synthetic profiles, deterministic BMI and lab-rule tools, a two-signal local safety gate, a LangGraph router, a citation-checked KB retrieval path, and chat/history screens.

This is not a clinical system. It does not diagnose, prescribe, change medication, or forecast glucose. It has no authentication and accepts synthetic profiles only. Do not enter real health or identifying data. Chat messages are held in the current browser session and are not saved by the backend.

## Run locally

Requirements: Python 3.11+, Node.js 20+, npm.

In PowerShell from the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. The API is available at `http://127.0.0.1:8000/api/v1/health`; interactive API documentation is at `http://127.0.0.1:8000/docs`.

Run the local acceptance checks with `python -m unittest discover -s tests -v`.

## Run objective evaluations

From the project root, the curated Safety Gate, unit, and tool-routing reports can be regenerated with:

```powershell
python scripts\evaluate_safety.py
python scripts\evaluate_units.py
python scripts\evaluate_tool_selection.py
```

The RAG evaluator runs the gold set in `evaluation/rag/gold_questions.json` against the approved index: `python scripts\evaluate_rag.py`. To use other reviewed cases, fill `evaluation/rag/benchmark.template.json` and pass it with `--cases`. The report's `retrieval_modes` field shows which retrieval path was measured, so run it where the neural stack is available, such as inside the Compose app container. See `docs/EVALUATION_REPORT.md` for the current scope and results.

The local default database is SQLite at `data/diacare_demo.sqlite3`. The database is seeded on first startup and contains only synthetic profiles and readings. For a database reset, stop the API, remove that SQLite file, then start the API again.

## Run with Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open `http://127.0.0.1:8000`. Compose binds the app to loopback; PostgreSQL stays on a private container network and also stores the KB vectors through pgvector. Compose reports the app as healthy only after `/api/v1/health` responds successfully. The app mounts only `data/kb` and `models`; research CSV files in `data/` stay outside the app container. The sample password in `.env.example` is only for local demonstration.

The Dockerfile base images and Compose PostgreSQL (pgvector) image are pinned by digest for repeatable builds.

The default image keeps the large ML and neural retrieval extras optional. If the selected research artifact uses XGBoost or you need SHAP explanations, set `DIACARE_INSTALL_ML_MODELS=1` in `.env` and rebuild with `docker compose up --build`; the flag installs the pinned XGBoost/SHAP runtime packages. If Logistic Regression or Random Forest is selected, this extra is not needed.

### Vector search

Set `DIACARE_INSTALL_RAG_MODELS=1` in `.env` to install FlagEmbedding and PyTorch, then rebuild. The first model call downloads about 7 GB of weights into a persistent Compose cache. Load the approved chunks into pgvector once, and again whenever `data/kb/index.json` changes:

```powershell
docker compose exec app python /app/scripts/index_vectors.py
```

`scripts/rebuild_kb.py` does the same after rebuilding `data/kb/index.json` from the source files. `GET /api/v1/health` reports the active mode. If the models, pgvector, or GPU memory are unavailable, retrieval falls back to local BM25/character TF-IDF.

The default build uses CPU PyTorch, where one query took about 34 s on the test machine with the settings used before tuning. For an NVIDIA GPU, uncomment the GPU lines in `.env`, as shown in `.env.example`, then rebuild. This adds `docker-compose.gpu.yml` and a CUDA build of PyTorch, which grew the image from 3.1 GB to 10.6 GB. On a 4 GB GTX 1650, a query took about 4.6 s and used about 3.5 GB of GPU memory. Run only one process that loads the models at a time on a GPU that small. Keep `DIACARE_BGE_RERANK_FP16=false`, because half precision made the reranker about five times slower there.

## What works in this prototype

- `GET /api/v1/demo/profiles` — list synthetic profiles.
- `GET /api/v1/demo/profiles/{id}/history` — read synthetic glucose history and synthetic HbA1c values.
- `POST /api/v1/clinical/bmi` — calculate BMI.
- `POST /api/v1/clinical/classify` — interpret HbA1c/glucose only when the matching diagnostic rule source is retrieved and approved; preserve units, ask for missing units, and otherwise refuse interpretation.
- `POST /api/v1/ml/predict` and `/api/v1/ml/explain` — validate the six-feature contract and return a research-only result when the local model artifact is present; otherwise return unavailable.
- `POST /api/v1/knowledge/search` — search only chunks marked `approved` and `license_status=approved`; uses pgvector + BGE-M3 + BM25/RRF + BGE reranking when configured, with a local fallback.
- `POST /api/v1/chat` — Safety Gate → LangGraph routing → up to five tools → fusion and citation validation.
- `POST /api/v1/safety/check` — internal demo endpoint for the experimental local safety heuristic.

Claude composition is optional and disabled by default. To enable it, set `DIACARE_LLM_ENABLED=true` and `ANTHROPIC_API_KEY` in `.env`, then restart Compose. It receives approved KB excerpts after medication and dose sentences are removed, plus the question after common measurements and identifiers are masked. It does not receive BMI, lab findings, risk scores, SHAP values, history, or demo profile data. Free text can still contain identifying health details, so use synthetic examples only. Each explanation must pass citation, number, URL, citation-coverage, and diagnostic-claim checks; otherwise the deterministic answer is returned. Safety, medication refusal, unit clarification, and emergency responses do not call Claude.

The web fallback is also optional and disabled by default (`DIACARE_WEB_SEARCH_ENABLED=false`). When enabled, and only when the approved KB cannot answer a general diabetes question at the normal safety level, a **filtered copy of the user's question is sent to Anthropic and its search provider** ($10 per 1,000 searches plus tokens). Questions with measurements, a selected profile, contact details, or medication changes are never sent. Results are limited to `kb_manifest/web_allowlist.json`. **Web answers are not reviewed**: they carry the status `WEB_UNVERIFIED`, a fixed label, and separate `web_sources`, and never appear as approved citations.

## Knowledge Base approval and ingest

`kb_manifest/sources.csv` records the design's proposed sources and the reorganized local files in `data/kb/candidates/`. 16 sources are approved by the project owner and indexed as 665 chunks in `data/kb/index.json`; the other 25 stay `candidate` and are blocked from ingest. Decisions are logged in the [source review log](kb_manifest/source_review.md). The owner is not a healthcare professional, so this is an unvalidated demo KB. ADA Standards of Care 2026 PDFs are held in `data/kb/rejected/` because each states it may not be used for text or data mining or machine learning without written permission. See [GUIDE.md](GUIDE.md) for the repair steps. `python scripts\dry_run_kb.py` builds a throwaway index and a chunk review file under `tmp/kb_dry_run/` without changing the manifest or `data/kb/index.json`.

Review each source, its current version, intended population, and permission to index it. Change both `review_status` and `license_status` to `approved` only after that review; put the exact local copy under the workspace and set `local_path`. Then run:

```powershell
python scripts\verify_kb_sources.py
python scripts\ingest_kb.py
```

The ingest script refuses non-approved sources and files outside the workspace. PDF extraction requires `PyMuPDF` (`pip install PyMuPDF`). Review extracted chunks and citation metadata before using them. For neural retrieval, install `backend/requirements-rag.txt` (`pip install -r backend\requirements-rag.txt`) or build Compose with `DIACARE_INSTALL_RAG_MODELS=1`, then run the pgvector indexing step. The indexer embeds only approved, licensed chunks. `GET /api/v1/health` reports the active retrieval mode and pgvector/model/composer configuration.

## Research model training

No approved research CSV is available for training. An unapproved candidate copy at `data/diabetes_dataset_with_notes.csv` matches the Kaggle file reviewed in [DATASET_REVIEW.md](ml_training/DATASET_REVIEW.md); its source rights, label-generation process, and synthetic-only provenance remain unresolved. The CSV is excluded from the Docker build context. Synthetic demo data must not be used to train or validate the research model. Before training, complete `ml_training/dataset_approval.json` with evidence for the exact CSV SHA-256, source rights, synthetic-only provenance, label definition and generation method, reviewer, and review date. The with-labs experiment also requires a documented label-leakage review. The script refuses a missing or unapproved manifest. The training program expects the six-feature contract plus a binary `diabetes` label. Review the dataset schema, duplicate rows, category values, and feature contract. It detects likely identifier/date columns and supports person-grouped or chronological splits. Logistic Regression, Random Forest, and XGBoost are required. Each candidate's threshold is selected on validation data to target at least 0.90 recall; held-out test data is used only for reporting. Then install the pinned Windows/Python 3.11 lock and run:

```powershell
pip install -r ml_training\pylock.win-py311.toml
python ml_training\train.py path\to\reviewed.csv --confirm-feature-contract
```

Training writes `models/risk_no_labs.joblib` and a model-card/metrics JSON beside it, including dataset and artifact SHA-256, training script hash, split-row fingerprints, and runtime package versions. Candidate selection uses validation PR-AUC and all three candidates receive held-out test metrics from the same train-fitted models used to choose validation thresholds. The report includes a calibration curve and subgroup metrics where group sizes allow. Runtime inference verifies the saved artifact hash and applies the metadata threshold. The artifact remains research-only and is not clinically validated. If the observed CSV categories do not match the contract, update and review the contract before training.

`ml_training/compare_features.py` uses the same split for the six-feature and with-labs feature sets, tunes each candidate threshold on validation data, and reports held-out test metrics for every candidate. The test set is not used to pick candidates or thresholds. With no reviewed CSV, model criteria remain not measured.

The checked-in full training lock `ml_training/pylock.win-py311.toml` targets Windows CPython 3.11. `ml_training/requirements.txt` pins the direct package versions for other supported environments; each run also records the resolved runtime versions in its report.

## Current implementation boundaries

- Only synthetic demo profiles are seeded. There is no login, patient import, or patient editing. Claude is an optional composer; when enabled, it receives a masked question and approved, redacted KB excerpts, not profile or tool data.
- The risk model is a research-only artifact and is not clinically validated. Without the local artifact, the risk endpoint returns unavailable. No placeholder score is generated.
- The KB index holds 16 sources approved by the project owner, who is not a healthcare professional. The content has not been clinically validated. G3 is not met: citation accuracy is 0.27 against a 0.95 target. See `kb_manifest/source_review.md` and `docs/EVALUATION_REPORT.md`.
- The answer step removes medication and dose content from KB excerpts. In most topics it removes only the affected sentences and tells the user; in the medication, hospital, and complications topics it drops the whole excerpt. Answers can therefore be incomplete, so check the cited source. Questions about antibiotics or glucagon get the medication refusal.
- The emergency phrase detector is experimental and not clinically validated. Its presence does not guarantee detection. The persistent UI emergency action links to Vietnam's 115 service.
- Lab thresholds are reference-only educational rules, not a substitute for examination, repeat testing, or clinician judgment. The app makes no diagnosis.
- Neural retrieval is optional and off by default. It has been measured on the gold set, but its rerank threshold was chosen on that same set, so those results may not generalize. Claude composition is also optional and off by default, and its answer quality has not been evaluated. Automatic source verification and representative RAGAS and safety benchmarks remain incomplete.

See `docs/DESIGN_OBJECTIVES.md`, `docs/ARCHITECTURE.md`, `docs/SAFETY_POLICY.md`, `docs/KB_DESIGN.md`, `docs/ML_DESIGN.md`, and `docs/EVALUATION_REPORT.md` for the objectives, implementation notes, and current measurements.
