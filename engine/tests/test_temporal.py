from datetime import date, datetime, time, timedelta, timezone

import pandas as pd
import pytest

from statdata_converter.models import Dataset
from statdata_converter.report import ConversionReport
from statdata_converter.service import ConversionService
from statdata_converter.temporal import (
    TemporalCompatibilityError,
    preflight_temporal_conversion,
    profile_temporal_columns,
)


def _report(output_format: str) -> ConversionReport:
    return ConversionReport("input", "output", "test", output_format)


def test_profiles_temporal_kinds_precision_timezone_and_missingness() -> None:
    dataset = Dataset(
        pd.DataFrame(
            {
                "date": [date(2024, 2, 29), None],
                "datetime": [
                    datetime(  # noqa: DTZ001 - naive value is intentional
                        2024, 2, 29, 23, 59, 58, 123456
                    ),
                    None,
                ],
                "time": [time(23, 59, 58, 123000), None],
                "duration": [timedelta(days=1, microseconds=1), None],
                "utc": [
                    datetime(
                        2024,
                        2,
                        29,
                        23,
                        59,
                        tzinfo=timezone.utc,
                    ),
                    None,
                ],
                "plain": [1, 2],
            }
        )
    )

    profiles = profile_temporal_columns(dataset)

    assert set(profiles) == {"date", "datetime", "time", "duration", "utc"}
    assert profiles["date"].kind == "date"
    assert profiles["date"].precision == "day"
    assert profiles["datetime"].precision == "microsecond"
    assert profiles["time"].precision == "millisecond"
    assert profiles["duration"].kind == "duration"
    assert profiles["duration"].precision == "microsecond"
    assert profiles["utc"].timezone == "UTC"
    assert profiles["date"].missing_count == 1


def test_readstat_preflight_reports_precision_timezone_and_duration_loss() -> None:
    dataset = Dataset(
        pd.DataFrame(
            {
                "observed": pd.Series(
                    ["2024-02-29 23:59:58.123456+00:00"],
                    dtype="datetime64[us, UTC]",
                ),
                "elapsed": pd.to_timedelta(["1 days 00:00:00.000001"]),
            }
        )
    )
    report = _report("stata")

    preflight_temporal_conversion(dataset, "stata", {}, report)

    entries = {entry.column: entry for entry in report.temporal}
    assert entries["observed"].outcome == "lossy"
    assert entries["observed"].destination_precision == "second"
    assert entries["observed"].destination_timezone is None
    assert entries["elapsed"].destination_kind == "text"
    assert {change.code for change in report.changes} == {
        "temporal.datetime_reduced",
        "temporal.duration_to_text",
    }


def test_safe_policy_rejects_text_fallback() -> None:
    dataset = Dataset(
        pd.DataFrame({"observed": pd.to_datetime(["2024-02-29 10:11:12"])})
    )
    report = _report("csv")

    with pytest.raises(
        TemporalCompatibilityError,
        match="Safe temporal policy",
    ):
        preflight_temporal_conversion(
            dataset,
            "csv",
            {"temporal_policy": "safe"},
            report,
        )

    assert report.temporal[0].destination_kind == "text"
    assert report.changes[0].code == "temporal.type_to_text"


def test_timezone_aware_excel_is_blocked_before_writing() -> None:
    dataset = Dataset(
        pd.DataFrame(
            {
                "observed": pd.Series(
                    ["2024-02-29 10:11:12+00:00"],
                    dtype="datetime64[us, UTC]",
                )
            }
        )
    )
    report = _report("excel_xlsx")

    with pytest.raises(
        TemporalCompatibilityError,
        match="cannot safely represent",
    ):
        preflight_temporal_conversion(dataset, "excel_xlsx", {}, report)

    assert report.temporal[0].code == "temporal.timezone_unsupported"
    assert report.changes[0].severity == "error"


def test_r_preflight_distinguishes_exact_assumed_and_unsupported_time() -> None:
    dataset = Dataset(
        pd.DataFrame(
            {
                "date": [date(2024, 2, 29)],
                "aware": pd.Series(
                    ["2024-02-29 10:11:12.123456+00:00"],
                    dtype="datetime64[us, UTC]",
                ),
                "naive": pd.to_datetime(["2024-02-29 10:11:12.123456"]),
                "time": [time(10, 11, 12)],
            }
        )
    )
    report = _report("r_data")

    with pytest.raises(
        TemporalCompatibilityError,
        match="cannot safely represent",
    ):
        preflight_temporal_conversion(dataset, "r_data", {}, report)

    entries = {entry.column: entry for entry in report.temporal}
    assert entries["date"].outcome == "exact"
    assert entries["aware"].outcome == "exact"
    assert entries["naive"].code == "temporal.timezone_assumed"
    assert entries["naive"].destination_timezone == "UTC"
    assert entries["time"].outcome == "unsupported"


def test_conversion_report_contains_temporal_text_fallback(tmp_path) -> None:
    source = tmp_path / "dates.xlsx"
    destination = tmp_path / "dates.csv"
    pd.DataFrame(
        {
            "observed": pd.to_datetime(
                ["2024-02-29 10:11:12.123", "1970-01-01 00:00:00.000"]
            )
        }
    ).to_excel(source, index=False)

    result = ConversionService().convert(source, destination)

    temporal = result["report"]["temporal"]
    assert len(temporal) == 1
    assert temporal[0]["column"] == "observed"
    assert temporal[0]["source_kind"] == "datetime"
    assert temporal[0]["destination_kind"] == "text"
    assert temporal[0]["outcome"] == "lossy"
    assert result["report"]["summary"]["temporal_lossy"] == 1
