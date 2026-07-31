from __future__ import annotations

import gzip
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from ..models import Dataset, DatasetMetadata
from ..report import ConversionReport
from ._eviews_reader import read_eviews
from .base import Adapter, AdapterError, FormatCapability


def _json_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


class EViewsAdapter(Adapter):
    capability = FormatCapability(
        id="eviews_wf2",
        family="EViews",
        label="EViews open workfile",
        extensions=(".wf2",),
        can_read=True,
        can_write=True,
        trust="experimental",
        availability="available",
        detail=(
            "Reads and writes the open WF2 JSON/gzip format locally. "
            "No EViews installation is required."
        ),
    )
    metadata_features = frozenset(
        {"table_name", "dataset_label", "column_labels"}
    )

    def read(
        self,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> Dataset:
        table = read_eviews(path, options.get("page"))
        if table.page_count > 1 and options.get("page") in (None, ""):
            report.add(
                "warning",
                "eviews.page_selected",
                f"The workfile contains {table.page_count} pages; "
                f"{table.page_name!r} was selected. Set page to choose another.",
            )
        if table.omitted_objects:
            report.add(
                "warning",
                "eviews.non_series_objects_omitted",
                "EViews equations, groups, VARs, graphs, tables, and other "
                "non-series objects are outside the tabular conversion model.",
                table.omitted_objects,
            )
        if table.failed_series:
            report.add(
                "warning",
                "eviews.series_not_read",
                "Some EViews series could not be decoded or did not match the "
                "selected page range.",
                table.failed_series,
            )
        if table.frequency not in {0, 1, 4, 12}:
            report.add(
                "warning",
                "eviews.frequency_projected",
                "This EViews frequency is exposed with sequential observation "
                "labels in the tabular model.",
            )
        report.add(
            "info",
            "eviews.observation_labels_added",
            "EViews page observations are represented in the 'obs' column.",
            ["obs"],
        )
        return Dataset(
            frame=table.frame,
            metadata=DatasetMetadata(
                dataset_label=table.page_name,
                table_name=table.page_name,
                column_labels=table.descriptions,
                extra={
                    "native_format": "eviews",
                    "eviews_version": table.version,
                    "eviews_frequency": table.frequency,
                    "eviews_start_year": table.start_year,
                    "eviews_start_period": table.start_period,
                },
            ),
        )

    def write(
        self,
        dataset: Dataset,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> None:
        if path.suffix.lower() != ".wf2":
            raise AdapterError(
                "The open core writes EViews WF2 JSON only; binary WF1 writing "
                "is not claimed."
            )
        frame = dataset.frame
        preserved_frequency = dataset.metadata.extra.get("eviews_frequency")
        default_frequency = {
            0: "U",
            1: "A",
            4: "Q",
            12: "M",
        }.get(preserved_frequency, "U")
        frequency = str(
            options.get("frequency", default_frequency)
        ).upper()
        if frequency not in {"U", "A", "Y", "Q", "M"}:
            raise AdapterError(
                "WF2 output frequency must be U, A/Y, Q, or M."
            )
        if "start" in options:
            start = options["start"]
        elif frequency in {"A", "Y", "Q", "M"}:
            year = dataset.metadata.extra.get("eviews_start_year", 1)
            period = dataset.metadata.extra.get("eviews_start_period", 1)
            month = (
                (int(period) - 1) * 3 + 1
                if frequency == "Q"
                else int(period) if frequency == "M" else 1
            )
            start = f"{int(year):04d}-{month:02d}-01"
        else:
            start = 1
        page_name = str(
            options.get(
                "page_name",
                dataset.metadata.table_name
                or dataset.metadata.dataset_label
                or "Page1",
            )
        )
        objects: list[dict[str, Any]] = []
        observation_column = "obs" if "obs" in frame.columns else None
        for column in frame.columns:
            if column == observation_column:
                continue
            values = [_json_value(value) for value in frame[column].tolist()]
            numeric = pd.api.types.is_numeric_dtype(frame[column].dtype)
            obj: dict[str, Any] = {
                "_name": str(column),
                "_basetype": "series",
                "_type": "series_double" if numeric else "series_alpha",
                "seriesType": "numeric" if numeric else "alpha",
                "data": values,
            }
            description = dataset.metadata.column_labels.get(str(column))
            if description:
                obj["_labels"] = {"description": description}
            objects.append(obj)
        if observation_column:
            report.add(
                "info",
                "eviews.observation_column_mapped",
                "The 'obs' column was mapped to the EViews page observation "
                "axis instead of being duplicated as a series.",
                ["obs"],
            )
        payload = {
            "_pages": [
                {
                    "_name": page_name,
                    "range": len(frame.index),
                    "frequency": {"value": frequency, "start": start},
                    "_objects": objects,
                }
            ]
        }
        try:
            if bool(options.get("gzip", False)):
                with gzip.open(path, "wt", encoding="utf-8") as stream:
                    json.dump(payload, stream, ensure_ascii=False, allow_nan=False)
            else:
                with path.open("w", encoding="utf-8") as stream:
                    json.dump(
                        payload,
                        stream,
                        ensure_ascii=False,
                        allow_nan=False,
                        indent=2,
                    )
                    stream.write("\n")
        except Exception as exc:
            raise AdapterError(f"Unable to write EViews WF2 JSON: {exc}") from exc
        report.add(
            "warning",
            "eviews.wf2_minimal_profile",
            "The file uses a minimal open WF2 JSON page-and-series profile. "
            "Interoperability is experimental until validated in supported "
            "EViews releases.",
        )
        report.add(
            "warning",
            "eviews.analysis_objects_not_synthesized",
            "Equations, groups, models, graphs, tables, and workfile UI state "
            "were not synthesized.",
        )


class EViewsWf1Adapter(EViewsAdapter):
    capability = FormatCapability(
        id="eviews_wf1",
        family="EViews",
        label="EViews binary workfile",
        extensions=(".wf1",),
        can_read=True,
        can_write=False,
        trust="experimental",
        availability="available",
        detail=(
            "Reads legacy binary WF1 workfiles locally. Binary WF1 writing "
            "requires a separately installed vendor bridge."
        ),
    )

    def write(
        self,
        dataset: Dataset,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> None:
        del dataset, path, options, report
        raise AdapterError(
            "The open core does not claim binary EViews WF1 writing."
        )
