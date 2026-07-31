from __future__ import annotations

import json
import math
from dataclasses import asdict
from datetime import date, datetime
from numbers import Number
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .models import Dataset, DatasetMetadata


def _json_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if math.isnan(float(value)):
            return None
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, dict):
        return {
            str(_json_value(key)): _json_value(item)
            for key, item in sorted(value.items(), key=lambda entry: str(entry[0]))
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    return str(value)


def _is_missing(value: Any) -> bool:
    if value is None or value is pd.NA:
        return True
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(result) if isinstance(result, (bool, np.bool_)) else False


def _values_equal(expected: Any, actual: Any) -> bool:
    if _is_missing(expected) and _is_missing(actual):
        return True
    if _is_missing(expected) or _is_missing(actual):
        return False
    if (
        isinstance(expected, Number)
        and not isinstance(expected, (bool, np.bool_))
        and isinstance(actual, Number)
        and not isinstance(actual, (bool, np.bool_))
    ):
        return bool(
            np.isclose(
                float(expected),
                float(actual),
                rtol=1e-9,
                atol=1e-12,
                equal_nan=True,
            )
        )
    if isinstance(expected, (pd.Timestamp, datetime, date)) or isinstance(
        actual, (pd.Timestamp, datetime, date)
    ):
        try:
            return pd.Timestamp(expected) == pd.Timestamp(actual)
        except (TypeError, ValueError):
            return False
    return type(expected) is type(actual) and expected == actual


def compare_datasets(expected: Dataset, actual: Dataset) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    expected_columns = [str(column) for column in expected.frame.columns]
    actual_columns = [str(column) for column in actual.frame.columns]
    if expected_columns != actual_columns:
        issues.append(
            {
                "severity": "error",
                "scope": "data",
                "code": "data.columns_changed",
                "message": "Column names or their order changed during round trip.",
                "expected": expected_columns,
                "actual": actual_columns,
            }
        )
    if len(expected.frame.index) != len(actual.frame.index):
        issues.append(
            {
                "severity": "error",
                "scope": "data",
                "code": "data.row_count_changed",
                "message": "The number of rows changed during round trip.",
                "expected": len(expected.frame.index),
                "actual": len(actual.frame.index),
            }
        )

    shared_columns = [
        column
        for column in expected.frame.columns
        if column in actual.frame.columns
    ]
    shared_rows = min(len(expected.frame.index), len(actual.frame.index))
    for column in shared_columns:
        mismatches: list[dict[str, Any]] = []
        mismatch_count = 0
        expected_values = expected.frame[column].iloc[:shared_rows].tolist()
        actual_values = actual.frame[column].iloc[:shared_rows].tolist()
        for index, (expected_value, actual_value) in enumerate(
            zip(expected_values, actual_values, strict=True)
        ):
            if _values_equal(expected_value, actual_value):
                continue
            mismatch_count += 1
            if len(mismatches) < 5:
                mismatches.append(
                    {
                        "row": index + 1,
                        "expected": _json_value(expected_value),
                        "actual": _json_value(actual_value),
                    }
                )
        if mismatch_count:
            issues.append(
                {
                    "severity": "error",
                    "scope": "data",
                    "code": "data.values_changed",
                    "message": (
                        f"{mismatch_count} value(s) changed in column {column!s}."
                    ),
                    "column": str(column),
                    "mismatch_count": mismatch_count,
                    "samples": mismatches,
                }
            )

    metadata_fields = (
        "dataset_label",
        "table_name",
        "source",
        "updated",
        "column_labels",
        "value_labels",
        "missing_values",
        "missing_ranges",
        "formats",
        "measures",
        "notes",
    )
    for field_name in metadata_fields:
        expected_value = getattr(expected.metadata, field_name)
        if not expected_value:
            continue
        actual_value = getattr(actual.metadata, field_name)
        normalized_expected = _json_value(expected_value)
        normalized_actual = _json_value(actual_value)
        if normalized_expected != normalized_actual:
            issues.append(
                {
                    "severity": "warning",
                    "scope": "metadata",
                    "code": f"metadata.{field_name}_changed",
                    "message": (
                        f"{field_name.replace('_', ' ').capitalize()} was not "
                        "preserved exactly during round trip."
                    ),
                    "expected": normalized_expected,
                    "actual": normalized_actual,
                }
            )

    data_issues = sum(issue["scope"] == "data" for issue in issues)
    metadata_issues = sum(issue["scope"] == "metadata" for issue in issues)
    return {
        "data_equivalent": data_issues == 0,
        "metadata_equivalent": metadata_issues == 0,
        "issues": issues,
        "summary": {
            "data_issues": data_issues,
            "metadata_issues": metadata_issues,
        },
    }


def metadata_to_debug_dict(metadata: DatasetMetadata) -> dict[str, Any]:
    return _json_value(asdict(metadata))


def write_validation_result(path: Path, result: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
