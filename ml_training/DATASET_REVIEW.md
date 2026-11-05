# Dataset review — research training authorization and limitations

Review date: 2026-11-03. The workspace copy at `data/diabetes_dataset_with_notes.csv` has SHA-256 `608a44d5619cd7ce7fdf97f6e8d3f754d1d0de72d7ff073122aa5654e1db7da8`. The user explicitly authorized local academic-research training. That project authorization is recorded in `ml_training/dataset_approval.json`; it does not resolve rights to copied upstream rows, patient-data status, or label provenance. The CSV remains excluded from the Docker context and is not mounted into the application container.

The user confirmed that the workspace copy was downloaded from [Ziya's Kaggle page](https://www.kaggle.com/datasets/ziya07/diabetes-clinical-dataset100k-rows). This confirms the listing used to obtain the file, but does not resolve the copied-row rights, whether the records are synthetic, or the label-generation process described below.

## Source and rights

- On 2026-11-03, Kaggle's public dataset API reported [Ziya's dataset](https://www.kaggle.com/datasets/ziya07/diabetes-clinical-dataset100k-rows) as CC0, last updated 2025-02-07. Its description says 100,000 individuals and describes `clinical_notes` as summaries based on patient attributes.
- The common nine fields in that file were compared as a multiset against [iammustafatz's Kaggle dataset](https://www.kaggle.com/datasets/iammustafatz/diabetes-prediction-dataset). All 100,000 rows match exactly after row order is ignored.
- On the same date, Kaggle's public API identified the underlying dataset owner as Mohammed Mustafa, last updated 2023-04-08, with license `Data files © Original Authors`; its description calls the records medical and demographic data “from patients.” Ziya's record adds `year`, `location`, one-hot race fields, and notes, but does not document the original data collection or provide evidence that the underlying rights were relicensed.

**Current project decision: authorized for local academic-research no-labs training; upstream rights remain unresolved.** A CC0 label on the derivative is not enough to establish rights to copied source rows. The metadata does not establish whether the observations include real patient records, and it does not document label generation. The manifest records the user's explicit project authorization while retaining these limits. The trained artifact is tagged `research_only` and `clinical_validation=false`. The with-labs comparison remains blocked because `label_leakage_reviewed=false` and the observed HbA1c/glucose proxy catches 100% of adult positive labels. No clinical use is authorized or validated.

## Observed schema and quality

The downloaded file was `diabetes_dataset_with_notes.csv`: 100,000 rows and 17 columns. All columns were non-null. The six no-labs features and binary `diabetes` label match the current feature contract and allowed categories. Lab columns are `hbA1c_level` and `blood_glucose_level`. Extra columns are `year`, `location`, five race indicators, and `clinical_notes`; none belongs in the six-feature model.

After the pipeline's adult filter (`age >= 18`), 82,781 rows remain (8,418 positive labels). Age spans 0.08–80 in the raw file. Among adult records, 22,687 rows repeat the six no-labs features plus label, and 3,323 repeat the six features, both lab values, and label. There is no person identifier, so repeated-feature records cannot be grouped by person or verified as independent observations.

There are 761 distinct non-empty `clinical_notes` values. A simple scan found no email or phone-shaped strings, but that does not establish that the data is synthetic, anonymized, or free of sensitive content. The notes are present in the candidate CSV, but the training code selects only the explicit feature and label columns, excluding `clinical_notes` from model input. The CSV is excluded from the Docker build context and is not mounted into the application container.

As a leakage warning, the simple proxy `HbA1c >= 6.5 OR glucose >= 126` catches every adult positive label in this file, with many false positives. This does not prove the label-generation rule, but the Kaggle source does not document how `diabetes` was assigned. The with-labs experiment must not be interpreted until that definition is verified.

## Year distribution and split audit

The adult count before exact-duplicate removal is 82,781. Removing 10 adult rows that are exact duplicates across all 17 original CSV columns leaves 82,771 adults. The training command applies full-row duplicate removal before its adult filter and therefore records 14 duplicates across the full CSV (four are outside the adult subset). The chronological audit below uses the deduplicated adults; positive rates are descriptive dataset statistics, not model metrics.

| Year | Rows | Positive labels | Positive rate |
|---:|---:|---:|---:|
| 2015 | 7,262 | 756 | 10.41% |
| 2016 | 7,293 | 751 | 10.30% |
| 2018 | 2,191 | 241 | 11.00% |
| 2019 | 65,977 | 6,664 | 10.10% |
| 2020 | 35 | 3 | 8.57% |
| 2021 | 7 | 1 | 14.29% |
| 2022 | 6 | 2 | 33.33% |

A chronological latest-20% holdout would contain 16,554 rows, with a 10.203% positive rate versus 10.170% overall (difference 0.033 percentage points). Its size is adequate and its overall rate is close to the full adult set. The training pipeline still uses `GroupShuffleSplit` over fingerprints of the six no-labs features plus both lab values, as required to keep repeated measurements together across partitions. `year` remains audit metadata and is never a model feature.

## Reproducibility fingerprints

- Ziya CSV SHA-256: `608a44d5619cd7ce7fdf97f6e8d3f754d1d0de72d7ff073122aa5654e1db7da8`
- Underlying Kaggle CSV SHA-256: `f233fc470e904201f35310d061cb46ca0a6bc7ca5c3e428b769fb4f87f69929b`
- The common nine-column rows match as a 100,000-row multiset; the two files differ in order and in added columns.

## Research model run and remaining review

The no-labs run used model `risk-no-labs-v1-9e7fdde241ff`; held-out test metrics and SHAP results are recorded in `docs/EVALUATION_REPORT.md` and `docs/MODEL_CARD.md`. The project manifest status is `approved` on the basis of the user's explicit authorization for this local research run, but `rights_status=approved` must not be read as proof that the derivative owner relicensed the underlying copied rows. The user/team still needs to resolve upstream rights and real-patient-data status before any broader reuse or redistribution, and independently establish the source label definition/generation process. Before a with-labs comparison, a reviewer must also assess label leakage and explicitly set `label_leakage_reviewed=true` with review notes. It remains false for now.

Reproduce the authorized no-labs research run with:

```powershell
.\.venv\Scripts\python.exe -m pip install -r ml_training\requirements.txt
.\.venv\Scripts\python.exe ml_training\train.py data\diabetes_dataset_with_notes.csv --confirm-feature-contract
.\.venv\Scripts\python.exe ml_training\evaluate.py --artifact models\risk_no_labs.joblib --csv data\diabetes_dataset_with_notes.csv
.\.venv\Scripts\python.exe ml_training\shap_analysis.py --artifact models\risk_no_labs.joblib --csv data\diabetes_dataset_with_notes.csv
```

Do not run the paired with-labs comparison until the label-leakage assessment is reviewed and recorded in the manifest.
