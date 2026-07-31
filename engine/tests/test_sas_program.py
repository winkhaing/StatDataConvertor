from datetime import date, datetime

import pandas as pd
from statdata_converter.adapters.rdata import RDataAdapter
from statdata_converter.models import Dataset
from statdata_converter.report import ConversionReport
from statdata_converter.service import ConversionService
from statdata_converter.temporal import profile_temporal_columns


def test_writes_sas_program_and_utf8_csv_sidecar(tmp_path) -> None:
    source = tmp_path / "source.rds"
    program = tmp_path / "survey.sas"
    frame = pd.DataFrame(
        {
            "case id": [1, 2],
            "label": ["café", "辛口"],
            "visit date": [date(2024, 2, 29), date(1960, 1, 1)],
            "observed": [
                datetime(2024, 2, 29, 12, 30, 1, 123000),  # noqa: DTZ001
                datetime(1960, 1, 1, 0, 0),  # noqa: DTZ001
            ],
        }
    )
    dataset = Dataset(frame)
    profile_temporal_columns(dataset)
    RDataAdapter().write(
        dataset,
        source,
        {},
        ConversionReport("memory", str(source), "memory", "r_data"),
    )

    result = ConversionService().convert(
        source,
        program,
        input_format="r_data",
        output_format="sas_program",
        output_options={"replace": True},
    )

    text = program.read_text(encoding="utf-8")
    csv_text = program.with_suffix(".csv").read_text(encoding="utf-8")
    assert "filename statcsv" in text
    assert "informat visit_date e8601da." in text
    assert "informat observed e8601dt." in text
    assert "case_id :best32." in text
    assert "café" in csv_text
    assert "辛口" in csv_text
    codes = {change["code"] for change in result["report"]["changes"]}
    assert "sas.program_csv_sidecar" in codes
    assert "sas.program_columns_renamed" in codes
