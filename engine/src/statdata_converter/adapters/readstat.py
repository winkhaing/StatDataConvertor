from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from ..models import Dataset, DatasetMetadata
from ..report import ConversionReport
from .base import Adapter, AdapterError, FormatCapability

try:
    import pyreadstat
except ImportError:  # pragma: no cover - exercised by capability checks
    pyreadstat = None


Reader = Callable[..., Any]


def _safe_variable_names(
    columns: list[Any],
    *,
    maximum_length: int,
) -> dict[Any, str]:
    result: dict[Any, str] = {}
    used: set[str] = set()
    reserved = {"_all", "_n", "if", "in", "using", "with", "by"}
    for column in columns:
        original = str(column)
        ascii_name = unicodedata.normalize("NFKD", original).encode(
            "ascii",
            errors="ignore",
        ).decode("ascii")
        base = re.sub(r"[^A-Za-z0-9_]", "_", ascii_name).strip("_")
        if not base:
            base = "variable"
        if not re.match(r"[A-Za-z_]", base):
            base = f"v_{base}"
        if base.lower() in reserved:
            base = f"v_{base}"
        base = base[:maximum_length]
        candidate = base
        suffix = 2
        while candidate.lower() in used:
            addition = f"_{suffix}"
            candidate = f"{base[: maximum_length - len(addition)]}{addition}"
            suffix += 1
        used.add(candidate.lower())
        result[column] = candidate
    return result


def _renamed_mapping(
    value: dict[str, Any],
    names: dict[Any, str],
) -> dict[str, Any]:
    return {
        names.get(column, names.get(str(column), str(column))): item
        for column, item in value.items()
    }


def _prepare_for_write(
    dataset: Dataset,
    *,
    maximum_length: int,
    report: ConversionReport,
) -> tuple[pd.DataFrame, dict[Any, str]]:
    names = _safe_variable_names(
        list(dataset.frame.columns),
        maximum_length=maximum_length,
    )
    for original, replacement in names.items():
        if str(original) == replacement:
            continue
        report.add(
            "warning",
            "column.renamed_for_destination",
            f"Column {str(original)!r} was renamed to {replacement!r} to satisfy "
            "the destination format's variable-name rules.",
            [str(original)],
        )
    return dataset.frame.rename(columns=names), names


def _metadata(meta: Any, source_format: str) -> DatasetMetadata:
    return DatasetMetadata(
        dataset_label=getattr(meta, "file_label", None),
        table_name=getattr(meta, "table_name", None),
        column_labels=dict(
            getattr(meta, "column_names_to_labels", None) or {}
        ),
        value_labels=dict(getattr(meta, "variable_value_labels", None) or {}),
        missing_values=dict(getattr(meta, "missing_user_values", None) or {}),
        missing_ranges=dict(getattr(meta, "missing_ranges", None) or {}),
        formats=dict(getattr(meta, "original_variable_types", None) or {}),
        measures=dict(getattr(meta, "variable_measure", None) or {}),
        notes=list(getattr(meta, "notes", None) or []),
        extra={"native_format": source_format},
    )


class ReadStatAdapter(Adapter):
    def __init__(self, format_id: str):
        available = pyreadstat is not None
        configurations = {
            "stata": FormatCapability(
                id="stata",
                family="Stata",
                label="Stata data file",
                extensions=(".dta",),
                can_read=available,
                can_write=available,
                trust="experimental",
                availability="available" if available else "dependency_missing",
                detail="All ReadStat-supported generations; output version is selectable.",
                requires=("pyreadstat",),
            ),
            "spss_data": FormatCapability(
                id="spss_data",
                family="IBM SPSS",
                label="SPSS data file",
                extensions=(".sav", ".zsav"),
                can_read=available,
                can_write=available,
                trust="experimental",
                availability="available" if available else "dependency_missing",
                detail="Compressed and uncompressed SPSS system files.",
                requires=("pyreadstat",),
            ),
            "spss_portable": FormatCapability(
                id="spss_portable",
                family="IBM SPSS",
                label="SPSS portable file",
                extensions=(".por",),
                can_read=available,
                can_write=False,
                trust="experimental",
                availability="available" if available else "dependency_missing",
                detail="Portable files are read-only in the open core.",
                requires=("pyreadstat",),
            ),
            "sas_data": FormatCapability(
                id="sas_data",
                family="SAS",
                label="SAS data file",
                extensions=(".sas7bdat",),
                can_read=available,
                can_write=False,
                trust="experimental",
                availability="available" if available else "dependency_missing",
                detail="Native SAS data is read-only; writing requires a vendor bridge.",
                requires=("pyreadstat",),
            ),
            "sas_xport": FormatCapability(
                id="sas_xport",
                family="SAS",
                label="SAS XPORT",
                extensions=(".xpt",),
                can_read=available,
                can_write=available,
                trust="experimental",
                availability="available" if available else "dependency_missing",
                detail="SAS transport v5 and v8.",
                requires=("pyreadstat",),
            ),
        }
        self.capability = configurations[format_id]
        self.format_id = format_id
        features = {
            "stata": {
                "dataset_label",
                "column_labels",
                "value_labels",
                "missing_values",
                "formats",
            },
            "spss_data": {
                "dataset_label",
                "column_labels",
                "value_labels",
                "missing_ranges",
                "formats",
                "measures",
                "notes",
            },
            "sas_xport": {
                "dataset_label",
                "table_name",
                "column_labels",
                "formats",
            },
        }
        self.metadata_features = frozenset(features.get(format_id, set()))

    def _require_library(self) -> Any:
        if pyreadstat is None:
            raise AdapterError(
                "This adapter requires the optional pyreadstat dependency."
            )
        return pyreadstat

    def read(
        self,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> Dataset:
        library = self._require_library()
        readers: dict[str, Reader] = {
            "stata": library.read_dta,
            "spss_data": library.read_sav,
            "spss_portable": library.read_por,
            "sas_data": library.read_sas7bdat,
            "sas_xport": library.read_xport,
        }
        kwargs: dict[str, Any] = {}
        if options.get("encoding"):
            kwargs["encoding"] = options["encoding"]
        if self.format_id in {"stata", "spss_data", "sas_data"}:
            kwargs["user_missing"] = True
        if self.format_id == "sas_data" and options.get("catalog_file"):
            kwargs["catalog_file"] = options["catalog_file"]
        frame, meta = readers[self.format_id](str(path), **kwargs)
        report.add(
            "info",
            "readstat.open_parser",
            "The file was decoded with the open-source ReadStat parser.",
        )
        return Dataset(frame=frame, metadata=_metadata(meta, self.format_id))

    def analyze_metadata(
        self,
        dataset: Dataset,
        report: ConversionReport,
    ) -> None:
        super().analyze_metadata(dataset, report)
        source_format = dataset.metadata.extra.get("native_format")
        if (
            dataset.metadata.formats
            and source_format
            and source_format != self.format_id
        ):
            report.add(
                "warning",
                "metadata_transformed.display_formats",
                "Source display-format codes use a different software syntax "
                "and were not copied verbatim.",
                list(dataset.metadata.formats),
            )

    def write(
        self,
        dataset: Dataset,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> None:
        library = self._require_library()
        metadata = dataset.metadata
        maximum_length = {
            "stata": 32,
            "spss_data": 64,
            "sas_xport": (
                8 if int(options.get("xport_version", 8)) == 5 else 32
            ),
        }.get(self.format_id, 64)
        frame, names = _prepare_for_write(
            dataset,
            maximum_length=maximum_length,
            report=report,
        )
        column_labels = _renamed_mapping(metadata.column_labels, names)
        for original, replacement in names.items():
            if str(original) != replacement and replacement not in column_labels:
                column_labels[replacement] = str(original)
        value_labels = _renamed_mapping(metadata.value_labels, names)
        missing_values = _renamed_mapping(metadata.missing_values, names)
        missing_ranges = _renamed_mapping(metadata.missing_ranges, names)
        measures = _renamed_mapping(metadata.measures, names)
        native_formats = (
            _renamed_mapping(metadata.formats, names)
            if metadata.extra.get("native_format") in {None, self.format_id}
            else None
        )
        common = {
            "file_label": metadata.dataset_label or "",
            "column_labels": column_labels or None,
        }
        if self.format_id == "stata":
            library.write_dta(
                frame,
                str(path),
                version=int(options.get("stata_version", 15)),
                variable_value_labels=value_labels or None,
                missing_user_values=missing_values or None,
                variable_format=native_formats or None,
                **common,
            )
        elif self.format_id == "spss_data":
            compress = path.suffix.lower() == ".zsav"
            library.write_sav(
                frame,
                str(path),
                compress=compress,
                variable_value_labels=value_labels or None,
                missing_ranges=missing_ranges or None,
                variable_measure=measures or None,
                variable_format=native_formats or None,
                note=metadata.notes or None,
                **common,
            )
        elif self.format_id == "sas_xport":
            library.write_xport(
                frame,
                str(path),
                file_format_version=int(options.get("xport_version", 8)),
                table_name=metadata.table_name or "DATASET",
                variable_format=native_formats or None,
                **common,
            )
            if metadata.value_labels:
                report.add(
                    "warning",
                    "sas_xport.value_labels_external",
                    "SAS value labels require a separate format catalog and were not embedded.",
                )
        else:
            raise AdapterError(
                f"{self.capability.label} writing is not available in the open core."
            )
