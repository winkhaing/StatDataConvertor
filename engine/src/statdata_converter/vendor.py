from __future__ import annotations

import os
import re
import shutil
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VendorRuntimeStatus:
    id: str
    label: str
    detected: bool
    executable: str | None
    version: str | None
    automation: str
    detail: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class _RuntimeSpec:
    id: str
    label: str
    environment: str
    command_names: tuple[str, ...]
    automation: str


_SPECS = (
    _RuntimeSpec(
        "jmp",
        "JMP",
        "STATDATA_JMP_EXECUTABLE",
        ("jmp", "jmp.exe"),
        "JSL",
    ),
    _RuntimeSpec(
        "sas",
        "SAS",
        "STATDATA_SAS_EXECUTABLE",
        ("sas", "sas.exe"),
        "batch",
    ),
    _RuntimeSpec(
        "minitab",
        "Minitab",
        "STATDATA_MINITAB_EXECUTABLE",
        ("Mtb.exe", "Minitab.exe"),
        "Windows COM",
    ),
    _RuntimeSpec(
        "statistica",
        "Statistica",
        "STATDATA_STATISTICA_EXECUTABLE",
        ("statist.exe", "Statistica.exe"),
        "Windows COM",
    ),
)


def _application_candidates(spec: _RuntimeSpec) -> Iterable[Path]:
    if sys.platform == "darwin":
        if spec.id != "jmp":
            return ()
        values: list[Path] = []
        for root in (Path("/Applications"), Path.home() / "Applications"):
            for application in sorted(root.glob("JMP*.app")):
                executable_root = application / "Contents" / "MacOS"
                if executable_root.is_dir():
                    values.extend(
                        item
                        for item in sorted(executable_root.iterdir())
                        if item.is_file() and "jmp" in item.name.lower()
                    )
        return values
    if os.name != "nt":
        roots = (Path("/opt"), Path("/usr/local"))
        patterns = {
            "jmp": ("**/jmp",),
            "sas": ("**/sas",),
        }.get(spec.id, ())
        return [
            candidate
            for root in roots
            for pattern in patterns
            for candidate in sorted(root.glob(pattern))
        ]

    roots = [
        Path(value)
        for value in (
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
        )
        if value
    ]
    patterns = {
        "jmp": (
            "SAS/JMP/*/jmp.exe",
            "SAS/JMPPRO/*/jmp.exe",
            "JMP/JMP/*/jmp.exe",
            "JMP/JMPPRO/*/jmp.exe",
        ),
        "sas": (
            "SASHome/SASFoundation/*/sas.exe",
            "SASHome/SASFoundation/*/*/sas.exe",
        ),
        "minitab": (
            "Minitab/Minitab */Mtb.exe",
            "Minitab/Minitab */Minitab.exe",
        ),
        "statistica": (
            "Statistica/Statistica */statist.exe",
            "TIBCO/Statistica */statist.exe",
            "Spotfire/Statistica */statist.exe",
        ),
    }.get(spec.id, ())
    return [
        candidate
        for root in roots
        for pattern in patterns
        for candidate in sorted(root.glob(pattern))
    ]


def _version_from_path(path: Path) -> str | None:
    for part in reversed(path.parts):
        match = re.search(r"(?<!\d)(\d{1,2}(?:\.\d+){0,2})(?!\d)", part)
        if match:
            return match.group(1)
    return None


def detect_vendor_runtime(runtime_id: str) -> VendorRuntimeStatus:
    try:
        spec = next(item for item in _SPECS if item.id == runtime_id)
    except StopIteration as exc:
        raise ValueError(f"Unknown vendor runtime: {runtime_id}") from exc

    configured = os.environ.get(spec.environment)
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    for command in spec.command_names:
        resolved = shutil.which(command)
        if resolved:
            candidates.append(Path(resolved))
    candidates.extend(_application_candidates(spec))

    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            resolved = candidate.resolve()
            platform_note = ""
            if spec.automation == "Windows COM" and os.name != "nt":
                platform_note = " COM conversion is available only on Windows."
            return VendorRuntimeStatus(
                id=spec.id,
                label=spec.label,
                detected=True,
                executable=str(resolved),
                version=_version_from_path(resolved),
                automation=spec.automation,
                detail=(
                    f"Detected a local {spec.label} executable."
                    f"{platform_note} A compatible bridge must still pass its probe."
                ),
            )

    platform_note = (
        " This bridge is supported only on Windows."
        if spec.automation == "Windows COM"
        else ""
    )
    return VendorRuntimeStatus(
        id=spec.id,
        label=spec.label,
        detected=False,
        executable=None,
        version=None,
        automation=spec.automation,
        detail=(
            f"No local {spec.label} runtime was detected. Set {spec.environment} "
            f"to its executable after installation.{platform_note}"
        ),
    )


def detect_vendor_runtimes() -> list[VendorRuntimeStatus]:
    return [detect_vendor_runtime(spec.id) for spec in _SPECS]
