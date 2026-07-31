import json

import pandas as pd

from statdata_converter.service import ConversionService


def test_csv_to_excel_writes_dataset_and_report(tmp_path) -> None:
    source = tmp_path / "survey.csv"
    destination = tmp_path / "survey.xlsx"
    pd.DataFrame(
        {
            "respondent": [1, 2, 3],
            "score": [4.5, None, 8.25],
            "group": ["A", "B", "A"],
        }
    ).to_csv(source, index=False)

    result = ConversionService().convert(source, destination)

    assert destination.is_file()
    actual = pd.read_excel(destination)
    assert actual["respondent"].tolist() == [1, 2, 3]
    assert actual["group"].tolist() == ["A", "B", "A"]
    assert pd.isna(actual.loc[1, "score"])
    assert result["report"]["rows"] == 3
    assert result["report"]["columns"] == 3

    with open(result["report_path"], encoding="utf-8") as stream:
        persisted = json.load(stream)
    assert persisted["status"] == "completed"
    assert persisted["input_format"] == "csv"
    assert persisted["output_format"] == "excel_xlsx"


def test_failed_conversion_still_writes_report(tmp_path) -> None:
    source = tmp_path / "survey.csv"
    destination = tmp_path / "survey.jmp"
    source.write_text("x\n1\n", encoding="utf-8")

    try:
        ConversionService().convert(source, destination)
    except Exception as exc:
        assert "JMP" in str(exc)
    else:
        raise AssertionError("Expected vendor-bridge conversion to fail")

    report_path = tmp_path / "survey.jmp.statdata-report.json"
    with report_path.open(encoding="utf-8") as stream:
        report = json.load(stream)
    assert report["status"] == "failed"
    assert report["summary"]["error"] == 1
    assert not destination.exists()
