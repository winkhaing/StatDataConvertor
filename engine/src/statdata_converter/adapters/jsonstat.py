from __future__ import annotations

import itertools
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from ..models import Dataset, DatasetMetadata
from ..report import ConversionReport
from .base import Adapter, AdapterError, FormatCapability


def _ordered_codes(index: Any) -> list[str]:
    if isinstance(index, list):
        return [str(code) for code in index]
    if isinstance(index, dict):
        return [
            str(code)
            for code, _ in sorted(index.items(), key=lambda item: item[1])
        ]
    raise AdapterError("A JSON-stat category index must be an array or object.")


def _dense_value(value: Any, offset: int) -> Any:
    if isinstance(value, list):
        return value[offset] if offset < len(value) else None
    if isinstance(value, dict):
        return value.get(str(offset), value.get(offset))
    raise AdapterError("JSON-stat value must be a dense array or sparse object.")


def _json_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _dimension_code(value: Any) -> str:
    return "__missing__" if pd.isna(value) else str(value)


class JsonStatAdapter(Adapter):
    capability = FormatCapability(
        id="jsonstat",
        family="JSON-stat",
        label="JSON-stat dataset",
        extensions=(".json", ".jsonstat"),
        can_read=True,
        can_write=True,
        trust="experimental",
        detail="Reads v1/v2 datasets and writes JSON-stat 2.0 cube datasets.",
    )
    metadata_features = frozenset(
        {"dataset_label", "source", "updated", "column_labels"}
    )

    def read(
        self,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> Dataset:
        del options
        with path.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)

        if payload.get("class") not in (None, "dataset"):
            raise AdapterError("Only JSON-stat dataset responses are supported.")
        ids = payload.get("id")
        sizes = payload.get("size")
        dimensions = payload.get("dimension")
        if not isinstance(ids, list) or not isinstance(sizes, list):
            raise AdapterError("JSON-stat dataset is missing id or size.")
        if not isinstance(dimensions, dict) or len(ids) != len(sizes):
            raise AdapterError("JSON-stat dimensions do not match id and size.")

        codes_by_dimension: list[list[str]] = []
        column_labels: dict[str, str] = {}
        category_labels: dict[str, dict[str, str]] = {}
        for dimension_id, expected_size in zip(ids, sizes, strict=True):
            dimension = dimensions.get(dimension_id, {})
            category = dimension.get("category", {})
            codes = _ordered_codes(category.get("index"))
            if len(codes) != expected_size:
                raise AdapterError(
                    f"Dimension {dimension_id!r} size does not match its index."
                )
            codes_by_dimension.append(codes)
            if dimension.get("label"):
                column_labels[str(dimension_id)] = str(dimension["label"])
            category_labels[str(dimension_id)] = {
                str(code): str(label)
                for code, label in category.get("label", {}).items()
            }

        rows: list[dict[str, Any]] = []
        status_payload = payload.get("status")
        for offset, coordinate in enumerate(itertools.product(*codes_by_dimension)):
            row = {
                str(dimension_id): code
                for dimension_id, code in zip(ids, coordinate, strict=True)
            }
            row["value"] = _dense_value(payload.get("value"), offset)
            if status_payload is not None:
                row["status"] = _dense_value(status_payload, offset)
            rows.append(row)

        report.add(
            "info",
            "jsonstat.cube_flattened",
            "The JSON-stat cube was flattened into one row per coordinate.",
        )
        metadata = DatasetMetadata(
            dataset_label=payload.get("label"),
            source=payload.get("source"),
            updated=payload.get("updated"),
            column_labels=column_labels,
            value_labels=category_labels,
            extra={
                "jsonstat": {
                    "ids": [str(item) for item in ids],
                    "dimension": dimensions,
                    "value_column": "value",
                    "status_column": "status" if status_payload is not None else None,
                }
            },
        )
        return Dataset(frame=pd.DataFrame(rows), metadata=metadata)

    def write(
        self,
        dataset: Dataset,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> None:
        frame = dataset.frame
        preserved = dataset.metadata.extra.get("jsonstat", {})
        value_column = options.get("value_column") or preserved.get("value_column")
        if not value_column:
            numeric_columns = list(frame.select_dtypes(include="number").columns)
            if not numeric_columns:
                raise AdapterError(
                    "Writing JSON-stat requires a numeric value column."
                )
            value_column = str(numeric_columns[-1])
            report.add(
                "warning",
                "jsonstat.value_column_inferred",
                f"{value_column!r} was inferred as the JSON-stat value column.",
                [value_column],
            )
        if value_column not in frame.columns:
            raise AdapterError(f"Value column {value_column!r} does not exist.")

        status_column = options.get("status_column") or preserved.get("status_column")
        dimensions = options.get("dimensions") or preserved.get("ids")
        if not dimensions:
            excluded = {value_column, status_column}
            dimensions = [
                str(column) for column in frame.columns if column not in excluded
            ]
            report.add(
                "warning",
                "jsonstat.dimensions_inferred",
                "All non-value columns were inferred as JSON-stat dimensions.",
                dimensions,
            )
        dimensions = [str(item) for item in dimensions]
        if not dimensions:
            raise AdapterError("Writing JSON-stat requires at least one dimension.")

        missing = [
            column
            for column in [*dimensions, value_column]
            if column not in frame.columns
        ]
        if missing:
            raise AdapterError(f"Columns do not exist: {', '.join(missing)}")
        if frame.duplicated(subset=dimensions).any():
            raise AdapterError(
                "JSON-stat dimensions do not uniquely identify rows. "
                "Choose more dimensions or aggregate the data first."
            )

        codes_by_dimension: dict[str, list[str]] = {}
        dimension_payload: dict[str, Any] = {}
        for dimension_id in dimensions:
            series = frame[dimension_id]
            raw_values = list(pd.unique(series))
            codes = [_dimension_code(value) for value in raw_values]
            if len(set(codes)) != len(codes):
                raise AdapterError(
                    f"Dimension {dimension_id!r} contains values that collapse "
                    "to the same JSON-stat category code."
                )
            if series.isna().any():
                report.add(
                    "warning",
                    "jsonstat.missing_dimension_category",
                    "Missing dimension values were represented by the "
                    "'__missing__' category.",
                    [dimension_id],
                )
            codes_by_dimension[dimension_id] = codes
            labels = dataset.metadata.value_labels.get(dimension_id, {})
            category: dict[str, Any] = {
                "index": {code: position for position, code in enumerate(codes)}
            }
            category_labels = {
                code: str(
                    labels.get(
                        value,
                        labels.get(
                            code,
                            "Missing" if pd.isna(value) else code,
                        ),
                    )
                )
                for code, value in zip(codes, raw_values, strict=True)
            }
            if any(label != code for code, label in category_labels.items()):
                category["label"] = category_labels
            dimension_payload[dimension_id] = {
                "label": dataset.metadata.column_labels.get(
                    dimension_id,
                    dimension_id,
                ),
                "category": category,
            }

        lookup = {
            tuple(_dimension_code(row[dimension]) for dimension in dimensions): row
            for _, row in frame.iterrows()
        }
        values: list[Any] = []
        statuses: list[Any] = []
        for coordinate in itertools.product(
            *(codes_by_dimension[item] for item in dimensions)
        ):
            row = lookup.get(coordinate)
            values.append(None if row is None else _json_value(row[value_column]))
            if status_column:
                statuses.append(
                    None if row is None else _json_value(row[status_column])
                )

        payload: dict[str, Any] = {
            "version": "2.0",
            "class": "dataset",
            "id": dimensions,
            "size": [len(codes_by_dimension[item]) for item in dimensions],
            "dimension": dimension_payload,
            "value": values,
        }
        for key, value in (
            ("label", dataset.metadata.dataset_label),
            ("source", dataset.metadata.source),
            ("updated", dataset.metadata.updated),
        ):
            if value:
                payload[key] = value
        if status_column:
            payload["status"] = statuses
        with path.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
