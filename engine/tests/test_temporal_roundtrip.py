import json
from datetime import date, datetime, time

import numpy as np
import pandas as pd
import pytest

from statdata_converter.registry import FormatRegistry
from statdata_converter.report import ConversionReport
from statdata_converter.service import ConversionService
from statdata_converter.temporal import TemporalCompatibilityError


def _write_native_temporal_xport(path) -> None:
    pyreadstat = pytest.importorskip("pyreadstat")
    epoch = datetime(1960, 1, 1)  # noqa: DTZ001 - native SAS epoch is naive
    dates = [datetime(2024, 2, 29), datetime(1959, 12, 31), None]  # noqa: DTZ001
    datetimes = [  # noqa: DTZ001
        datetime(2024, 2, 29, 23, 59, 58, 123456),
        datetime(1959, 12, 31, 0, 0, 0, 1),
        None,
    ]
    times = [  # noqa: DTZ001
        datetime(1960, 1, 1, 23, 59, 58, 123456),
        datetime(1960, 1, 1, 0, 0, 0, 1),
        None,
    ]
    frame = pd.DataFrame(
        {
            "date": [
                (value - epoch).days if value is not None else np.nan
                for value in dates
            ],
            "datetime": [
                (value - epoch).total_seconds() if value is not None else np.nan
                for value in datetimes
            ],
            "time": [
                (value - epoch).total_seconds() if value is not None else np.nan
                for value in times
            ],
            "metric": [1.0, 2.0, 3.0],
        }
    )
    pyreadstat.write_xport(
        frame,
        path,
        file_format_version=8,
        variable_format={
            "date": "DATE9.",
            "datetime": "DATETIME26.6",
            "time": "TIME15.6",
        },
    )


@pytest.mark.parametrize(
    ("target_format", "extension"),
    [
        ("stata", ".dta"),
        ("spss_data", ".sav"),
        ("sas_xport", ".xpt"),
    ],
)
def test_readstat_temporal_matrix_reports_and_matches_known_fidelity(
    tmp_path,
    target_format,
    extension,
) -> None:
    source = tmp_path / "source.xpt"
    destination = tmp_path / f"destination{extension}"
    _write_native_temporal_xport(source)

    result = ConversionService().convert(
        source,
        destination,
        output_format=target_format,
    )

    adapter = FormatRegistry().get(target_format)
    read_report = ConversionReport(
        str(destination),
        "memory",
        target_format,
        "test",
    )
    actual = adapter.read(destination, {}, read_report).frame
    temporal = {
        entry["column"]: entry for entry in result["report"]["temporal"]
    }

    assert temporal["date"]["outcome"] == "exact"
    assert temporal["datetime"]["outcome"] == "lossy"
    assert temporal["datetime"]["destination_precision"] == "second"
    assert temporal["time"]["outcome"] == "exact"
    assert actual["date"].iloc[:2].tolist() == [
        date(2024, 2, 29),
        date(1959, 12, 31),
    ]
    assert actual["datetime"].iloc[:2].tolist() == [
        pd.Timestamp("2024-02-29 23:59:58"),
        pd.Timestamp("1959-12-31 00:00:00"),
    ]
    assert actual["time"].iloc[:2].tolist() == [
        time(23, 59, 58, 123456),
        time(0, 0, 0, 1),
    ]
    assert pd.isna(actual.loc[2, "date"])
    assert pd.isna(actual.loc[2, "datetime"])
    assert pd.isna(actual.loc[2, "time"])


def test_safe_policy_blocks_readstat_precision_loss_before_output(tmp_path) -> None:
    source = tmp_path / "source.xpt"
    destination = tmp_path / "destination.dta"
    _write_native_temporal_xport(source)

    with pytest.raises(
        TemporalCompatibilityError,
        match="Safe temporal policy",
    ):
        ConversionService().convert(
            source,
            destination,
            output_options={"temporal_policy": "safe"},
        )

    assert not destination.exists()
    report_path = destination.with_name(
        destination.name + ".statdata-report.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert any(
        entry["code"] == "temporal.datetime_reduced"
        for entry in report["temporal"]
    )


def test_native_temporal_source_to_excel_reports_known_changes(tmp_path) -> None:
    source = tmp_path / "source.xpt"
    destination = tmp_path / "destination.xlsx"
    _write_native_temporal_xport(source)

    result = ConversionService().convert(source, destination)
    actual = pd.read_excel(destination)
    temporal = {
        entry["column"]: entry for entry in result["report"]["temporal"]
    }

    assert temporal["date"]["outcome"] == "exact"
    assert temporal["datetime"]["destination_precision"] == "millisecond"
    assert temporal["time"]["destination_kind"] == "text"
    assert actual.loc[0, "datetime"] == pd.Timestamp(
        "2024-02-29 23:59:58.123"
    )
    assert actual.loc[0, "time"] == "23:59:58.123456"
