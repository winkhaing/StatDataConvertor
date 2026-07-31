from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .models import Dataset, DatasetMetadata


PACKAGE_VERSION = 1


def _encode_scalar(value: Any) -> dict[str, Any]:
    if value is None or value is pd.NA:
        return {"type": "null", "value": None}
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        missing = False
    if isinstance(missing, (bool, np.bool_)) and missing:
        return {"type": "null", "value": None}
    if isinstance(value, (np.bool_, bool)):
        return {"type": "boolean", "value": bool(value)}
    if isinstance(value, (np.integer, int)):
        return {"type": "integer", "value": int(value)}
    if isinstance(value, (np.floating, float)):
        return {"type": "number", "value": float(value)}
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return {"type": "datetime", "value": pd.Timestamp(value).isoformat()}
    return {"type": "string", "value": str(value)}


def _decode_scalar(value: dict[str, Any]) -> Any:
    kind = value.get("type")
    raw = value.get("value")
    if kind == "null":
        return None
    if kind == "boolean":
        return bool(raw)
    if kind == "integer":
        return int(raw)
    if kind == "number":
        return float(raw)
    if kind == "datetime":
        return pd.Timestamp(raw)
    return str(raw)


def _encode_metadata(metadata: DatasetMetadata) -> dict[str, Any]:
    return {
        "dataset_label": metadata.dataset_label,
        "table_name": metadata.table_name,
        "source": metadata.source,
        "updated": metadata.updated,
        "column_labels": metadata.column_labels,
        "value_labels": {
            column: [
                {"value": _encode_scalar(value), "label": label}
                for value, label in labels.items()
            ]
            for column, labels in metadata.value_labels.items()
        },
        "missing_values": {
            column: [_encode_scalar(value) for value in values]
            for column, values in metadata.missing_values.items()
        },
        "missing_ranges": {
            column: [
                (
                    {
                        "lo": _encode_scalar(value["lo"]),
                        "hi": _encode_scalar(value["hi"]),
                    }
                    if isinstance(value, dict)
                    and "lo" in value
                    and "hi" in value
                    else _encode_scalar(value)
                )
                for value in values
            ]
            for column, values in metadata.missing_ranges.items()
        },
        "formats": metadata.formats,
        "measures": metadata.measures,
        "notes": metadata.notes,
        "extra": metadata.extra,
    }


def _decode_metadata(value: dict[str, Any]) -> DatasetMetadata:
    missing_ranges: dict[str, list[Any]] = {}
    for column, ranges in value.get("missing_ranges", {}).items():
        missing_ranges[column] = [
            (
                {
                    "lo": _decode_scalar(item["lo"]),
                    "hi": _decode_scalar(item["hi"]),
                }
                if isinstance(item, dict) and "lo" in item and "hi" in item
                else _decode_scalar(item)
            )
            for item in ranges
        ]
    return DatasetMetadata(
        dataset_label=value.get("dataset_label"),
        table_name=value.get("table_name"),
        source=value.get("source"),
        updated=value.get("updated"),
        column_labels=dict(value.get("column_labels") or {}),
        value_labels={
            column: {
                _decode_scalar(item["value"]): str(item["label"])
                for item in labels
            }
            for column, labels in (value.get("value_labels") or {}).items()
        },
        missing_values={
            column: [_decode_scalar(item) for item in values]
            for column, values in (value.get("missing_values") or {}).items()
        },
        missing_ranges=missing_ranges,
        formats=dict(value.get("formats") or {}),
        measures=dict(value.get("measures") or {}),
        notes=list(value.get("notes") or []),
        extra=dict(value.get("extra") or {}),
    )


def write_dataset_package(dataset: Dataset, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    data_path = directory / "data.json"
    metadata_path = directory / "metadata.json"
    manifest_path = directory / "manifest.json"
    dataset.frame.to_json(
        data_path,
        orient="table",
        date_format="iso",
        index=False,
        force_ascii=False,
    )
    metadata_path.write_text(
        json.dumps(
            _encode_metadata(dataset.metadata),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "package_version": PACKAGE_VERSION,
                "data": "data.json",
                "metadata": "metadata.json",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def read_dataset_package(directory: Path) -> Dataset:
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("The bridge did not produce a dataset package manifest.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("package_version") != PACKAGE_VERSION:
        raise ValueError(
            f"Unsupported dataset package version: {manifest.get('package_version')!r}."
        )
    data_path = directory / str(manifest.get("data", "data.json"))
    metadata_path = directory / str(manifest.get("metadata", "metadata.json"))
    frame = pd.read_json(data_path, orient="table")
    metadata = _decode_metadata(
        json.loads(metadata_path.read_text(encoding="utf-8"))
    )
    return Dataset(frame=frame, metadata=metadata)
