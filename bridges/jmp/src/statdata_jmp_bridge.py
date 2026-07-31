from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = 1
BRIDGE_VERSION = "0.10.0"
JMP_EXECUTABLE_ENV = "STATDATA_JMP_EXECUTABLE"


def _resource(name: str) -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled) / name
    return Path(__file__).resolve().with_name(name)


def _candidate_executables() -> list[Path]:
    configured = os.environ.get(JMP_EXECUTABLE_ENV)
    if configured:
        return [Path(configured).expanduser()]

    candidates: list[Path] = []
    if sys.platform == "darwin":
        for application_root in (
            Path("/Applications"),
            Path.home() / "Applications",
        ):
            if not application_root.is_dir():
                continue
            for application in sorted(application_root.glob("JMP*.app")):
                executable_root = application / "Contents" / "MacOS"
                if executable_root.is_dir():
                    candidates.extend(
                        item
                        for item in sorted(executable_root.iterdir())
                        if item.is_file()
                        and "jmp" in item.name.lower()
                        and os.access(item, os.X_OK)
                    )
    elif os.name == "nt":
        roots = [
            Path(value)
            for value in (
                os.environ.get("ProgramFiles"),
                os.environ.get("ProgramFiles(x86)"),
            )
            if value
        ]
        patterns = (
            "SAS/JMP/*/jmp.exe",
            "SAS/JMPPRO/*/jmp.exe",
            "JMP/JMP/*/jmp.exe",
            "JMP/JMPPRO/*/jmp.exe",
        )
        for root in roots:
            for pattern in patterns:
                candidates.extend(sorted(root.glob(pattern)))
    else:
        for root in (Path("/opt"), Path("/usr/local")):
            if root.is_dir():
                candidates.extend(sorted(root.glob("**/jmp")))
    return candidates


def find_jmp_executable() -> Path:
    for candidate in _candidate_executables():
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "JMP was not detected. Set STATDATA_JMP_EXECUTABLE to the local "
        "JMP application executable."
    )


def _detected_version(executable: Path) -> str:
    for part in reversed(executable.parts):
        match = re.search(r"\b(\d{2}(?:\.\d+)?)\b", part)
        if match:
            return match.group(1)
    return "detected"


def _field_names(table_document: dict[str, Any]) -> list[str]:
    return [
        str(field["name"])
        for field in table_document.get("schema", {}).get("fields", [])
        if field.get("name") != "index"
    ]


def package_to_csv(package_path: Path, csv_path: Path) -> None:
    manifest = json.loads(
        package_path.joinpath("manifest.json").read_text(encoding="utf-8")
    )
    table_document = json.loads(
        package_path.joinpath(str(manifest["data"])).read_text(encoding="utf-8")
    )
    columns = _field_names(table_document)
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for record in table_document.get("data", []):
            writer.writerow(
                {
                    column: ("" if record.get(column) is None else record.get(column))
                    for column in columns
                }
            )


def _infer(values: list[str]) -> tuple[str, list[Any]]:
    populated = [value for value in values if value != ""]
    if not populated:
        return "string", [None for _ in values]
    lowered = [value.lower() for value in populated]
    if all(value in {"true", "false"} for value in lowered):
        return (
            "boolean",
            [None if value == "" else value.lower() == "true" for value in values],
        )
    try:
        converted = [None if value == "" else int(value) for value in values]
        return "integer", converted
    except ValueError:
        pass
    try:
        converted = [None if value == "" else float(value) for value in values]
        return "number", converted
    except ValueError:
        return "string", [None if value == "" else value for value in values]


def csv_to_package(
    csv_path: Path,
    package_path: Path,
    *,
    table_name: str,
) -> None:
    with csv_path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        columns = [str(column) for column in (reader.fieldnames or [])]
        source_rows = list(reader)
    inferred: dict[str, list[Any]] = {}
    fields: list[dict[str, str]] = []
    for column in columns:
        field_type, values = _infer([str(row.get(column, "")) for row in source_rows])
        inferred[column] = values
        fields.append({"name": column, "type": field_type})
    records = [
        {column: inferred[column][index] for column in columns}
        for index in range(len(source_rows))
    ]

    package_path.mkdir(parents=True, exist_ok=False)
    package_path.joinpath("data.json").write_text(
        json.dumps(
            {
                "schema": {
                    "fields": fields,
                    "pandas_version": "1.4.0",
                },
                "data": records,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    package_path.joinpath("metadata.json").write_text(
        json.dumps(
            {
                "dataset_label": None,
                "table_name": table_name,
                "source": None,
                "updated": None,
                "column_labels": {},
                "value_labels": {},
                "missing_values": {},
                "missing_ranges": {},
                "formats": {},
                "measures": {},
                "notes": [],
                "extra": {"native_format": "jmp"},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    package_path.joinpath("manifest.json").write_text(
        json.dumps(
            {
                "package_version": 1,
                "data": "data.json",
                "metadata": "metadata.json",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _run_jsl(
    executable: Path,
    *,
    action: str,
    source_path: Path,
    destination_path: Path,
    timeout_seconds: float,
) -> None:
    with tempfile.TemporaryDirectory(prefix="statdata-jmp-jsl-") as value:
        status_path = Path(value) / "status.txt"
        environment = os.environ.copy()
        environment.update(
            {
                "STATDATA_JMP_ACTION": action,
                "STATDATA_JMP_SOURCE": str(source_path),
                "STATDATA_JMP_DESTINATION": str(destination_path),
                "STATDATA_JMP_STATUS": str(status_path),
            }
        )
        process = subprocess.Popen(
            [str(executable), str(_resource("jmp_bridge.jsl"))],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if status_path.is_file():
                status = status_path.read_text(encoding="utf-8").strip()
                if status == "ok":
                    return
                raise RuntimeError(
                    "JMP reported that the bridge script could not complete."
                )
            if process.poll() not in {None, 0}:
                detail = process.stderr.read().strip() if process.stderr else ""
                raise RuntimeError(detail or "JMP could not run the bridge script.")
            time.sleep(0.2)
        raise TimeoutError(
            "Timed out waiting for JMP. Check JMP for a license or security prompt."
        )


def probe() -> dict[str, Any]:
    executable = find_jmp_executable()
    return {
        "status": "ok",
        "protocol_version": PROTOCOL_VERSION,
        "version": f"{BRIDGE_VERSION} / JMP {_detected_version(executable)}",
        "can_read": True,
        "can_write": True,
    }


def read(request: dict[str, Any]) -> dict[str, Any]:
    executable = find_jmp_executable()
    input_path = Path(request["input_path"]).resolve()
    package_path = Path(request["package_path"]).resolve()
    timeout_seconds = float((request.get("options") or {}).get("timeout_seconds", 120))
    with tempfile.TemporaryDirectory(prefix="statdata-jmp-read-") as value:
        csv_path = Path(value) / "jmp-export.csv"
        _run_jsl(
            executable,
            action="read",
            source_path=input_path,
            destination_path=csv_path,
            timeout_seconds=timeout_seconds,
        )
        if not csv_path.is_file():
            raise RuntimeError("JMP did not create the expected interchange file.")
        csv_to_package(csv_path, package_path, table_name=input_path.stem)
    return {
        "status": "ok",
        "changes": [
            {
                "severity": "warning",
                "code": "jmp.bridge_metadata_not_extracted",
                "message": (
                    "The initial JMP bridge extracts table values and column names. "
                    "Column properties, row states, table scripts, labels, and "
                    "JMP-specific modeling metadata are not yet extracted."
                ),
                "columns": [],
            },
            {
                "severity": "warning",
                "code": "jmp.bridge_types_inferred",
                "message": ("Storage types were inferred from JMP's UTF-8 CSV export."),
                "columns": [],
            },
        ],
    }


def write(request: dict[str, Any]) -> dict[str, Any]:
    executable = find_jmp_executable()
    package_path = Path(request["package_path"]).resolve()
    output_path = Path(request["output_path"]).resolve()
    if output_path.exists():
        raise FileExistsError(
            "The JMP bridge will not overwrite an existing output file."
        )
    timeout_seconds = float((request.get("options") or {}).get("timeout_seconds", 120))
    with tempfile.TemporaryDirectory(prefix="statdata-jmp-write-") as value:
        csv_path = Path(value) / "statdata-import.csv"
        package_to_csv(package_path, csv_path)
        _run_jsl(
            executable,
            action="write",
            source_path=csv_path,
            destination_path=output_path,
            timeout_seconds=timeout_seconds,
        )
    return {
        "status": "ok",
        "changes": [
            {
                "severity": "warning",
                "code": "jmp.bridge_tabular_projection",
                "message": (
                    "The initial JMP bridge writes values and column names through "
                    "UTF-8 CSV. JMP storage types are inferred and JMP-specific "
                    "column properties are not synthesized."
                ),
                "columns": [],
            }
        ],
    }


def main() -> int:
    try:
        action = sys.argv[1]
        request = json.load(sys.stdin)
        if request.get("protocol_version") != PROTOCOL_VERSION:
            raise ValueError("Unsupported bridge protocol version.")
        if action == "probe":
            result = probe()
        elif action == "read":
            result = read(request)
        elif action == "write":
            result = write(request)
        else:
            raise ValueError(f"Unknown JMP bridge action: {action}")
    except Exception as exc:
        result = {"status": "error", "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
