import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_sas_bridge_probe_uses_configured_runtime(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "sas"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    environment = os.environ.copy()
    environment["STATDATA_SAS_EXECUTABLE"] = str(executable)
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "bridges/sas/src/statdata_sas_bridge.py"),
            "--format",
            "sas_data",
            "probe",
        ],
        input=json.dumps({"protocol_version": 1}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        check=False,
    )

    response = json.loads(completed.stdout)
    assert response["status"] == "ok"
    assert response["can_read"] is True
    assert response["can_write"] is True
    assert response["version"].startswith("0.10.0 / SAS")


def test_windows_com_bridge_is_safely_unavailable_off_windows() -> None:
    if os.name == "nt":
        return
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "bridges/windows-com/src/statdata_windows_com_bridge.py"),
            "--vendor",
            "minitab",
            "probe",
        ],
        input=json.dumps({"protocol_version": 1}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    response = json.loads(completed.stdout)
    assert response["status"] == "error"
    assert "only on Windows" in response["error"]


def test_vendor_bridge_manifests_are_protocol_compatible() -> None:
    manifests = [
        ROOT / "bridges/sas/manifest.sas-data.template.json",
        ROOT / "bridges/sas/manifest.cport.template.json",
        ROOT / "bridges/windows-com/manifest.minitab.template.json",
        ROOT / "bridges/windows-com/manifest.statistica.template.json",
    ]
    values = [json.loads(path.read_text(encoding="utf-8")) for path in manifests]

    assert all(value["protocol_version"] == 1 for value in values)
    assert {value["format"]["id"] for value in values} == {
        "sas_data",
        "sas_cport",
        "minitab",
        "statistica",
    }
    assert all(value["format"]["trust"] == "experimental" for value in values)
