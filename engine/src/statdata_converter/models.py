from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(frozen=True, slots=True)
class TemporalColumnProfile:
    column: str
    kind: str
    precision: str
    timezone: str | None
    missing_count: int
    storage_dtype: str
    native_format: str | None = None


@dataclass(slots=True)
class DatasetMetadata:
    dataset_label: str | None = None
    table_name: str | None = None
    source: str | None = None
    updated: str | None = None
    column_labels: dict[str, str] = field(default_factory=dict)
    value_labels: dict[str, dict[Any, str]] = field(default_factory=dict)
    missing_values: dict[str, list[Any]] = field(default_factory=dict)
    missing_ranges: dict[str, list[Any]] = field(default_factory=dict)
    formats: dict[str, str] = field(default_factory=dict)
    measures: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def populated_features(self) -> set[str]:
        features: set[str] = set()
        for name in (
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
        ):
            if getattr(self, name):
                features.add(name)
        return features


@dataclass(slots=True)
class Dataset:
    frame: pd.DataFrame
    metadata: DatasetMetadata = field(default_factory=DatasetMetadata)
    temporal: dict[str, TemporalColumnProfile] = field(default_factory=dict)
