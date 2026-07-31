import shutil

import pandas as pd
import pytest

from statdata_converter.service import ConversionService


def test_reads_legacy_minitab_portable_with_local_r(tmp_path) -> None:
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not installed")
    source = tmp_path / "sample.mtp"
    destination = tmp_path / "sample.csv"
    header = (
        "Minitab Portable Worksheet P1.1             "
        "1994 522 Release 9.1               .\n"
    )
    record = f"%{3:7d}{1:7d}{3:7d}{0:7d} {'score':<8}.\n"
    source.write_text(header + record + " 1.25 2.5 5.0 .\n", encoding="ascii")

    result = ConversionService().convert(source, destination)

    assert pd.read_csv(destination).to_dict(orient="list") == {
        "score": [1.25, 2.5, 5.0]
    }
    assert any(
        change["code"] == "minitab.portable_metadata_limited"
        for change in result["report"]["changes"]
    )
