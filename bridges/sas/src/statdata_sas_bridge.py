from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from statdata_converter.adapters.readstat import ReadStatAdapter
from statdata_converter.package import read_dataset_package, write_dataset_package
from statdata_converter.report import ConversionReport
from statdata_converter.temporal import profile_temporal_columns
from statdata_converter.vendor import detect_vendor_runtime

PROTOCOL_VERSION = 1
BRIDGE_VERSION = "0.10.0"


def _sas_quote(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _member(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_]", "_", value).strip("_").upper()
    if not result or not result[0].isalpha():
        result = f"D_{result}"
    return result[:8]


def _sas_executable() -> Path:
    status = detect_vendor_runtime("sas")
    if not status.detected or not status.executable:
        raise FileNotFoundError(status.detail)
    return Path(status.executable)


def _run_sas(program: str, directory: Path, timeout: float) -> None:
    program_path = directory / "bridge.sas"
    log_path = directory / "bridge.log"
    listing_path = directory / "bridge.lst"
    program_path.write_text(program, encoding="utf-8")
    completed = subprocess.run(
        [
            str(_sas_executable()),
            "-sysin",
            str(program_path),
            "-log",
            str(log_path),
            "-print",
            str(listing_path),
            "-nosplash",
            "-noterminal",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )
    log = (
        log_path.read_text(encoding="utf-8", errors="replace")
        if log_path.is_file()
        else ""
    )
    errors = [
        line.strip() for line in log.splitlines() if line.lstrip().startswith("ERROR:")
    ]
    if completed.returncode != 0 or errors:
        detail = "\n".join(errors[-8:]) or completed.stderr.strip()
        raise RuntimeError(detail or "SAS batch execution failed.")


def _report(source: str, target: str) -> ConversionReport:
    return ConversionReport("bridge", "bridge", source, target)


def _write_xport_from_package(package_path: Path, xpt_path: Path) -> None:
    dataset = read_dataset_package(package_path)
    profile_temporal_columns(dataset)
    ReadStatAdapter("sas_xport").write(
        dataset,
        xpt_path,
        {"xport_version": 8, "table_name": "STATDATA"},
        _report("package", "sas_xport"),
    )


def _sas_data_read(request: dict[str, Any]) -> dict[str, Any]:
    source = Path(request["input_path"]).resolve()
    package = Path(request["package_path"]).resolve()
    dataset = ReadStatAdapter("sas_data").read(
        source,
        request.get("options") or {},
        _report("sas_data", "package"),
    )
    profile_temporal_columns(dataset)
    write_dataset_package(dataset, package)
    return {
        "status": "ok",
        "changes": [
            {
                "severity": "info",
                "code": "sas.open_reader_used",
                "message": (
                    "SAS7BDAT input was decoded by the bundled ReadStat reader; "
                    "the detected SAS runtime was not needed for this direction."
                ),
                "columns": [],
            }
        ],
    }


def _sas_data_write(request: dict[str, Any]) -> dict[str, Any]:
    destination = Path(request["output_path"]).resolve()
    if destination.exists():
        raise FileExistsError("The SAS bridge will not overwrite an existing file.")
    timeout = float((request.get("options") or {}).get("timeout_seconds", 300))
    with tempfile.TemporaryDirectory(prefix="statdata-sas-write-") as value:
        work = Path(value)
        library = work / "library"
        library.mkdir()
        xpt = work / "statdata.xpt"
        _write_xport_from_package(Path(request["package_path"]).resolve(), xpt)
        _run_sas(
            "\n".join(
                [
                    f"libname sdxpt xport {_sas_quote(xpt)};",
                    f"libname sdout {_sas_quote(library)};",
                    "proc copy in=sdxpt out=sdout memtype=data;",
                    "  select STATDATA;",
                    "run;",
                ]
            ),
            work,
            timeout,
        )
        created = next(library.glob("*.sas7bdat"), None)
        if not created:
            raise RuntimeError("SAS did not create the requested SAS7BDAT file.")
        shutil.move(str(created), destination)
    return {
        "status": "ok",
        "changes": [
            {
                "severity": "warning",
                "code": "sas.bridge_xport_interchange",
                "message": (
                    "SAS7BDAT output was created by local SAS through a temporary "
                    "XPORT v8 table. Destination opening and metadata fidelity "
                    "remain unverified."
                ),
                "columns": [],
            }
        ],
    }


def _cport_read(request: dict[str, Any]) -> dict[str, Any]:
    source = Path(request["input_path"]).resolve()
    package = Path(request["package_path"]).resolve()
    options = request.get("options") or {}
    timeout = float(options.get("timeout_seconds", 300))
    requested_member = (
        _member(str(options["member"])) if options.get("member") else None
    )
    with tempfile.TemporaryDirectory(prefix="statdata-cimport-") as value:
        work = Path(value)
        library = work / "library"
        library.mkdir()
        _run_sas(
            "\n".join(
                [
                    f"filename sdin {_sas_quote(source)};",
                    f"libname sdlib {_sas_quote(library)};",
                    "proc cimport infile=sdin library=sdlib memtype=data;",
                    "run;",
                ]
            ),
            work,
            timeout,
        )
        datasets = sorted(library.glob("*.sas7bdat"))
        if requested_member:
            datasets = [
                item for item in datasets if item.stem.upper() == requested_member
            ]
        if not datasets:
            raise RuntimeError(
                "The CPORT file did not yield a selectable SAS data set."
            )
        selected = datasets[0]
        dataset = ReadStatAdapter("sas_data").read(
            selected,
            {},
            _report("sas_cport", "package"),
        )
        profile_temporal_columns(dataset)
        dataset.metadata.extra["sas_cport_members"] = [
            item.stem for item in sorted(library.glob("*.sas7bdat"))
        ]
        write_dataset_package(dataset, package)
    return {
        "status": "ok",
        "changes": [
            {
                "severity": "warning" if len(datasets) > 1 else "info",
                "code": "sas.cport_member_selected",
                "message": (
                    f"Selected SAS data set {selected.stem} from the CPORT archive. "
                    "Catalogs and additional members are outside the one-table model."
                ),
                "columns": [],
            }
        ],
    }


def _cport_write(request: dict[str, Any]) -> dict[str, Any]:
    destination = Path(request["output_path"]).resolve()
    if destination.exists():
        raise FileExistsError("The SAS bridge will not overwrite an existing file.")
    options = request.get("options") or {}
    timeout = float(options.get("timeout_seconds", 300))
    member = _member(str(options.get("member", "STATDATA")))
    with tempfile.TemporaryDirectory(prefix="statdata-cport-") as value:
        work = Path(value)
        library = work / "library"
        library.mkdir()
        xpt = work / "statdata.xpt"
        _write_xport_from_package(Path(request["package_path"]).resolve(), xpt)
        _run_sas(
            "\n".join(
                [
                    f"libname sdxpt xport {_sas_quote(xpt)};",
                    f"libname sdlib {_sas_quote(library)};",
                    "proc copy in=sdxpt out=sdlib memtype=data;",
                    "  select STATDATA;",
                    "run;",
                    f"data sdlib.{member}; set sdlib.STATDATA; run;",
                    f"filename sdout {_sas_quote(destination)};",
                    f"proc cport data=sdlib.{member} file=sdout;",
                    "run;",
                ]
            ),
            work,
            timeout,
        )
    if not destination.is_file():
        raise RuntimeError("SAS did not create the requested CPORT file.")
    return {
        "status": "ok",
        "changes": [
            {
                "severity": "warning",
                "code": "sas.cport_single_dataset",
                "message": (
                    f"Created a CPORT archive containing data set {member}. "
                    "The canonical model does not synthesize SAS catalog entries."
                ),
                "columns": [],
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("sas_data", "sas_cport"), required=True)
    parser.add_argument("action", choices=("probe", "read", "write"))
    args = parser.parse_args()
    try:
        request = json.load(sys.stdin)
        if request.get("protocol_version") != PROTOCOL_VERSION:
            raise ValueError("Unsupported bridge protocol version.")
        status = detect_vendor_runtime("sas")
        if not status.detected:
            raise FileNotFoundError(status.detail)
        if args.action == "probe":
            result = {
                "status": "ok",
                "protocol_version": PROTOCOL_VERSION,
                "version": f"{BRIDGE_VERSION} / SAS {status.version or 'detected'}",
                "can_read": True,
                "can_write": True,
            }
        elif args.format == "sas_data" and args.action == "read":
            result = _sas_data_read(request)
        elif args.format == "sas_data":
            result = _sas_data_write(request)
        elif args.action == "read":
            result = _cport_read(request)
        else:
            result = _cport_write(request)
    except Exception as exc:
        result = {"status": "error", "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
