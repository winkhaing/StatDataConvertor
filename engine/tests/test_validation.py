import json

import pandas as pd
from statdata_converter.service import ConversionService


def test_validation_round_trip_compares_data_and_metadata(tmp_path) -> None:
    source = tmp_path / "survey.csv"
    artifacts = tmp_path / "validation"
    pd.DataFrame(
        {
            "case_id": [1, 2, 3],
            "score": [2.5, None, 9.75],
            "group": ["control", "test", "test"],
        }
    ).to_csv(source, index=False)

    result = ConversionService().validate(
        source,
        "excel_xlsx",
        artifact_directory=artifacts,
    )

    assert result["status"] == "passed"
    assert result["data_equivalent"] is True
    assert result["metadata_equivalent"] is True
    assert result["lossless"] is True
    assert result["rows"] == 3
    assert result["columns"] == 3
    assert result["summary"]["data_issues"] == 0
    assert result["summary"]["metadata_issues"] == 0
    assert result["evidence"]["schema_version"] == 1
    assert result["evidence"]["engine"]["statdata_converter"]
    assert result["evidence"]["target_adapter"]["id"] == "excel_xlsx"
    assert len(result["evidence"]["vendor_runtimes"]) == 4

    with open(result["validation_path"], encoding="utf-8") as stream:
        persisted = json.load(stream)
    assert persisted == result
    assert artifacts.joinpath(
        "survey__roundtrip__excel_xlsx.xlsx"
    ).is_file()


def test_validation_distinguishes_data_integrity_from_metadata_loss(
    tmp_path,
) -> None:
    source = tmp_path / "survey.csv"
    pd.DataFrame({"case_id": [1, 2], "score": [5.0, 8.0]}).to_csv(
        source,
        index=False,
    )

    result = ConversionService().validate(
        source,
        "stata",
        artifact_directory=tmp_path / "validation",
    )

    assert result["status"] == "passed"
    assert result["data_equivalent"] is True
    assert result["metadata_equivalent"] is False
    assert result["lossless"] is False
    assert {
        issue["code"] for issue in result["issues"]
    } == {"metadata.table_name_changed"}


def test_validation_records_temporal_source_and_conversion_evidence(
    tmp_path,
) -> None:
    source = tmp_path / "dates.csv"
    pd.DataFrame(
        {
            "observed": [
                "2024-01-01T02:03:04.123456",
                "2024-06-30T23:59:59.000000",
            ],
            "value": [1, 2],
        }
    ).to_csv(source, index=False)

    result = ConversionService().validate(
        source,
        "excel_xlsx",
        artifact_directory=tmp_path / "validation",
        input_options={"parse_dates": ["observed"]},
        output_options={"temporal_policy": "compatible"},
    )

    temporal = result["evidence"]["temporal"]
    assert temporal["source_columns"][0]["column"] == "observed"
    assert temporal["source_columns"][0]["precision"] == "microsecond"
    assert temporal["conversion_decisions"][0]["column"] == "observed"
    assert temporal["conversion_decisions"][0]["outcome"] == "lossy"
