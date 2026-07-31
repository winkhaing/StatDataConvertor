from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import Dataset, DatasetMetadata
from ..report import ConversionReport
from ._jmp_reader import JmpReadError, read_jmp
from .base import Adapter, AdapterError, FormatCapability


class JmpAdapter(Adapter):
    capability = FormatCapability(
        id="jmp",
        family="JMP",
        label="JMP data table",
        extensions=(".jmp",),
        can_read=True,
        can_write=False,
        trust="experimental",
        availability="available",
        detail=(
            "License-free native JMP reading is built in. Native JMP writing "
            "is unavailable until an open writer is independently verified."
        ),
    )
    metadata_features = frozenset()

    def read(
        self,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> Dataset:
        del options
        try:
            result = read_jmp(path)
        except JmpReadError as exc:
            raise AdapterError(str(exc)) from exc
        report.add(
            "info",
            "jmp.native_open_reader",
            "The file was decoded locally by the built-in open-source JMP reader; "
            "JMP software was not used.",
        )
        report.add(
            "warning",
            "jmp.metadata_not_extracted",
            "The native reader currently extracts table values, column names, "
            "dates, times, durations, and storage types. JMP formulas, column "
            "properties, table scripts, value labels, and modeling metadata "
            "are not yet extracted.",
        )
        for code, message, columns in result.warnings:
            report.add("warning", code, message, columns)
        return Dataset(
            frame=result.frame,
            metadata=DatasetMetadata(
                table_name=path.stem,
                updated=(
                    result.info.saved_at.isoformat()
                    if result.info.saved_at
                    else None
                ),
                formats=result.formats,
                extra={
                    "native_format": "jmp",
                    "jmp_version": result.info.version,
                    "jmp_build": result.info.build_string,
                    "jmp_reader": "StatData native Python / JMPReader.jl-derived",
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
        del dataset, path, options, report
        raise AdapterError(
            "Native JMP writing is not available without a verified open-source "
            "writer. Choose another output format."
        )
