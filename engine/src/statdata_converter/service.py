from __future__ import annotations

import json
import platform
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from . import __version__
from .adapters import AdapterError
from .adapters.bridge import bridge_home
from .bridge_management import install_bridge
from .certification import (
    audit_certification_manifest,
    certification_registry,
)
from .registry import FormatRegistry
from .report import ConversionReport
from .temporal import preflight_temporal_conversion, profile_temporal_columns
from .validation import compare_datasets, write_validation_result
from .vendor import detect_vendor_runtimes


class ConversionService:
    def __init__(self, registry: FormatRegistry | None = None) -> None:
        self.registry = registry or FormatRegistry()

    def capabilities(self) -> dict[str, Any]:
        return {
            "engine_version": __version__,
            "python_version": platform.python_version(),
            "formats": self.registry.capabilities(),
            "privacy": {
                "local_only": True,
                "network_access": False,
            },
            "bridges": [status.to_dict() for status in self.registry.bridge_statuses],
            "vendor_runtimes": [
                status.to_dict() for status in detect_vendor_runtimes()
            ],
            "certifications": [
                status.to_dict() for status in certification_registry()
            ],
        }

    def bridge_diagnostics(self) -> dict[str, Any]:
        capabilities = self.capabilities()
        return {
            "bridge_directory": str(bridge_home().resolve()),
            "installed_bridges": capabilities["bridges"],
            "vendor_runtimes": capabilities["vendor_runtimes"],
            "summary": {
                "installed": len(capabilities["bridges"]),
                "ready": sum(
                    1 for item in capabilities["bridges"] if item["available"]
                ),
                "vendor_runtimes_detected": sum(
                    1
                    for item in capabilities["vendor_runtimes"]
                    if item["detected"]
                ),
            },
        }

    def install_bridge(self, manifest_path: str | Path) -> dict[str, Any]:
        result = install_bridge(manifest_path)
        self.registry = FormatRegistry()
        return {
            **result,
            "diagnostics": self.bridge_diagnostics(),
            "capabilities": self.capabilities(),
        }

    @staticmethod
    def audit_certification(manifest_path: str | Path) -> dict[str, Any]:
        return audit_certification_manifest(manifest_path)

    def convert(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        input_format: str | None = None,
        output_format: str | None = None,
        input_options: dict[str, Any] | None = None,
        output_options: dict[str, Any] | None = None,
        report_path: str | Path | None = None,
    ) -> dict[str, Any]:
        source = Path(input_path).expanduser().resolve()
        destination = Path(output_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Input file does not exist: {source}")
        if source == destination:
            raise ValueError("Input and output paths must be different.")

        reader = (
            self.registry.get(input_format)
            if input_format
            else self.registry.detect(source)
        )
        writer = (
            self.registry.get(output_format)
            if output_format
            else self.registry.detect(destination)
        )
        report = ConversionReport(
            input_path=str(source),
            output_path=str(destination),
            input_format=reader.capability.id,
            output_format=writer.capability.id,
            engine={
                "statdata_converter": __version__,
                "python": platform.python_version(),
                "pandas": pd.__version__,
            },
        )

        report_destination = (
            Path(report_path).expanduser().resolve()
            if report_path
            else destination.with_name(destination.name + ".statdata-report.json")
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        report_destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            if not reader.capability.can_read:
                raise AdapterError(
                    reader.capability.detail
                    or f"{reader.capability.label} cannot currently be read."
                )
            if not writer.capability.can_write:
                raise AdapterError(
                    writer.capability.detail
                    or f"{writer.capability.label} cannot currently be written."
                )
            dataset = reader.read(source, input_options or {}, report)
            resolved_output_options = output_options or {}
            preflight_temporal_conversion(
                dataset,
                writer.capability.id,
                resolved_output_options,
                report,
            )
            writer.analyze_metadata(dataset, report)
            writer.write(dataset, destination, resolved_output_options, report)
            report.complete(len(dataset.frame.index), len(dataset.frame.columns))
        except Exception as exc:
            report.fail(str(exc))
            self._write_report(report_destination, report.to_dict())
            raise

        result = report.to_dict()
        self._write_report(report_destination, result)
        return {
            "output_path": str(destination),
            "report_path": str(report_destination),
            "report": result,
        }

    def validate(
        self,
        input_path: str | Path,
        target_format: str,
        *,
        artifact_directory: str | Path | None = None,
        input_format: str | None = None,
        input_options: dict[str, Any] | None = None,
        output_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        source = Path(input_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Input file does not exist: {source}")
        reader = (
            self.registry.get(input_format)
            if input_format
            else self.registry.detect(source)
        )
        target = self.registry.get(target_format)
        if not target.capability.can_write or not target.capability.can_read:
            raise ValueError(
                f"{target.capability.label} must support both reading and writing "
                "for round-trip validation."
            )

        artifacts = (
            Path(artifact_directory).expanduser().resolve()
            if artifact_directory
            else source.parent / "statdata-validation"
        )
        artifacts.mkdir(parents=True, exist_ok=True)
        extension = target.capability.extensions[0]
        base_name = f"{source.stem}__roundtrip__{target.capability.id}"
        destination = artifacts / f"{base_name}{extension}"
        suffix = 2
        while destination.exists():
            destination = artifacts / f"{base_name}-{suffix}{extension}"
            suffix += 1
        conversion_report_path = destination.with_name(
            destination.name + ".statdata-report.json"
        )
        validation_path = destination.with_name(
            destination.name + ".statdata-validation.json"
        )
        started_at = datetime.now(UTC).isoformat()
        evidence = {
            "schema_version": 1,
            "engine": {
                "statdata_converter": __version__,
                "python": platform.python_version(),
                "pandas": pd.__version__,
            },
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
            },
            "source_adapter": {
                "id": reader.capability.id,
                "label": reader.capability.label,
                "trust": reader.capability.trust,
                "availability": reader.capability.availability,
            },
            "target_adapter": {
                "id": target.capability.id,
                "label": target.capability.label,
                "trust": target.capability.trust,
                "availability": target.capability.availability,
            },
            "bridges": [
                status.to_dict()
                for status in self.registry.bridge_statuses
                if status.format_id in {reader.capability.id, target.capability.id}
            ],
            "vendor_runtimes": [
                status.to_dict() for status in detect_vendor_runtimes()
            ],
            "temporal": {
                "source_columns": [],
                "conversion_decisions": [],
            },
        }

        try:
            source_report = ConversionReport(
                input_path=str(source),
                output_path=str(destination),
                input_format=reader.capability.id,
                output_format=target.capability.id,
            )
            expected = reader.read(source, input_options or {}, source_report)
            evidence["temporal"]["source_columns"] = [
                asdict(profile)
                for profile in profile_temporal_columns(expected).values()
            ]
            conversion = self.convert(
                source,
                destination,
                input_format=reader.capability.id,
                output_format=target.capability.id,
                input_options=input_options,
                output_options=output_options,
                report_path=conversion_report_path,
            )
            evidence["temporal"]["conversion_decisions"] = conversion["report"][
                "temporal"
            ]
            readback_report = ConversionReport(
                input_path=str(destination),
                output_path=str(source),
                input_format=target.capability.id,
                output_format=reader.capability.id,
            )
            actual = target.read(destination, {}, readback_report)
            comparison = compare_datasets(expected, actual)
            status = "passed" if comparison["data_equivalent"] else "failed"
            result = {
                "status": status,
                "started_at": started_at,
                "finished_at": datetime.now(UTC).isoformat(),
                "input_path": str(source),
                "input_format": reader.capability.id,
                "target_format": target.capability.id,
                "artifact_path": str(destination),
                "conversion_report_path": str(conversion_report_path),
                "validation_path": str(validation_path),
                "data_equivalent": comparison["data_equivalent"],
                "metadata_equivalent": comparison["metadata_equivalent"],
                "lossless": (
                    comparison["data_equivalent"]
                    and comparison["metadata_equivalent"]
                    and conversion["report"]["lossless"]
                ),
                "rows": len(expected.frame.index),
                "columns": len(expected.frame.columns),
                "evidence": evidence,
                "issues": comparison["issues"],
                "summary": {
                    **comparison["summary"],
                    "conversion_warnings": conversion["report"]["summary"]["warning"],
                    "conversion_errors": conversion["report"]["summary"]["error"],
                },
            }
        except Exception as exc:
            result = {
                "status": "failed",
                "started_at": started_at,
                "finished_at": datetime.now(UTC).isoformat(),
                "input_path": str(source),
                "input_format": reader.capability.id,
                "target_format": target.capability.id,
                "artifact_path": (str(destination) if destination.exists() else None),
                "conversion_report_path": (
                    str(conversion_report_path)
                    if conversion_report_path.exists()
                    else None
                ),
                "validation_path": str(validation_path),
                "data_equivalent": False,
                "metadata_equivalent": False,
                "lossless": False,
                "rows": 0,
                "columns": 0,
                "evidence": evidence,
                "issues": [
                    {
                        "severity": "error",
                        "scope": "validation",
                        "code": "validation_failed",
                        "message": str(exc),
                    }
                ],
                "summary": {
                    "data_issues": 1,
                    "metadata_issues": 0,
                    "conversion_warnings": 0,
                    "conversion_errors": 1,
                },
            }
        write_validation_result(validation_path, result)
        return result

    @staticmethod
    def _write_report(path: Path, report: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
