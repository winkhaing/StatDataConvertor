from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from ..models import Dataset, DatasetMetadata
from ..report import ConversionReport
from .base import Adapter, AdapterError, FormatCapability


READ_MTP_CODE = r"""
args <- commandArgs(TRUE)
input <- args[[1]]
output <- args[[2]]
objects <- foreign::read.mtp(input)
if (length(objects) == 0) stop("The worksheet contains no components.")
lengths <- vapply(objects, function(value) {
  if (is.atomic(value) && is.null(dim(value))) length(value) else 0L
}, integer(1))
row_count <- max(lengths)
if (row_count < 1) stop("The worksheet contains no tabular columns.")
keep <- lengths == row_count
selected <- objects[keep]
if (length(selected) == 0) stop("The worksheet contains no tabular columns.")
column_names <- names(selected)
if (is.null(column_names)) column_names <- rep("", length(selected))
empty <- !nzchar(column_names)
column_names[empty] <- paste0("C", which(empty))
column_names <- make.unique(column_names)
names(selected) <- column_names
frame <- as.data.frame(selected, check.names = FALSE, stringsAsFactors = FALSE)
write.csv(frame, output, row.names = FALSE, na = "", fileEncoding = "UTF-8")
cat(paste0("SELECTED\t", paste(column_names, collapse = "\t"), "\n"))
omitted <- names(objects)[!keep]
if (is.null(omitted)) omitted <- character()
if (length(omitted)) cat(paste0("OMITTED\t", paste(omitted, collapse = "\t"), "\n"))
"""


class MinitabPortableAdapter(Adapter):
    metadata_features = frozenset({"table_name"})

    def __init__(self) -> None:
        self.rscript = shutil.which("Rscript")
        available = self.rscript is not None
        self.capability = FormatCapability(
            id="minitab_portable",
            family="Minitab",
            label="Minitab Portable Worksheet",
            extensions=(".mtp",),
            can_read=available,
            can_write=False,
            trust="experimental",
            availability="available" if available else "vendor_bridge",
            detail=(
                "Reads legacy text-based MTP worksheets through the local R "
                "recommended package 'foreign'."
                if available
                else "Reading legacy MTP worksheets requires local Rscript "
                "with the recommended package 'foreign'."
            ),
            requires=("Rscript", "R package: foreign"),
        )

    def read(
        self,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> Dataset:
        del options
        if not self.rscript:
            raise AdapterError(
                "Minitab Portable conversion requires local Rscript with "
                "the recommended package 'foreign'."
            )
        with tempfile.TemporaryDirectory(prefix="statdata-mtp-") as directory:
            interchange = Path(directory) / "dataset.csv"
            completed = subprocess.run(
                [
                    self.rscript,
                    "--vanilla",
                    "-e",
                    READ_MTP_CODE,
                    str(path),
                    str(interchange),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip()
                raise AdapterError(
                    detail or "The Minitab Portable reader failed."
                )
            frame = pd.read_csv(interchange)

        omitted: list[str] = []
        for line in completed.stdout.splitlines():
            if line.startswith("OMITTED\t"):
                omitted.extend(
                    value for value in line.split("\t")[1:] if value
                )
        if omitted:
            report.add(
                "warning",
                "minitab.non_column_components_omitted",
                "Constants, matrices, or components with a different length "
                "were not projected into the output table.",
                omitted,
            )
        report.add(
            "warning",
            "minitab.portable_metadata_limited",
            "The legacy MTP reader preserves worksheet column values but does "
            "not preserve modern Minitab design objects, formulas, or settings.",
        )
        return Dataset(
            frame=frame,
            metadata=DatasetMetadata(
                table_name=path.stem,
                extra={"native_format": "minitab_portable"},
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
            "No maintained open Minitab Portable writer has been verified."
        )
