import shutil
import subprocess
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from statdata_converter.adapters.rdata import RDataAdapter
from statdata_converter.models import Dataset
from statdata_converter.report import ConversionReport
from statdata_converter.service import ConversionService


@pytest.mark.parametrize(
    ("format_id", "extension"),
    [
        ("stata", ".dta"),
        ("spss_data", ".sav"),
        ("sas_xport", ".xpt"),
        ("r_data", ".rds"),
        ("r_data", ".RData"),
    ],
)
def test_statistical_adapter_round_trip(tmp_path, format_id, extension) -> None:
    if format_id != "r_data":
        pytest.importorskip("pyreadstat")

    source = tmp_path / "source.csv"
    native = tmp_path / f"native{extension}"
    destination = tmp_path / "roundtrip.csv"
    expected = pd.DataFrame(
        {
            "case_id": [1, 2, 3],
            "score": [1.25, 8.5, 10.0],
            "group": ["control", "test", "test"],
        }
    )
    expected.to_csv(source, index=False)
    service = ConversionService()

    service.convert(source, native, output_format=format_id)
    service.convert(native, destination, input_format=format_id)
    actual = pd.read_csv(destination)

    pd.testing.assert_frame_equal(actual, expected, check_dtype=False)


def test_r_factor_levels_become_codes_and_value_labels(tmp_path) -> None:
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript is needed to create an independent factor fixture")
    source = tmp_path / "factor.rds"
    subprocess.run(
        [
            rscript,
            "--vanilla",
            "-e",
            (
                "saveRDS(data.frame(group=factor(c('control','test',NA))), "
                f"'{source.as_posix()}')"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    report = ConversionReport(
        input_path=str(source),
        output_path="",
        input_format="r_data",
        output_format="csv",
    )

    dataset = RDataAdapter().read(source, {}, report)

    assert dataset.frame["group"].iloc[:2].tolist() == [1, 2]
    assert pd.isna(dataset.frame["group"].iloc[2])
    assert dataset.metadata.value_labels == {
        "group": {1: "control", 2: "test"}
    }
    assert any(
        change.code == "r.factor_levels_preserved"
        for change in report.changes
    )


def test_native_r_temporal_classes_are_restored(tmp_path) -> None:
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript is needed to create an independent temporal fixture")
    source = tmp_path / "temporal.rds"
    subprocess.run(
        [
            rscript,
            "--vanilla",
            "-e",
            (
                "saveRDS(data.frame("
                "date=as.Date(c('2024-02-29','1970-01-01',NA)),"
                "datetime=as.POSIXct(c("
                "'2024-02-29 23:59:58.123456',"
                "'1960-01-02 03:04:05',NA),tz='UTC'),"
                "duration=as.difftime(c(93784.123456,-1,NA),units='secs')"
                f"),'{source.as_posix()}')"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    report = ConversionReport(
        str(source),
        "",
        "r_data",
        "test",
    )

    dataset = RDataAdapter().read(source, {}, report)

    assert dataset.frame["date"].tolist() == [
        date(2024, 2, 29),
        date(1970, 1, 1),
        None,
    ]
    assert dataset.frame["datetime"].iloc[0] == pd.Timestamp(
        "2024-02-29 23:59:58.123456",
        tz="UTC",
    )
    assert dataset.frame["duration"].iloc[0] == pd.Timedelta(
        "1 days 02:03:04.123456"
    )
    assert dataset.temporal["date"].kind == "date"
    assert dataset.temporal["datetime"].timezone == "UTC"
    assert dataset.temporal["duration"].kind == "duration"
    assert any(
        change.code == "r.temporal_classes_restored"
        for change in report.changes
    )


@pytest.mark.parametrize("extension", [".rds", ".RData"])
def test_r_temporal_classes_round_trip_without_r_installation(
    tmp_path,
    extension,
) -> None:
    path = tmp_path / f"temporal{extension}"
    expected = Dataset(
        pd.DataFrame(
            {
                "date": [date(2024, 2, 29), date(1970, 1, 1), None],
                "datetime": [
                    datetime(
                        2024,
                        2,
                        29,
                        23,
                        59,
                        58,
                        123456,
                        tzinfo=timezone.utc,
                    ),
                    datetime(1960, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
                    None,
                ],
                "duration": [
                    timedelta(
                        days=1,
                        hours=2,
                        minutes=3,
                        seconds=4,
                        microseconds=123456,
                    ),
                    timedelta(seconds=-1),
                    None,
                ],
            }
        )
    )
    adapter = RDataAdapter()
    write_report = ConversionReport("memory", str(path), "test", "r_data")
    read_report = ConversionReport(str(path), "memory", "r_data", "test")

    adapter.write(expected, path, {}, write_report)
    actual = adapter.read(path, {}, read_report)

    assert actual.frame["date"].tolist() == expected.frame["date"].tolist()
    assert actual.frame["datetime"].tolist() == expected.frame["datetime"].tolist()
    assert actual.frame["duration"].tolist() == expected.frame["duration"].tolist()
    assert any(
        change.code == "r.temporal_classes_written"
        for change in write_report.changes
    )


def test_r_opens_app_written_temporal_classes(tmp_path) -> None:
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript is needed for independent output validation")
    path = tmp_path / "app-written.rds"
    dataset = Dataset(
        pd.DataFrame(
            {
                "date": [date(2024, 2, 29)],
                "datetime": [
                    datetime(
                        2024,
                        2,
                        29,
                        23,
                        59,
                        58,
                        123456,
                        tzinfo=timezone.utc,
                    )
                ],
                "duration": [timedelta(seconds=1, microseconds=123456)],
            }
        )
    )
    report = ConversionReport("memory", str(path), "test", "r_data")
    RDataAdapter().write(dataset, path, {}, report)

    validation = subprocess.run(
        [
            rscript,
            "--vanilla",
            "-e",
            (
                f"x<-readRDS('{path.as_posix()}');"
                "stopifnot(inherits(x$date,'Date'));"
                "stopifnot(inherits(x$datetime,'POSIXct'));"
                "stopifnot(inherits(x$duration,'difftime'));"
                "stopifnot(abs(as.numeric(x$datetime[1])-1709251198.123456)"
                "<0.000001);"
                "stopifnot(abs(as.numeric(x$duration[1],units='secs')"
                "-1.123456)<0.000001)"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert validation.returncode == 0


def test_spss_to_stata_preserves_labels_and_reports_missing_range_loss(
    tmp_path,
) -> None:
    pyreadstat = pytest.importorskip("pyreadstat")
    source = tmp_path / "labelled.sav"
    destination = tmp_path / "labelled.dta"
    frame = pd.DataFrame(
        {
            "gender": [1, 2, 1],
            "score": [5, 999, 8],
        }
    )
    pyreadstat.write_sav(
        frame,
        source,
        file_label="Example survey",
        column_labels={"gender": "Gender", "score": "Score"},
        variable_value_labels={"gender": {1: "Male", 2: "Female"}},
        missing_ranges={"score": [999]},
    )

    result = ConversionService().convert(source, destination)
    _, metadata = pyreadstat.read_dta(destination, user_missing=True)

    assert metadata.file_label == "Example survey"
    assert metadata.column_names_to_labels == {
        "gender": "Gender",
        "score": "Score",
    }
    assert metadata.variable_value_labels["gender"] == {
        1.0: "Male",
        2.0: "Female",
    }
    codes = {change["code"] for change in result["report"]["changes"]}
    assert "metadata_dropped.missing_ranges" in codes
    assert "metadata_transformed.display_formats" in codes
    assert result["report"]["lossless"] is False
