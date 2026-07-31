from pathlib import Path

import pandas as pd
import pytest

from statdata_converter.adapters._jmp_reader import JmpReadError, read_jmp
from statdata_converter.service import ConversionService


FIXTURES = Path(__file__).parent / "fixtures" / "jmp"


def test_native_jmp_reader_decodes_core_types_without_jmp() -> None:
    result = read_jmp(FIXTURES / "example1.jmp")

    assert result.frame.shape == (4, 12)
    assert result.frame["ints"].tolist() == [1, 2, 3, 4]
    assert result.frame["floats"].tolist() == [11.1, 22.2, 33.3, 44.4]
    assert result.frame["charconstwidth"].tolist() == ["a", "b", "c", "d"]
    assert result.frame["time"].tolist()[:3] == [
        pd.Timestamp("1976-04-01 21:12:00"),
        pd.Timestamp("1984-08-06 23:58:00"),
        pd.Timestamp("2003-06-02 17:00:00"),
    ]
    assert pd.isna(result.frame["time"].iloc[3])
    assert result.frame["date"].tolist()[:2] == [
        pd.Timestamp("2024-01-13"),
        pd.Timestamp("2024-01-14"),
    ]
    assert result.frame["duration"].tolist() == [2322.0, 364.0, 229.0, 0.0]
    assert result.frame["char utf8"].tolist() == [
        "ꙮꙮꙮ",
        "🚴💨",
        "jäääär",
        "辛口",
    ]
    assert result.info.version
    assert result.formats["duration"] == "JMP duration in seconds"


def test_native_jmp_reader_decodes_compressed_and_compact_text() -> None:
    compressed = read_jmp(FIXTURES / "compressed.jmp").frame
    compact = read_jmp(FIXTURES / "compact.jmp").frame

    assert compressed.shape == (10_000, 7)
    assert compressed["numeric"].eq(1).all()
    assert compressed["character1"].eq("a").all()
    assert compressed["character11"].eq("abcdefghijk").all()
    assert compressed["character130"].eq("abcdefghij" * 13).all()
    assert compact["normalsubtype"].tolist() == ["aa", "b", "ccc", "dd", "dd"]
    assert compact["compactsubtype"].tolist() == ["aa", "b", "ccc", "dd", "dd"]
    assert len(compact["longcompact"].iloc[0]) == 254
    assert len(compact["longcompact"].iloc[3]) == 256


def test_native_jmp_reader_decodes_dates_missing_integers_and_row_states() -> None:
    dates = read_jmp(FIXTURES / "date.jmp").frame
    integers = read_jmp(FIXTURES / "byteintegers_withmissing.jmp").frame
    row_states = read_jmp(FIXTURES / "rowstate.jmp")

    assert dates["ddmmyyyy"].tolist() == [
        pd.Timestamp("2011-05-25"),
        pd.Timestamp("1973-05-24"),
        pd.Timestamp("2027-05-22"),
        pd.Timestamp("2020-05-01"),
    ]
    assert integers["1-byte integer"].iloc[:5].tolist() == [0, 1, 0, 1, 0]
    assert pd.isna(integers["1-byte integer"].iloc[5])
    assert row_states.frame["rowstate3"].tolist() == ["•", "▲", "ꙮ"]
    assert any(
        warning[0] == "jmp.row_state_color_not_extracted"
        for warning in row_states.warnings
    )


def test_jmp_to_csv_conversion_uses_native_reader_and_reports_loss(
    tmp_path,
) -> None:
    destination = tmp_path / "converted.csv"

    result = ConversionService().convert(
        FIXTURES / "example1.jmp",
        destination,
    )
    actual = pd.read_csv(destination)

    assert actual.shape == (4, 12)
    assert actual["ints"].tolist() == [1, 2, 3, 4]
    assert actual["char utf8"].tolist() == ["ꙮꙮꙮ", "🚴💨", "jäääär", "辛口"]
    codes = {change["code"] for change in result["report"]["changes"]}
    assert "jmp.native_open_reader" in codes
    assert "jmp.metadata_not_extracted" in codes
    assert "jmp.duration_values_as_seconds" in codes
    assert result["report"]["lossless"] is False


@pytest.mark.parametrize(
    ("format_id", "extension", "reader_name"),
    [
        ("stata", ".dta", "read_dta"),
        ("spss_data", ".sav", "read_sav"),
        ("sas_xport", ".xpt", "read_xport"),
    ],
)
def test_jmp_converts_to_readstat_formats_with_reported_safe_names(
    tmp_path,
    format_id,
    extension,
    reader_name,
) -> None:
    pyreadstat = pytest.importorskip("pyreadstat")
    destination = tmp_path / f"converted{extension}"

    result = ConversionService().convert(
        FIXTURES / "example1.jmp",
        destination,
        output_format=format_id,
    )
    frame, _ = getattr(pyreadstat, reader_name)(destination)

    assert frame.shape == (4, 12)
    assert frame["char_utf8"].tolist() == ["ꙮꙮꙮ", "🚴💨", "jäääär", "辛口"]
    renames = [
        change
        for change in result["report"]["changes"]
        if change["code"] == "column.renamed_for_destination"
    ]
    assert any(
        "'char utf8' was renamed to 'char_utf8'" in change["message"]
        for change in renames
    )


def test_native_jmp_reader_rejects_non_jmp_data(tmp_path) -> None:
    invalid = tmp_path / "invalid.jmp"
    invalid.write_bytes(b"not-a-jmp-table")

    with pytest.raises(JmpReadError, match="signature"):
        read_jmp(invalid)


def test_jmp_output_is_not_claimed_without_an_open_writer(tmp_path) -> None:
    source = tmp_path / "source.csv"
    source.write_text("case_id\n1\n", encoding="utf-8")

    with pytest.raises(
        RuntimeError,
        match="Native JMP writing is unavailable",
    ):
        ConversionService().convert(source, tmp_path / "output.jmp")
