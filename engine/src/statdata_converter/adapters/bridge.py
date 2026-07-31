from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..models import Dataset
from ..package import read_dataset_package, write_dataset_package
from ..report import ConversionReport
from .base import Adapter, AdapterError, FormatCapability

BRIDGE_PROTOCOL_VERSION = 1
BRIDGE_ENVIRONMENT = "STATDATA_BRIDGE_PATH"
BRIDGE_HOME_ENVIRONMENT = "STATDATA_BRIDGE_HOME"


def bridge_home() -> Path:
    configured = os.environ.get(BRIDGE_HOME_ENVIRONMENT)
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".statdata-converter" / "bridges"


@dataclass(frozen=True, slots=True)
class BridgeStatus:
    name: str
    manifest_path: str
    format_id: str | None
    available: bool
    detail: str
    version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "manifest_path": self.manifest_path,
            "format_id": self.format_id,
            "available": self.available,
            "detail": self.detail,
            "version": self.version,
        }


class ExternalBridgeAdapter(Adapter):
    def __init__(
        self,
        manifest_path: Path,
        manifest: dict[str, Any],
        probe: dict[str, Any],
    ) -> None:
        self.manifest_path = manifest_path.resolve()
        self.name = str(manifest["name"])
        executable_value = str(manifest["executable"])
        executable_path = Path(executable_value)
        if not executable_path.is_absolute():
            executable_path = self.manifest_path.parent / executable_path
        resolved = (
            str(executable_path.resolve())
            if executable_path.is_file()
            else shutil.which(executable_value)
        )
        if not resolved:
            raise AdapterError(f"Bridge executable was not found: {executable_value}")
        self.executable = resolved
        self.arguments = [str(item) for item in manifest.get("arguments", [])]
        self.timeout_seconds = float(manifest.get("timeout_seconds", 300))
        format_value = manifest["format"]
        self.capability = FormatCapability(
            id=str(format_value["id"]),
            family=str(format_value["family"]),
            label=str(format_value["label"]),
            extensions=tuple(str(item) for item in format_value["extensions"]),
            can_read=bool(probe.get("can_read", format_value.get("can_read", False))),
            can_write=bool(
                probe.get("can_write", format_value.get("can_write", False))
            ),
            trust=str(format_value.get("trust", "experimental")),
            availability="available",
            detail=(
                f"Provided by the local {self.name} bridge"
                + (f" {probe['version']}" if probe.get("version") else "")
                + "."
            ),
            requires=(self.name,),
        )
        self.metadata_features = frozenset(
            str(item) for item in format_value.get("metadata_features", [])
        )

    def _invoke(self, action: str, request: dict[str, Any]) -> dict[str, Any]:
        completed = subprocess.run(
            [self.executable, *self.arguments, action],
            input=json.dumps(request, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=self.manifest_path.parent,
            timeout=self.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise AdapterError(
                detail or f"The {self.name} bridge failed during {action}."
            )
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise AdapterError(
                f"The {self.name} bridge returned invalid JSON."
            ) from exc
        if not isinstance(response, dict):
            raise AdapterError(f"The {self.name} bridge returned no result object.")
        if response.get("status") != "ok":
            raise AdapterError(
                str(response.get("error") or f"The {self.name} bridge failed.")
            )
        return response

    def _record_response(
        self,
        response: dict[str, Any],
        report: ConversionReport,
    ) -> None:
        report.add(
            "warning",
            "bridge.external_unverified",
            f"The conversion used the separately installed {self.name} bridge. "
            "Its fidelity must be verified with vendor-generated fixtures.",
        )
        for change in response.get("changes", []):
            if not isinstance(change, dict):
                continue
            severity = str(change.get("severity", "warning"))
            if severity not in {"info", "warning", "error"}:
                severity = "warning"
            report.add(
                severity,  # type: ignore[arg-type]
                str(change.get("code", "bridge.reported_change")),
                str(change.get("message", "The bridge reported a transformation.")),
                [str(item) for item in change.get("columns", [])],
            )

    def read(
        self,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> Dataset:
        with tempfile.TemporaryDirectory(prefix="statdata-bridge-read-") as value:
            package_path = Path(value) / "dataset.statdata-package"
            response = self._invoke(
                "read",
                {
                    "protocol_version": BRIDGE_PROTOCOL_VERSION,
                    "input_path": str(path),
                    "package_path": str(package_path),
                    "options": options,
                },
            )
            dataset = read_dataset_package(package_path)
        self._record_response(response, report)
        dataset.metadata.extra["native_format"] = self.capability.id
        return dataset

    def write(
        self,
        dataset: Dataset,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="statdata-bridge-write-") as value:
            package_path = Path(value) / "dataset.statdata-package"
            write_dataset_package(dataset, package_path)
            response = self._invoke(
                "write",
                {
                    "protocol_version": BRIDGE_PROTOCOL_VERSION,
                    "package_path": str(package_path),
                    "output_path": str(path),
                    "options": options,
                },
            )
        if not path.is_file():
            raise AdapterError(
                f"The {self.name} bridge did not create the requested output file."
            )
        self._record_response(response, report)


def _manifest_candidates(paths: Iterable[Path] | None = None) -> list[Path]:
    configured = list(paths or [])
    if not configured:
        environment = os.environ.get(BRIDGE_ENVIRONMENT, "")
        configured.extend(
            Path(item).expanduser()
            for item in environment.split(os.pathsep)
            if item.strip()
        )
        configured.append(bridge_home())
    candidates: list[Path] = []
    for entry in configured:
        if entry.is_file():
            candidates.append(entry)
        elif entry.is_dir():
            candidates.extend(sorted(entry.glob("*.statdata-bridge.json")))
            candidates.extend(sorted(entry.glob("*/bridge.json")))
    return list(dict.fromkeys(candidate.resolve() for candidate in candidates))


def discover_bridges(
    paths: Iterable[Path] | None = None,
) -> tuple[list[ExternalBridgeAdapter], list[BridgeStatus]]:
    adapters: list[ExternalBridgeAdapter] = []
    statuses: list[BridgeStatus] = []
    for manifest_path in _manifest_candidates(paths):
        name = manifest_path.stem
        format_id: str | None = None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("protocol_version") != BRIDGE_PROTOCOL_VERSION:
                raise AdapterError(
                    "The bridge manifest uses an unsupported protocol version."
                )
            name = str(manifest["name"])
            format_id = str(manifest["format"]["id"])
            executable_value = str(manifest["executable"])
            executable_path = Path(executable_value)
            if not executable_path.is_absolute():
                executable_path = manifest_path.parent / executable_path
            executable = (
                str(executable_path.resolve())
                if executable_path.is_file()
                else shutil.which(executable_value)
            )
            if not executable:
                raise AdapterError(
                    f"Bridge executable was not found: {executable_value}"
                )
            completed = subprocess.run(
                [
                    executable,
                    *[str(item) for item in manifest.get("arguments", [])],
                    "probe",
                ],
                input=json.dumps(
                    {"protocol_version": BRIDGE_PROTOCOL_VERSION},
                    ensure_ascii=False,
                ),
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=manifest_path.parent,
                timeout=min(float(manifest.get("timeout_seconds", 300)), 10),
                check=False,
            )
            if completed.returncode != 0:
                raise AdapterError(
                    completed.stderr.strip()
                    or completed.stdout.strip()
                    or "Bridge probe failed."
                )
            probe = json.loads(completed.stdout)
            if not isinstance(probe, dict):
                raise AdapterError("Bridge probe returned no result object.")
            if probe.get("status") != "ok":
                raise AdapterError(
                    str(probe.get("error") or "Bridge probe failed.")
                )
            if probe.get("protocol_version") != BRIDGE_PROTOCOL_VERSION:
                raise AdapterError("Bridge probe returned an incompatible response.")
            adapter = ExternalBridgeAdapter(manifest_path, manifest, probe)
            adapters.append(adapter)
            statuses.append(
                BridgeStatus(
                    name=name,
                    manifest_path=str(manifest_path),
                    format_id=format_id,
                    available=True,
                    detail="Bridge detected and protocol probe passed.",
                    version=(
                        str(probe["version"]) if probe.get("version") else None
                    ),
                )
            )
        except Exception as exc:
            statuses.append(
                BridgeStatus(
                    name=name,
                    manifest_path=str(manifest_path),
                    format_id=format_id,
                    available=False,
                    detail=str(exc),
                )
            )
    return adapters, statuses
