import json
import sys
from pathlib import Path

import pandas as pd

from statdata_converter.registry import FormatRegistry
from statdata_converter.service import ConversionService


BRIDGE_SCRIPT = r"""
import json
import sys
import zipfile
from pathlib import Path

action = sys.argv[1]
request = json.load(sys.stdin)
if action == "probe":
    print(json.dumps({
        "status": "ok",
        "protocol_version": 1,
        "version": "test-1",
        "can_read": True,
        "can_write": True,
    }))
elif action == "write":
    package = Path(request["package_path"])
    output = Path(request["output_path"])
    with zipfile.ZipFile(output, "w") as archive:
        for item in package.iterdir():
            archive.write(item, item.name)
    print(json.dumps({"status": "ok", "changes": []}))
elif action == "read":
    package = Path(request["package_path"])
    package.mkdir(parents=True)
    with zipfile.ZipFile(request["input_path"]) as archive:
        archive.extractall(package)
    print(json.dumps({"status": "ok", "changes": []}))
else:
    raise SystemExit(2)
"""


def _mock_bridge(tmp_path: Path) -> Path:
    script = tmp_path / "mock_bridge.py"
    script.write_text(BRIDGE_SCRIPT, encoding="utf-8")
    manifest = tmp_path / "jmp.statdata-bridge.json"
    manifest.write_text(
        json.dumps(
            {
                "protocol_version": 1,
                "name": "Test JMP",
                "executable": sys.executable,
                "arguments": [str(script)],
                "format": {
                    "id": "jmp",
                    "family": "JMP",
                    "label": "JMP data table",
                    "extensions": [".jmp"],
                    "can_read": True,
                    "can_write": True,
                    "trust": "experimental",
                    "metadata_features": ["table_name"],
                },
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_external_bridge_is_discovered_and_converts_through_package(
    tmp_path,
) -> None:
    manifest = _mock_bridge(tmp_path)
    registry = FormatRegistry(bridge_paths=[manifest])
    service = ConversionService(registry)
    source = tmp_path / "source.csv"
    native = tmp_path / "result.jmp"
    roundtrip = tmp_path / "roundtrip.csv"
    expected = pd.DataFrame(
        {
            "case_id": [1, 2],
            "score": [3.5, 9.0],
            "group": ["A", "B"],
        }
    )
    expected.to_csv(source, index=False)

    write_result = service.convert(source, native)
    service.convert(native, roundtrip)

    pd.testing.assert_frame_equal(
        pd.read_csv(roundtrip),
        expected,
        check_dtype=False,
    )
    capability = next(
        item for item in service.capabilities()["formats"] if item["id"] == "jmp"
    )
    assert capability["can_read"] is True
    assert capability["can_write"] is True
    assert capability["availability"] == "available"
    assert service.capabilities()["bridges"][0]["available"] is True
    assert "bridge.external_unverified" in {
        change["code"] for change in write_result["report"]["changes"]
    }


def test_invalid_bridge_remains_unavailable_and_reports_probe_failure(
    tmp_path,
) -> None:
    manifest = tmp_path / "broken.statdata-bridge.json"
    manifest.write_text(
        json.dumps(
            {
                "protocol_version": 1,
                "name": "Broken JMP",
                "executable": "./missing-bridge",
                "format": {
                    "id": "jmp",
                    "family": "JMP",
                    "label": "JMP data table",
                    "extensions": [".jmp"],
                },
            }
        ),
        encoding="utf-8",
    )

    service = ConversionService(FormatRegistry(bridge_paths=[manifest]))
    capability = next(
        item for item in service.capabilities()["formats"] if item["id"] == "jmp"
    )

    assert capability["can_read"] is True
    assert capability["can_write"] is False
    assert capability["availability"] == "available"
    assert service.capabilities()["bridges"][0]["available"] is False
    assert "not found" in service.capabilities()["bridges"][0]["detail"]
