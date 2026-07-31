import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from statdata_converter.models import Dataset, DatasetMetadata
from statdata_converter.package import (
    read_dataset_package,
    write_dataset_package,
)


BRIDGE_SOURCE = (
    Path(__file__).parents[2]
    / "bridges"
    / "jmp"
    / "src"
    / "statdata_jmp_bridge.py"
)
SPEC = importlib.util.spec_from_file_location("statdata_jmp_bridge", BRIDGE_SOURCE)
assert SPEC and SPEC.loader
JMP_BRIDGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(JMP_BRIDGE)


def test_jmp_bridge_package_csv_projection(tmp_path) -> None:
    source_package = tmp_path / "source.statdata-package"
    csv_path = tmp_path / "interchange.csv"
    result_package = tmp_path / "result.statdata-package"
    dataset = Dataset(
        frame=pd.DataFrame(
            {
                "case_id": [1, 2],
                "score": [2.5, None],
                "group": ["Control", "Treatment"],
                "active": [True, False],
            }
        ),
        metadata=DatasetMetadata(
            table_name="SURVEY",
            column_labels={"group": "Study group"},
        ),
    )
    write_dataset_package(dataset, source_package)

    JMP_BRIDGE.package_to_csv(source_package, csv_path)
    JMP_BRIDGE.csv_to_package(
        csv_path,
        result_package,
        table_name="ROUNDTRIP",
    )
    actual = read_dataset_package(result_package)

    pd.testing.assert_frame_equal(actual.frame, dataset.frame, check_dtype=False)
    assert actual.metadata.table_name == "ROUNDTRIP"
    assert actual.metadata.column_labels == {}
    assert actual.metadata.extra["native_format"] == "jmp"


def test_jmp_bridge_uses_explicit_executable(monkeypatch, tmp_path) -> None:
    executable = tmp_path / "jmp"
    executable.write_text("fixture", encoding="utf-8")
    monkeypatch.setenv("STATDATA_JMP_EXECUTABLE", str(executable))

    assert JMP_BRIDGE.find_jmp_executable() == executable.resolve()
    result = JMP_BRIDGE.probe()
    assert result["status"] == "ok"
    assert result["can_read"] is True
    assert result["can_write"] is True


def test_jmp_bridge_probe_fails_closed_without_jmp(monkeypatch, tmp_path) -> None:
    missing = tmp_path / "missing-jmp"
    monkeypatch.setenv("STATDATA_JMP_EXECUTABLE", str(missing))

    with pytest.raises(FileNotFoundError, match="JMP was not detected"):
        JMP_BRIDGE.probe()


def test_jmp_bridge_refuses_to_overwrite_output(monkeypatch, tmp_path) -> None:
    executable = tmp_path / "JMP"
    executable.write_text("fixture", encoding="utf-8")
    output = tmp_path / "existing.jmp"
    output.write_bytes(b"keep-me")
    monkeypatch.setattr(JMP_BRIDGE, "find_jmp_executable", lambda: executable)

    with pytest.raises(FileExistsError, match="will not overwrite"):
        JMP_BRIDGE.write(
            {
                "package_path": str(tmp_path / "unused-package"),
                "output_path": str(output),
                "options": {},
            }
        )
    assert output.read_bytes() == b"keep-me"


def test_jmp_bridge_manifest_stays_unverified() -> None:
    manifest = json.loads(
        BRIDGE_SOURCE.parents[1]
        .joinpath("manifest.template.json")
        .read_text(encoding="utf-8")
    )

    assert manifest["format"]["id"] == "jmp"
    assert manifest["format"]["trust"] == "experimental"
    assert manifest["format"]["metadata_features"] == []


def test_jmp_bridge_read_and_write_actions_report_projection(
    monkeypatch,
    tmp_path,
) -> None:
    executable = tmp_path / "JMP"
    executable.write_text("fixture", encoding="utf-8")

    class FakeProcess:
        stderr = None

        def poll(self):
            return None

    def fake_popen(arguments, *, env, **kwargs):
        del arguments, kwargs
        source = Path(env["STATDATA_JMP_SOURCE"])
        destination = Path(env["STATDATA_JMP_DESTINATION"])
        if env["STATDATA_JMP_ACTION"] == "read":
            assert source.suffix == ".jmp"
            destination.write_text(
                "case_id,group,score\n1,Control,4.5\n2,Treatment,\n",
                encoding="utf-8",
            )
        else:
            assert source.suffix == ".csv"
            destination.write_bytes(b"synthetic-jmp")
        Path(env["STATDATA_JMP_STATUS"]).write_text("ok", encoding="utf-8")
        return FakeProcess()

    monkeypatch.setattr(JMP_BRIDGE, "find_jmp_executable", lambda: executable)
    monkeypatch.setattr(JMP_BRIDGE.subprocess, "Popen", fake_popen)

    native = tmp_path / "source.jmp"
    native.write_bytes(b"synthetic-jmp")
    read_package = tmp_path / "read.statdata-package"
    read_result = JMP_BRIDGE.read(
        {
            "input_path": str(native),
            "package_path": str(read_package),
            "options": {},
        }
    )
    dataset = read_dataset_package(read_package)

    assert dataset.frame["case_id"].tolist() == [1, 2]
    assert dataset.frame["group"].tolist() == ["Control", "Treatment"]
    assert pd.isna(dataset.frame.loc[1, "score"])
    assert {
        change["code"] for change in read_result["changes"]
    } == {
        "jmp.bridge_metadata_not_extracted",
        "jmp.bridge_types_inferred",
    }

    output = tmp_path / "output.jmp"
    write_result = JMP_BRIDGE.write(
        {
            "package_path": str(read_package),
            "output_path": str(output),
            "options": {},
        }
    )
    assert output.read_bytes() == b"synthetic-jmp"
    assert write_result["changes"][0]["code"] == "jmp.bridge_tabular_projection"
