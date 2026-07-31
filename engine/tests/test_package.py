import pandas as pd

from statdata_converter.models import Dataset, DatasetMetadata
from statdata_converter.package import (
    read_dataset_package,
    write_dataset_package,
)


def test_dataset_package_preserves_table_and_metadata(tmp_path) -> None:
    package = tmp_path / "example.statdata-package"
    dataset = Dataset(
        frame=pd.DataFrame(
            {
                "case_id": [1, 2],
                "group": [1, 2],
                "observed": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            }
        ),
        metadata=DatasetMetadata(
            dataset_label="Example",
            table_name="SURVEY",
            column_labels={"group": "Study group"},
            value_labels={"group": {1: "Control", 2: "Treatment"}},
            missing_values={"group": [99]},
            missing_ranges={"case_id": [{"lo": 900, "hi": 999}]},
            notes=["Synthetic fixture"],
            extra={"native_format": "test"},
        ),
    )

    write_dataset_package(dataset, package)
    actual = read_dataset_package(package)

    pd.testing.assert_frame_equal(actual.frame, dataset.frame, check_dtype=False)
    assert actual.metadata.dataset_label == "Example"
    assert actual.metadata.table_name == "SURVEY"
    assert actual.metadata.value_labels == {
        "group": {1: "Control", 2: "Treatment"}
    }
    assert actual.metadata.missing_ranges == {
        "case_id": [{"lo": 900, "hi": 999}]
    }
    assert actual.metadata.notes == ["Synthetic fixture"]
