import os
from pathlib import Path

from statdata_converter.service import ConversionService
from statdata_converter.vendor import detect_vendor_runtime


def test_vendor_runtime_can_be_configured_explicitly(
    tmp_path: Path,
    monkeypatch,
) -> None:
    executable = tmp_path / "SASFoundation" / "9.4" / "sas"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("STATDATA_SAS_EXECUTABLE", str(executable))

    status = detect_vendor_runtime("sas")

    assert status.detected is True
    assert status.executable == str(executable.resolve())
    assert status.version == "9.4"


def test_capabilities_report_all_vendor_runtime_states(monkeypatch) -> None:
    for name in (
        "STATDATA_JMP_EXECUTABLE",
        "STATDATA_SAS_EXECUTABLE",
        "STATDATA_MINITAB_EXECUTABLE",
        "STATDATA_STATISTICA_EXECUTABLE",
    ):
        monkeypatch.delenv(name, raising=False)

    runtimes = ConversionService().capabilities()["vendor_runtimes"]

    assert {runtime["id"] for runtime in runtimes} == {
        "jmp",
        "sas",
        "minitab",
        "statistica",
    }
    assert all("automation" in runtime for runtime in runtimes)
    assert (
        os.name == "nt"
        or next(item for item in runtimes if item["id"] == "minitab")["detected"]
        is False
    )
