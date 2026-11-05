from __future__ import annotations

import numpy as np
import pandas as pd


FIXTURE_COLUMNS = [
    "year", "gender", "age", "location", "race:AfricanAmerican", "race:Asian",
    "race:Caucasian", "race:Hispanic", "race:Other", "hypertension", "heart_disease",
    "smoking_history", "bmi", "hbA1c_level", "blood_glucose_level", "diabetes", "clinical_notes",
]


def make_fixture_dataset(rows: int = 240) -> pd.DataFrame:
    """Create non-clinical deterministic rows with the candidate's 17-column schema."""
    if rows < 120:
        raise ValueError("The fixture needs at least 120 rows for three grouped splits.")
    rng = np.random.default_rng(42)
    gender = np.array(["Female" if i % 2 == 0 else "Male" for i in range(rows)], dtype=object)
    gender[np.arange(rows) % 13 == 0] = "Other"
    smoking = np.array(["never", "former", "current", "not current", "ever", "No Info"], dtype=object)
    label = (np.arange(rows) % 5 == 0).astype(int)
    return pd.DataFrame({
        "year": 2015 + (np.arange(rows) % 8),
        "gender": gender,
        "age": 18 + (np.arange(rows) % 63),
        "location": [f"fixture-region-{i % 4}" for i in range(rows)],
        "race:AfricanAmerican": (np.arange(rows) % 7 == 0).astype(int),
        "race:Asian": (np.arange(rows) % 7 == 1).astype(int),
        "race:Caucasian": (np.arange(rows) % 7 == 2).astype(int),
        "race:Hispanic": (np.arange(rows) % 7 == 3).astype(int),
        "race:Other": (np.arange(rows) % 7 == 4).astype(int),
        "hypertension": (np.arange(rows) % 3 == 0).astype(int),
        "heart_disease": (np.arange(rows) % 9 == 0).astype(int),
        "smoking_history": smoking[np.arange(rows) % len(smoking)],
        "bmi": np.round(18 + (np.arange(rows) % 50) * 0.37 + rng.uniform(0, 0.01, rows), 3),
        "hbA1c_level": np.choose(np.arange(rows) % 4, [5.2, 5.8, 6.1, 6.7]),
        "blood_glucose_level": np.choose(np.arange(rows) % 5, [95, 110, 126, 155, 200]),
        "diabetes": label,
        "clinical_notes": ["synthetic test fixture; no patient data" for _ in range(rows)],
    }, columns=FIXTURE_COLUMNS)
