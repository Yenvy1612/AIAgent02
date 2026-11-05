# DiaCare AI no-labs research model card

## Status

The local candidate was trained on 2026-11-03 under the user's explicit
project authorization for academic-research use. The authorization does not
resolve rights to the copied upstream rows. `usage` is `research_only` and
`clinical_validation` is `false`; this artifact is not approved for clinical
use.

- Model: `risk-no-labs-v1-9e7fdde241ff` (XGBoost pipeline)
- Artifact SHA-256: `9e7fdde241ffae5e96d44e272217e6e82bf30900cacc7912d319869a031ad089`
- Dataset SHA-256: `608a44d5619cd7ce7fdf97f6e8d3f754d1d0de72d7ff073122aa5654e1db7da8`
- Approval manifest SHA-256: `f25414fcd5b079476639873109ad54917da30bdafc08055bc2d8884c2b94f7a9`
- Fingerprint split SHA-256: `aba010f0ae648f76ffbbdd61f455d39f872f15bb41ea2f13a6b961c8b0d00421`
- Split: 53,825 train / 12,437 validation / 16,509 test; 79,368 groups
- Exact duplicate rows removed across the original CSV: 14
- Selected threshold: `0.3242011368`; validation recall `0.9001` met the 0.90 target

## Intended use and limits

- Research and course demonstration of classification against the dataset's
  supplied current `diabetes` label.
- The model uses only `age`, `gender`, `bmi`, `hypertension`,
  `heart_disease`, and `smoking_history`.
- A score is not a diagnosis, a future-risk forecast, or a treatment
  recommendation. Do not use for screening, triage, or clinical decisions.
- The project authorization is for local academic research. The derivative's
  100,000 rows match the underlying iammustafatz Kaggle dataset as a multiset,
  whose listing says “Data files © Original Authors.” Rights to copied rows
  remain unresolved. Whether the records are real patient data is unknown.
- The source does not document the target definition or label-generation
  method. A proxy `HbA1c >= 6.5 OR glucose >= 126` captures 100% of adult
  positive labels. The separate label-leakage review remains false, so no
  with-labs comparison was run and such AUC must not be treated as predictive
  value.
- There is no person identifier. Grouping identical six-feature plus two-lab
  fingerprints reduces leakage across partitions but cannot establish
  person-level independence.
- Glucose has only 18 distinct values, no fasting/random/OGTT type, and an
  implied mg/dL unit. `year` is audit metadata, not a feature.
- `gender=Other` has 18 adult records in the source; its test subgroup has only
  n=4 and is withheld as `insufficient_n` (<100).
- SHAP values describe model associations and do not support causal inference.

## Held-out evaluation

Metrics were computed once on the fixed 16,509-row test split at the threshold
selected on validation. The test recall is below the validation target, and
precision and specificity are low. This is an offline dataset result, not
evidence of clinical performance.

| Measure | Held-out test result |
|---|---:|
| Accuracy | 0.5567 |
| Precision | 0.1707 |
| Recall / sensitivity | 0.8783 |
| Specificity | 0.5205 |
| F1 | 0.2859 |
| ROC-AUC | 0.7952 |
| PR-AUC | 0.3021 |
| Brier score | 0.1828 |
| Confusion matrix (TN, FP, FN, TP) | 7,725; 7,116; 203; 1,465 |
| Validation recall target 0.90 | Met on validation (0.9001); held-out test recall is 0.8783 |
| `gender=Other` test subgroup | n=4, `insufficient_n`; no subgroup metric reported |
| Clinical validation | False |

The ten largest global mean absolute SHAP features were led by age (0.9777),
BMI (0.5171), and hypertension (0.1782). These are model associations, not
causal effects. Full metrics and curves are in
`evaluation/ml/risk-no-labs-v1-9e7fdde241ff_evaluation.json`; global SHAP
values are in `evaluation/ml/risk-no-labs-v1-9e7fdde241ff_shap.json`.

## Reproduction

The training pipeline uses seed 42, removes exact full-row duplicates across
the original CSV, filters adults, and groups records by fingerprints of the
six no-labs features plus HbA1c and glucose. It selects a threshold on the
validation partition to target recall 0.90. `year`, location, race indicators,
clinical notes, HbA1c, and glucose are not model inputs.

```powershell
.\.venv\Scripts\python.exe ml_training\train.py data\diabetes_dataset_with_notes.csv --confirm-feature-contract
.\.venv\Scripts\python.exe ml_training\evaluate.py --artifact models\risk_no_labs.joblib --csv data\diabetes_dataset_with_notes.csv --manifest ml_training\dataset_approval.json
.\.venv\Scripts\python.exe ml_training\shap_analysis.py --artifact models\risk_no_labs.joblib --csv data\diabetes_dataset_with_notes.csv --manifest ml_training\dataset_approval.json
```

