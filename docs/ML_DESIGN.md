# Research model path

## Contract

The model uses exactly six non-laboratory features: `age`, `gender`, `bmi`, `hypertension`, `heart_disease`, and `smoking_history`. The target is a current `diabetes` label in a research dataset. This is not a future-risk forecast and has no clinical validation.

## Readiness

No approved research dataset or trained artifact is present. The Kaggle derivative's 100,000 common rows exactly match another Kaggle source whose license metadata is `Data files © Original Authors`. Real-patient-data status and rights to copied rows are unresolved; the label definition and generation process are undocumented. Dataset v2 permits a reviewed `public_research_dataset` when rights and academic-research scope are documented; it does not require every research training dataset to be synthetic. See `ml_training/DATASET_REVIEW.md`. Demo profiles are synthetic and are never used for model training or evaluation. Until an approved artifact exists, `/ml/predict` returns `MODEL_NOT_AVAILABLE`; it does not fabricate a score.

## Training workflow

`requirements-dev.txt` pins pytest for workspace checks. `ml_training/requirements.txt` pins direct training dependencies, and `ml_training/pylock.win-py311.toml` resolves their full dependency set for Windows CPython 3.11. Both training scripts require a reviewed v1 or v2 dataset manifest bound to the exact CSV SHA-256. V2 records `data_category`, real-patient-data status, `permitted_use`, rights basis, label definition/generation method, and known limitations; the with-labs comparison also requires a leakage review. A legacy v1 manifest is migrated in memory without changing its review decision. The feature contract requires explicit operator confirmation. The scripts remove under-18 rows and only exact duplicate rows across all original CSV columns. GroupShuffleSplit keeps identical fingerprints of the six model features plus HbA1c and glucose in one partition. The `year` column is audit metadata and never a model input. Preprocessing is fit on training data only; real training compares Logistic Regression, Random Forest, and XGBoost. Each candidate's threshold is selected on validation data for a 0.90 recall target and candidate selection uses validation PR-AUC. A real artifact records dataset and manifest hashes, seed, feature/lab group fingerprint, split sizes, threshold, recall-target attainment, subgroup results, and `research_only`/`clinical_validation: false` tags. `ml_training/evaluate.py` exports confusion matrix, ROC/PR, calibration, and Brier metrics to `evaluation/ml/`; `ml_training/shap_analysis.py` reports global test-set attributions and explicitly avoids causal claims. Both remain unmeasured until an approved artifact exists.

Metrics include accuracy, precision, recall/sensitivity, specificity, F1, ROC-AUC, PR-AUC, Brier score, calibration curve, subgroup summaries, and confusion matrix. Groups with fewer than 100 examples report `insufficient_n` without subgroup metrics. `ml_training/compare_features.py` defaults to `--lab-features hbA1c_level blood_glucose_level` and shares the same feature/lab fingerprint split between no-labs and with-labs runs. Its report includes the measured HbA1c/glucose proxy-label capture and warns that with-labs AUC does not represent predictive value when label leakage is unresolved.

SHAP is optional. `/api/v1/ml/explain` returns feature contributions only when a reviewed model and SHAP are installed. A feature contribution describes the model output; it does not establish causation.

No benchmark values or clinical performance claims are bundled in this repository.
