from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

CERTIFICATION_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class DirectionCertification:
    state: str
    certified: bool
    tested_versions: tuple[str, ...]
    evidence_count: int
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FormatCertification:
    format_id: str
    family: str
    label: str
    read: DirectionCertification
    write: DirectionCertification

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_id": self.format_id,
            "family": self.family,
            "label": self.label,
            "read": self.read.to_dict(),
            "write": self.write.to_dict(),
        }


def _pending(detail: str) -> DirectionCertification:
    return DirectionCertification("pending", False, (), 0, detail)


def _fixture_tested(
    versions: tuple[str, ...],
    evidence_count: int,
    detail: str,
) -> DirectionCertification:
    return DirectionCertification(
        "fixture_tested",
        False,
        versions,
        evidence_count,
        detail,
    )


def certification_registry() -> list[FormatCertification]:
    pending_bridge = (
        "Awaiting independently generated vendor fixtures, a successful "
        "destination-opening check, and maintainer review."
    )
    return [
        FormatCertification(
            "jmp",
            "JMP",
            "JMP data table",
            _fixture_tested(
                ("17.2", "18.2.1"),
                2,
                "The open reader has native JMP fixtures, but this is not a "
                "vendor certification.",
            ),
            _pending(pending_bridge),
        ),
        FormatCertification(
            "sas_data",
            "SAS",
            "SAS data file",
            _pending(pending_bridge),
            _pending(pending_bridge),
        ),
        FormatCertification(
            "sas_cport",
            "SAS",
            "SAS CPORT",
            _pending(pending_bridge),
            _pending(pending_bridge),
        ),
        FormatCertification(
            "sas_catalog",
            "SAS",
            "SAS format catalog",
            _pending(
                "Catalog evidence must be paired with its data set and a "
                "licensed SAS runtime."
            ),
            _pending(
                "Catalog evidence must be paired with its data set and a "
                "licensed SAS runtime."
            ),
        ),
        FormatCertification(
            "minitab",
            "Minitab",
            "Modern Minitab worksheet / project",
            _pending(pending_bridge),
            _pending(pending_bridge),
        ),
        FormatCertification(
            "statistica",
            "Statistica",
            "Statistica data file",
            _pending(pending_bridge),
            _pending(pending_bridge),
        ),
        FormatCertification(
            "eviews_wf1",
            "EViews",
            "EViews binary workfile",
            _fixture_tested(
                (),
                1,
                "Vendor-published workfiles have been exercised, but the "
                "evidence is not yet a redistributable certification set.",
            ),
            _pending("Binary WF1 writing is not implemented in the open core."),
        ),
        FormatCertification(
            "eviews_wf2",
            "EViews",
            "EViews open workfile",
            _fixture_tested(
                (),
                1,
                "Automated open-format fixtures pass; vendor-release opening "
                "evidence is still pending.",
            ),
            _fixture_tested(
                (),
                1,
                "Automated round trips pass; opening app-written files in "
                "supported EViews releases is still pending.",
            ),
        ),
    ]


def _issue(
    issues: list[dict[str, str]],
    severity: str,
    code: str,
    message: str,
) -> None:
    issues.append({"severity": severity, "code": code, "message": message})


def _evidence_path(manifest_root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} path is missing.")
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError(f"{label} path must be relative to the manifest.")
    candidate = manifest_root / relative
    if candidate.is_symlink():
        raise ValueError(f"{label} file cannot be a symbolic link.")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(manifest_root)
    except ValueError as exc:
        raise ValueError(f"{label} path leaves the evidence folder.") from exc
    if not resolved.is_file():
        raise ValueError(f"{label} file does not exist.")
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _check_evidence_file(
    manifest_root: Path,
    entry: Any,
    label: str,
    issues: list[dict[str, str]],
) -> tuple[Path | None, str | None]:
    if not isinstance(entry, dict):
        _issue(issues, "error", "evidence.entry_missing", f"{label} is missing.")
        return None, None
    try:
        path = _evidence_path(manifest_root, entry.get("path"), label)
    except (FileNotFoundError, ValueError) as exc:
        _issue(issues, "error", "evidence.file_invalid", str(exc))
        return None, None
    actual = _sha256(path)
    expected = str(entry.get("sha256", "")).lower()
    if len(expected) != 64 or actual != expected:
        _issue(
            issues,
            "error",
            "evidence.hash_mismatch",
            f"{label} SHA-256 does not match the manifest.",
        )
    return path, actual


def audit_certification_manifest(manifest_path: str | Path) -> dict[str, Any]:
    selected = Path(manifest_path).expanduser()
    if not selected.is_absolute():
        selected = Path.cwd() / selected
    if selected.is_symlink() or not selected.is_file():
        raise FileNotFoundError(
            f"Certification manifest does not exist: {selected}"
        )
    manifest_path_resolved = selected.resolve()
    manifest_root = manifest_path_resolved.parent
    try:
        manifest = json.loads(manifest_path_resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("The certification manifest is not valid JSON.") from exc
    if not isinstance(manifest, dict):
        raise TypeError("The certification manifest must contain a JSON object.")

    issues: list[dict[str, str]] = []
    if manifest.get("schema_version") != CERTIFICATION_SCHEMA_VERSION:
        _issue(
            issues,
            "error",
            "manifest.schema_unsupported",
            "The certification manifest uses an unsupported schema version.",
        )
    format_id = str(manifest.get("format_id", "")).strip()
    known_format_ids = {
        status.format_id for status in certification_registry()
    }
    if format_id not in known_format_ids:
        _issue(
            issues,
            "error",
            "manifest.format_unknown",
            "The format is not present in the certification registry.",
        )
    direction = str(manifest.get("direction", "")).strip()
    if direction not in {"read", "write", "round_trip"}:
        _issue(
            issues,
            "error",
            "manifest.direction_invalid",
            "Direction must be read, write, or round_trip.",
        )
    vendor = manifest.get("vendor")
    if not isinstance(vendor, dict) or not all(
        str(vendor.get(field, "")).strip()
        for field in ("product", "version", "operating_system")
    ):
        _issue(
            issues,
            "error",
            "manifest.vendor_incomplete",
            "Vendor product, version, and operating system are required.",
        )

    fixture_path, fixture_hash = _check_evidence_file(
        manifest_root,
        manifest.get("fixture"),
        "Fixture",
        issues,
    )
    validation_path, validation_hash = _check_evidence_file(
        manifest_root,
        manifest.get("validation_result"),
        "Validation result",
        issues,
    )
    report_path, report_hash = _check_evidence_file(
        manifest_root,
        manifest.get("conversion_report"),
        "Conversion report",
        issues,
    )

    validation: dict[str, Any] | None = None
    if validation_path is not None:
        try:
            parsed = json.loads(validation_path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                raise TypeError
            validation = parsed
        except (json.JSONDecodeError, TypeError):
            _issue(
                issues,
                "error",
                "validation.invalid",
                "The validation result is not a valid JSON object.",
            )

    report: dict[str, Any] | None = None
    if report_path is not None:
        try:
            parsed = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(parsed, dict):
                raise TypeError
            report = parsed
        except (json.JSONDecodeError, TypeError):
            _issue(
                issues,
                "error",
                "report.invalid",
                "The conversion report is not a valid JSON object.",
            )

    if validation is not None:
        if validation.get("status") != "passed":
            _issue(
                issues,
                "error",
                "validation.not_passed",
                "The round-trip validation did not pass.",
            )
        if validation.get("data_equivalent") is not True:
            _issue(
                issues,
                "error",
                "validation.data_changed",
                "The validation result does not show equivalent data.",
            )
        if direction == "read" and validation.get("input_format") != format_id:
            _issue(
                issues,
                "error",
                "validation.format_mismatch",
                "Read certification requires the vendor format as input.",
            )
        if direction in {"write", "round_trip"} and validation.get(
            "target_format"
        ) != format_id:
            _issue(
                issues,
                "error",
                "validation.format_mismatch",
                "Write certification requires the vendor format as target.",
            )

    if report is not None:
        if report.get("status") != "completed":
            _issue(
                issues,
                "error",
                "report.not_completed",
                "The conversion report did not complete successfully.",
            )
        if direction == "read" and report.get("input_format") != format_id:
            _issue(
                issues,
                "error",
                "report.format_mismatch",
                "The read conversion report must use the vendor format as input.",
            )
        if direction in {"write", "round_trip"} and report.get(
            "output_format"
        ) != format_id:
            _issue(
                issues,
                "error",
                "report.format_mismatch",
                "The write conversion report must use the vendor format as output.",
            )

        expected_transformations = manifest.get("expected_transformations", [])
        if not isinstance(expected_transformations, list) or not all(
            isinstance(item, str) and item.strip()
            for item in expected_transformations
        ):
            _issue(
                issues,
                "error",
                "manifest.transformations_invalid",
                "Expected transformations must be a list of report codes.",
            )
            expected_codes: set[str] = set()
        else:
            expected_codes = set(expected_transformations)
        reported_codes = {
            str(change.get("code"))
            for change in report.get("changes", [])
            if isinstance(change, dict)
            and change.get("severity") in {"warning", "error"}
            and change.get("code")
        }
        reported_codes.update(
            str(entry.get("code"))
            for entry in report.get("temporal", [])
            if isinstance(entry, dict)
            and entry.get("outcome") != "exact"
            and entry.get("code")
        )
        if expected_codes != reported_codes:
            _issue(
                issues,
                "error",
                "report.transformations_mismatch",
                "Expected transformation codes do not match the conversion report.",
            )
        if validation is not None and bool(report.get("lossless")) != bool(
            validation.get("lossless")
        ):
            _issue(
                issues,
                "error",
                "report.lossless_mismatch",
                "The conversion report and validation result disagree on losslessness.",
            )

    opening = manifest.get("destination_opening")
    if direction in {"write", "round_trip"}:
        if not isinstance(opening, dict) or opening.get("passed") is not True:
            _issue(
                issues,
                "error",
                "vendor_opening.not_passed",
                "A passed destination-opening check is required for writing.",
            )
        elif isinstance(vendor, dict) and str(
            opening.get("application_version", "")
        ).strip() != str(vendor.get("version", "")).strip():
            _issue(
                issues,
                "error",
                "vendor_opening.version_mismatch",
                "The destination-opening version must match the vendor version.",
            )
    elif isinstance(opening, dict) and opening.get("passed") is not True:
        _issue(
            issues,
            "warning",
            "vendor_opening.not_recorded",
            "No successful vendor-application opening check was recorded.",
        )

    error_count = sum(item["severity"] == "error" for item in issues)
    metadata_equivalent = bool(
        validation and validation.get("metadata_equivalent") is True
    )
    lossless = bool(validation and validation.get("lossless") is True)
    eligible = error_count == 0
    claim = (
        "lossless_fixture"
        if eligible and lossless
        else "verified_with_documented_changes"
        if eligible
        else "not_eligible"
    )
    return {
        "status": "passed" if eligible else "failed",
        "eligible_for_registry_review": eligible,
        "claim": claim,
        "format_id": format_id,
        "direction": direction,
        "manifest_path": str(manifest_path_resolved),
        "fixture_path": str(fixture_path) if fixture_path else None,
        "validation_path": str(validation_path) if validation_path else None,
        "conversion_report_path": str(report_path) if report_path else None,
        "hashes": {
            "fixture_sha256": fixture_hash,
            "validation_sha256": validation_hash,
            "conversion_report_sha256": report_hash,
        },
        "data_equivalent": bool(
            validation and validation.get("data_equivalent") is True
        ),
        "metadata_equivalent": metadata_equivalent,
        "lossless": lossless,
        "issues": issues,
        "summary": {
            "errors": error_count,
            "warnings": sum(item["severity"] == "warning" for item in issues),
        },
    }
