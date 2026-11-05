from __future__ import annotations

import hashlib
import json
import platform
from importlib.metadata import PackageNotFoundError, version

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit, train_test_split


ID_NAMES = {"id", "patientid", "personid", "subjectid", "participantid", "recordid", "patientcode"}
# A plain `year` field is retained for auditing; it is never auto-selected as a split clock.
TIME_NAMES = {"time", "date", "datetime", "timestamp", "measuredat", "measurementdate", "recordedat"}


def split_row_fingerprints(splits: dict[str, object]) -> dict[str, str]:
    """Hash original CSV row indexes for each frozen train/validation/test split."""
    return {
        name: hashlib.sha256(
            "\n".join(sorted(str(value) for value in row_ids)).encode("utf-8")
        ).hexdigest()
        for name, row_ids in splits.items()
    }


def fingerprint_groups(data: pd.DataFrame, columns: list[str]) -> pd.Series:
    missing = [column for column in columns if column not in data.columns]
    if missing:
        raise ValueError(f"Fingerprint columns are missing from the split data: {missing}")
    canonical = data[columns].astype("string").fillna("<MISSING>").agg("\x1f".join, axis=1)
    return canonical.map(lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()).rename("split_group")


def split_fingerprint(splits: dict[str, object], groups: pd.Series) -> dict[str, object]:
    split_rows = split_row_fingerprints(splits)
    groups_hash = hashlib.sha256("\n".join(sorted(groups.astype(str).tolist())).encode("utf-8")).hexdigest()
    payload = {"split_rows": split_rows, "group_assignments_sha256": groups_hash}
    return {
        "sha256": hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest(),
        "split_row_index_sha256": split_rows,
        "group_assignments_sha256": groups_hash,
        "group_count": int(groups.nunique()),
    }


def year_split_audit(data: pd.DataFrame, label: pd.Series, year_column: str = "year") -> dict[str, object] | None:
    if year_column not in data.columns:
        return None
    years = pd.to_numeric(data[year_column], errors="coerce")
    if years.isna().any():
        return {"status": "NOT_MEASURED", "reason": f"{year_column} contains non-numeric values."}
    grouped = pd.DataFrame({"year": years, "label": label.astype(int)}, index=data.index)
    distribution = [
        {"year": str(year), "n": int(group["label"].size), "positives": int(group["label"].sum()), "positive_rate": float(group["label"].mean())}
        for year, group in grouped.groupby("year", sort=True)
    ]
    ordered_ids = grouped.sort_values("year").index.to_numpy()
    test_start = max(1, int(len(ordered_ids) * 0.8))
    test_ids = ordered_ids[test_start:]
    overall_rate = float(label.mean())
    test_rate = float(label.loc[test_ids].mean()) if len(test_ids) else None
    return {
        "status": "MEASURED",
        "column": year_column,
        "distribution": distribution,
        "chronological_80_20_test_rows": int(len(test_ids)),
        "chronological_80_20_test_positive_rate": test_rate,
        "overall_positive_rate": overall_rate,
        "absolute_positive_rate_difference_percentage_points": round(abs(test_rate - overall_rate) * 100, 6) if test_rate is not None else None,
        "year_is_model_feature": False,
    }


def runtime_versions() -> dict[str, str | None]:
    packages = ("numpy", "pandas", "scikit-learn", "joblib", "xgboost")
    versions: dict[str, str | None] = {"python": platform.python_version()}
    for package in packages:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    return versions


def resolve_split_columns(columns, group_column: str | None, time_column: str | None, parser) -> tuple[str | None, str | None]:
    normalized = {"".join(ch for ch in name.lower() if ch.isalnum()): name for name in columns}
    id_candidates = [name for key, name in normalized.items() if key in ID_NAMES]
    time_candidates = [name for key, name in normalized.items() if key in TIME_NAMES]
    if group_column is None and len(id_candidates) == 1:
        group_column = id_candidates[0]
    elif group_column is None and len(id_candidates) > 1:
        parser.error(f"Multiple possible person/record identifiers found {id_candidates}; choose --group-column explicitly.")
    if time_column is None and len(time_candidates) == 1:
        time_column = time_candidates[0]
    elif time_column is None and len(time_candidates) > 1:
        parser.error(f"Multiple possible time columns found {time_candidates}; choose --time-column explicitly.")
    if group_column and group_column not in columns:
        parser.error(f"Group column not in CSV: {group_column}")
    if time_column and time_column not in columns:
        parser.error(f"Time column not in CSV: {time_column}")
    return group_column, time_column


def _group_shuffle_splits(data: pd.DataFrame, label: pd.Series, groups: pd.Series, row_ids):
    if groups.nunique() < 8:
        raise ValueError("Need at least eight distinct fingerprint groups for group-aware splits.")
    first = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_val_pos, test_pos = next(first.split(data, label, groups))
    train_val_ids = row_ids[train_val_pos]
    test_ids = row_ids[test_pos]
    second = GroupShuffleSplit(n_splits=1, test_size=0.1875, random_state=42)
    train_pos, val_pos = next(second.split(data.loc[train_val_ids], label.loc[train_val_ids], groups.loc[train_val_ids]))
    train_ids = train_val_ids[train_pos]
    validation_ids = train_val_ids[val_pos]
    return {"train": train_ids, "validation": validation_ids, "test": test_ids}


def split_indices(
    data: pd.DataFrame,
    label: pd.Series,
    group_column: str | None,
    time_column: str | None,
    *,
    fingerprint_columns: list[str] | None = None,
):
    row_ids = data.index.to_numpy()
    groups = fingerprint_groups(data, fingerprint_columns) if fingerprint_columns else None
    if groups is not None:
        splits = _group_shuffle_splits(data, label, groups, row_ids)
    elif group_column:
        groups = data[group_column].fillna("__MISSING_GROUP__")
        splits = _group_shuffle_splits(data, label, groups, row_ids)
    elif time_column:
        times = pd.to_datetime(data[time_column], errors="coerce", utc=True)
        if times.isna().any():
            raise ValueError(f"Time column {time_column} contains unparseable values.")
        ordered = data.assign(_split_time=times).sort_values("_split_time").index.to_numpy()
        test_start = max(1, int(len(ordered) * 0.8))
        train_val_ids, test_ids = ordered[:test_start], ordered[test_start:]
        validation_start = max(1, int(len(train_val_ids) * 0.8125))
        train_ids, validation_ids = train_val_ids[:validation_start], train_val_ids[validation_start:]
        splits = {"train": train_ids, "validation": validation_ids, "test": test_ids}
    else:
        train_val_ids, test_ids = train_test_split(row_ids, test_size=0.2, random_state=42, stratify=label)
        train_ids, validation_ids = train_test_split(
            train_val_ids, test_size=0.1875, random_state=42,
            stratify=label.loc[train_val_ids],
        )
        splits = {"train": train_ids, "validation": validation_ids, "test": test_ids}

    for name, ids in splits.items():
        if len(ids) == 0 or label.loc[ids].nunique() < 2:
            raise ValueError(f"{name} split does not contain both label classes; review group/time split settings.")
    if groups is not None:
        partitions = {name: set(groups.loc[ids].astype(str)) for name, ids in splits.items()}
        if any(partitions[left] & partitions[right] for left, right in (("train", "validation"), ("train", "test"), ("validation", "test"))):
            raise AssertionError("Fingerprint group leaked across train/validation/test splits.")
    return splits
