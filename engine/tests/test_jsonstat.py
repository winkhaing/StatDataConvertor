import json

import pandas as pd

from statdata_converter.service import ConversionService


def test_jsonstat_to_csv_flattens_cube_and_reports_metadata_loss(tmp_path) -> None:
    source = tmp_path / "population.json"
    destination = tmp_path / "population.csv"
    source.write_text(
        json.dumps(
            {
                "version": "2.0",
                "class": "dataset",
                "label": "Population",
                "source": "Test fixture",
                "id": ["area", "year"],
                "size": [2, 2],
                "dimension": {
                    "area": {
                        "label": "Area",
                        "category": {
                            "index": {"north": 0, "south": 1},
                            "label": {"north": "North", "south": "South"},
                        },
                    },
                    "year": {
                        "label": "Year",
                        "category": {"index": ["2024", "2025"]},
                    },
                },
                "value": [10, 11, 20, None],
            }
        ),
        encoding="utf-8",
    )

    result = ConversionService().convert(source, destination)
    frame = pd.read_csv(destination)

    assert frame.to_dict("records")[:3] == [
        {"area": "north", "year": 2024, "value": 10.0},
        {"area": "north", "year": 2025, "value": 11.0},
        {"area": "south", "year": 2024, "value": 20.0},
    ]
    codes = {change["code"] for change in result["report"]["changes"]}
    assert "jsonstat.cube_flattened" in codes
    assert "metadata_dropped.dataset_label" in codes
    assert "metadata_dropped.value_labels" in codes
    assert result["report"]["lossless"] is False


def test_csv_to_jsonstat_writes_dense_cube(tmp_path) -> None:
    source = tmp_path / "measure.csv"
    destination = tmp_path / "measure.json"
    pd.DataFrame(
        {
            "area": ["north", "north", "south", "south"],
            "year": [2024, 2025, 2024, 2025],
            "population": [10, 11, 20, 21],
        }
    ).to_csv(source, index=False)

    ConversionService().convert(
        source,
        destination,
        output_options={
            "dimensions": ["area", "year"],
            "value_column": "population",
        },
    )

    with destination.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    assert payload["version"] == "2.0"
    assert payload["id"] == ["area", "year"]
    assert payload["size"] == [2, 2]
    assert payload["value"] == [10, 11, 20, 21]


def test_sparse_jsonstat_values_are_supported(tmp_path) -> None:
    source = tmp_path / "sparse.jsonstat"
    destination = tmp_path / "sparse.csv"
    source.write_text(
        json.dumps(
            {
                "class": "dataset",
                "id": ["kind"],
                "size": [3],
                "dimension": {
                    "kind": {"category": {"index": {"a": 0, "b": 1, "c": 2}}}
                },
                "value": {"0": 2, "2": 9},
            }
        ),
        encoding="utf-8",
    )

    ConversionService().convert(source, destination)
    frame = pd.read_csv(destination)
    assert frame["kind"].tolist() == ["a", "b", "c"]
    assert frame["value"].iloc[0] == 2
    assert pd.isna(frame["value"].iloc[1])
    assert frame["value"].iloc[2] == 9


def test_jsonstat_writer_represents_missing_dimension_values(tmp_path) -> None:
    source = tmp_path / "missing-dimension.csv"
    destination = tmp_path / "missing-dimension.json"
    pd.DataFrame(
        {
            "area": ["north", None],
            "population": [10, 20],
        }
    ).to_csv(source, index=False)

    result = ConversionService().convert(
        source,
        destination,
        output_options={
            "dimensions": ["area"],
            "value_column": "population",
        },
    )

    with destination.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    assert payload["dimension"]["area"]["category"]["index"] == {
        "north": 0,
        "__missing__": 1,
    }
    assert payload["value"] == [10, 20]
    assert any(
        change["code"] == "jsonstat.missing_dimension_category"
        for change in result["report"]["changes"]
    )
