from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import pandas as pd

from ..models import Dataset
from ..report import ConversionReport
from .base import Adapter, AdapterError, FormatCapability


def _sas_name(value: str, index: int) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", value).strip("_")
    if not normalized or not normalized[0].isalpha():
        normalized = f"V{index}_{normalized}"
    return normalized[:32]


class SasProgramAdapter(Adapter):
    capability = FormatCapability(
        id="sas_program",
        family="SAS",
        label="SAS program + CSV data",
        extensions=(".sas",),
        can_read=False,
        can_write=True,
        trust="experimental",
        detail=(
            "Writes a portable SAS DATA-step program plus a UTF-8 CSV sidecar. "
            "Reading arbitrary SAS programs is not claimed."
        ),
    )
    metadata_features = frozenset({"column_labels", "formats"})

    def read(
        self,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> Dataset:
        del path, options, report
        raise AdapterError("Reading arbitrary SAS programs is not supported.")

    def write(
        self,
        dataset: Dataset,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> None:
        frame = dataset.frame.copy()
        original_columns = [str(column) for column in frame.columns]
        sas_columns = [
            _sas_name(column, index)
            for index, column in enumerate(original_columns, start=1)
        ]
        if len({name.lower() for name in sas_columns}) != len(sas_columns):
            raise AdapterError("Column names collide after applying SAS naming rules.")
        frame.columns = sas_columns
        csv_path = path.with_suffix(".csv")
        if csv_path.exists() and not bool(options.get("replace", False)):
            raise FileExistsError(f"The SAS data sidecar already exists: {csv_path}")
        frame.to_csv(
            csv_path,
            index=False,
            encoding="utf-8",
            quoting=csv.QUOTE_MINIMAL,
            date_format="%Y-%m-%dT%H:%M:%S.%f",
        )

        lengths: dict[str, int] = {}
        temporal_kinds: dict[str, str] = {}
        temporal_by_original = dataset.temporal
        for name in sas_columns:
            original = original_columns[sas_columns.index(name)]
            profile = temporal_by_original.get(original)
            if profile:
                temporal_kinds[name] = profile.kind
                continue
            if not (
                pd.api.types.is_numeric_dtype(frame[name])
                or pd.api.types.is_datetime64_any_dtype(frame[name])
            ):
                populated = frame[name].dropna().astype(str)
                lengths[name] = max(
                    1,
                    min(
                        32767,
                        max(
                            (len(value.encode("utf-8")) for value in populated),
                            default=1,
                        ),
                    ),
                )
        member = _sas_name(str(options.get("member", path.stem)), 1)
        lines = [
            "/* Generated locally by StatData Converter. */",
            "options validvarname=any;",
            "filename statcsv '"
            + str(csv_path).replace("'", "''")
            + "' encoding='utf-8';",
            f"data work.{member};",
        ]
        if lengths:
            lines.append(
                "  length "
                + " ".join(f"{name} ${lengths[name]}" for name in lengths)
                + ";"
            )
        for name, kind in temporal_kinds.items():
            if kind == "date":
                lines.append(f"  informat {name} e8601da.; format {name} e8601da.;")
            elif kind == "time":
                lines.append(f"  informat {name} e8601tm.; format {name} e8601tm15.6;")
            elif kind == "datetime":
                lines.append(f"  informat {name} e8601dt.; format {name} e8601dt26.6;")
        for original, name in zip(original_columns, sas_columns, strict=True):
            label = dataset.metadata.column_labels.get(original)
            if label:
                escaped = label.replace("'", "''")
                lines.append(f"  label {name}='{escaped}';")
            display = dataset.metadata.formats.get(original)
            if display:
                lines.append(f"  format {name} {display};")
        lines.extend(
            [
                "  infile statcsv dsd dlm=',' firstobs=2 truncover lrecl=1048576;",
                "  input",
            ]
        )
        for name in sas_columns:
            if name in lengths:
                lines.append(f"    {name} :$32767.")
            elif name in temporal_kinds:
                informat = {
                    "date": "e8601da.",
                    "time": "e8601tm.",
                    "datetime": "e8601dt.",
                }.get(temporal_kinds[name], "best32.")
                lines.append(f"    {name} :{informat}")
            else:
                lines.append(f"    {name} :best32.")
        lines.extend(["  ;", "run;", ""])
        path.write_text("\n".join(lines), encoding="utf-8")

        renamed = [
            f"{original} → {name}"
            for original, name in zip(original_columns, sas_columns, strict=True)
            if original != name
        ]
        if renamed:
            report.add(
                "warning",
                "sas.program_columns_renamed",
                "SAS-compatible variable names were generated: " + ", ".join(renamed),
                original_columns,
            )
        report.add(
            "info",
            "sas.program_csv_sidecar",
            f"The generated SAS program reads the UTF-8 sidecar {csv_path.name}.",
        )
        report.add(
            "warning",
            "sas.program_reader_unverified",
            "The generated DATA step must be validated in the destination SAS release.",
        )
