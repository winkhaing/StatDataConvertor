from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .adapters.bridge import (
    BRIDGE_PROTOCOL_VERSION,
    bridge_home,
    discover_bridges,
)

MAX_BRIDGE_FILES = 128
MAX_BRIDGE_BYTES = 512 * 1024 * 1024


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized[:48] or "local"


def _read_manifest(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError("Bridge manifests cannot be symbolic links.")
    if not path.is_file():
        raise FileNotFoundError(f"Bridge manifest does not exist: {path}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("The selected bridge manifest is not valid JSON.") from exc
    if not isinstance(manifest, dict):
        raise ValueError("The selected bridge manifest must contain a JSON object.")
    if manifest.get("protocol_version") != BRIDGE_PROTOCOL_VERSION:
        raise ValueError("The bridge uses an unsupported protocol version.")
    for field in ("name", "executable", "format"):
        if field not in manifest:
            raise ValueError(f"The bridge manifest is missing {field!r}.")
    format_value = manifest["format"]
    if not isinstance(format_value, dict) or not format_value.get("id"):
        raise ValueError("The bridge manifest has no valid format identifier.")
    return manifest


def _check_bundle(source_root: Path) -> tuple[int, int]:
    file_count = 0
    total_bytes = 0
    for item in source_root.rglob("*"):
        if item.is_symlink():
            raise ValueError(
                "Bridge bundles containing symbolic links cannot be installed."
            )
        if item.is_dir():
            continue
        if not item.is_file():
            raise ValueError("The bridge bundle contains an unsupported file type.")
        file_count += 1
        total_bytes += item.stat().st_size
        if file_count > MAX_BRIDGE_FILES:
            raise ValueError(
                f"The bridge bundle exceeds the {MAX_BRIDGE_FILES}-file safety limit."
            )
        if total_bytes > MAX_BRIDGE_BYTES:
            raise ValueError("The bridge bundle exceeds the 512 MB safety limit.")
    return file_count, total_bytes


def install_bridge(manifest_path: str | Path) -> dict[str, Any]:
    selected_manifest = Path(manifest_path).expanduser()
    if not selected_manifest.is_absolute():
        selected_manifest = Path.cwd() / selected_manifest
    manifest = _read_manifest(selected_manifest)
    source_manifest = selected_manifest.resolve()
    source_root = source_manifest.parent
    file_count, total_bytes = _check_bundle(source_root)

    name = str(manifest["name"]).strip()
    format_id = str(manifest["format"]["id"]).strip()
    destination_root = bridge_home().resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    destination = destination_root / f"{_slug(format_id)}-{_slug(name)}"
    if destination.exists():
        raise FileExistsError(
            "This bridge is already installed. Remove the existing bridge folder "
            "before installing a replacement."
        )

    staging = Path(
        tempfile.mkdtemp(prefix=".installing-", dir=destination_root)
    )
    try:
        shutil.copytree(source_root, staging, dirs_exist_ok=True, symlinks=False)
        copied_manifest = staging / source_manifest.name
        installed_manifest = staging / "bridge.json"
        if copied_manifest != installed_manifest:
            if installed_manifest.exists():
                raise ValueError(
                    "The bridge bundle contains more than one primary manifest."
                )
            copied_manifest.replace(installed_manifest)
        staging.replace(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    final_manifest = destination / "bridge.json"
    _adapters, statuses = discover_bridges([final_manifest])
    bridge_status = statuses[0].to_dict() if statuses else {
        "name": name,
        "manifest_path": str(final_manifest),
        "format_id": format_id,
        "available": False,
        "detail": "The installed bridge could not be discovered.",
        "version": None,
    }
    return {
        "status": "installed",
        "name": name,
        "format_id": format_id,
        "manifest_path": str(final_manifest),
        "file_count": file_count,
        "size_bytes": total_bytes,
        "bridge": bridge_status,
    }
