from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from statdata_converter.adapters.tabular import ExcelAdapter
from statdata_converter.package import read_dataset_package, write_dataset_package
from statdata_converter.report import ConversionReport
from statdata_converter.temporal import profile_temporal_columns
from statdata_converter.vendor import detect_vendor_runtime

PROTOCOL_VERSION = 1
BRIDGE_VERSION = "0.10.0"
FORMATS = {
    "minitab": {
        "runtime": "minitab",
        "script": "minitab_bridge.ps1",
        "name": "Minitab",
    },
    "statistica": {
        "runtime": "statistica",
        "script": "statistica_bridge.ps1",
        "name": "Statistica",
    },
}


def _resource(name: str) -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    return Path(bundled) / name if bundled else Path(__file__).resolve().with_name(name)


def _powershell() -> str:
    executable = shutil.which("powershell.exe") or shutil.which("powershell")
    if not executable:
        raise FileNotFoundError("Windows PowerShell was not detected.")
    return executable


def _probe(vendor: str) -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError(
            f"The {FORMATS[vendor]['name']} COM bridge is available only on Windows."
        )
    status = detect_vendor_runtime(FORMATS[vendor]["runtime"])
    if not status.detected:
        raise FileNotFoundError(status.detail)
    completed = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_resource(FORMATS[vendor]["script"])),
            "-Action",
            "probe",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            completed.stderr.strip()
            or f"{FORMATS[vendor]['name']} COM activation failed."
        )
    return {
        "status": "ok",
        "protocol_version": PROTOCOL_VERSION,
        "version": (
            f"{BRIDGE_VERSION} / {FORMATS[vendor]['name']} "
            f"{status.version or 'detected'}"
        ),
        "can_read": True,
        "can_write": True,
    }


def _run(
    vendor: str,
    action: str,
    source: Path,
    destination: Path,
    timeout: float,
) -> None:
    completed = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_resource(FORMATS[vendor]["script"])),
            "-Action",
            action,
            "-Source",
            str(source),
            "-Destination",
            str(destination),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            completed.stderr.strip() or f"{FORMATS[vendor]['name']} automation failed."
        )
    if not destination.is_file():
        raise RuntimeError(
            f"{FORMATS[vendor]['name']} did not create the requested file."
        )


def _report(source: str, target: str) -> ConversionReport:
    return ConversionReport("bridge", "bridge", source, target)


def _read(vendor: str, request: dict[str, Any]) -> dict[str, Any]:
    package = Path(request["package_path"]).resolve()
    timeout = float((request.get("options") or {}).get("timeout_seconds", 300))
    with tempfile.TemporaryDirectory(prefix=f"statdata-{vendor}-read-") as value:
        interchange = Path(value) / "vendor-export.xlsx"
        _run(
            vendor,
            "read",
            Path(request["input_path"]).resolve(),
            interchange,
            timeout,
        )
        dataset = ExcelAdapter().read(
            interchange,
            {},
            _report(vendor, "excel_xlsx"),
        )
        profile_temporal_columns(dataset)
        dataset.metadata.extra["native_format"] = vendor
        write_dataset_package(dataset, package)
    return _changes(vendor, "read")


def _write(vendor: str, request: dict[str, Any]) -> dict[str, Any]:
    destination = Path(request["output_path"]).resolve()
    if destination.exists():
        raise FileExistsError(
            f"The {FORMATS[vendor]['name']} bridge will not overwrite an existing file."
        )
    timeout = float((request.get("options") or {}).get("timeout_seconds", 300))
    dataset = read_dataset_package(Path(request["package_path"]).resolve())
    with tempfile.TemporaryDirectory(prefix=f"statdata-{vendor}-write-") as value:
        interchange = Path(value) / "statdata-import.xlsx"
        ExcelAdapter().write(
            dataset,
            interchange,
            {},
            _report("package", "excel_xlsx"),
        )
        _run(vendor, "write", interchange, destination, timeout)
    return _changes(vendor, "write")


def _changes(vendor: str, action: str) -> dict[str, Any]:
    name = FORMATS[vendor]["name"]
    return {
        "status": "ok",
        "changes": [
            {
                "severity": "warning",
                "code": f"{vendor}.bridge_xlsx_projection",
                "message": (
                    f"{name} {action} used a temporary XLSX table. Data and "
                    "displayed date/time values are retained where Excel can "
                    "represent them, but project output, analyses, design objects, "
                    "constants, matrices, formulas, and vendor-specific properties "
                    "are not preserved."
                ),
                "columns": [],
            },
            {
                "severity": "warning",
                "code": f"{vendor}.bridge_vendor_validation_required",
                "message": (
                    f"The result must pass fixture comparison and opening tests "
                    f"in the installed {name} release before any lossless claim."
                ),
                "columns": [],
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vendor", choices=tuple(FORMATS), required=True)
    parser.add_argument("action", choices=("probe", "read", "write"))
    args = parser.parse_args()
    try:
        request = json.load(sys.stdin)
        if request.get("protocol_version") != PROTOCOL_VERSION:
            raise ValueError("Unsupported bridge protocol version.")
        if args.action == "probe":
            result = _probe(args.vendor)
        elif args.action == "read":
            result = _read(args.vendor, request)
        else:
            result = _write(args.vendor, request)
    except Exception as exc:
        result = {"status": "error", "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
