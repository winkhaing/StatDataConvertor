import hashlib
import json

from statdata_converter.certification import (
    audit_certification_manifest,
    certification_registry,
)
from statdata_converter.service import ConversionService


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _evidence_package(tmp_path, *, opening_passed=True):
    fixture = tmp_path / "fixture.jmp"
    fixture.write_bytes(b"independent-vendor-fixture")
    validation = tmp_path / "validation.json"
    validation.write_text(
        json.dumps(
            {
                "status": "passed",
                "input_format": "csv",
                "target_format": "jmp",
                "data_equivalent": True,
                "metadata_equivalent": False,
                "lossless": False,
            }
        ),
        encoding="utf-8",
    )
    report = tmp_path / "conversion-report.json"
    report.write_text(
        json.dumps(
            {
                "status": "completed",
                "input_format": "csv",
                "output_format": "jmp",
                "lossless": False,
                "changes": [
                    {
                        "severity": "warning",
                        "code": "jmp.column_property_omitted",
                        "message": "A column property was omitted.",
                        "columns": ["category"],
                    }
                ],
                "temporal": [],
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "certification.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "format_id": "jmp",
                "direction": "write",
                "vendor": {
                    "product": "JMP",
                    "version": "18",
                    "operating_system": "Windows 11",
                },
                "fixture": {
                    "path": fixture.name,
                    "sha256": _sha256(fixture),
                },
                "validation_result": {
                    "path": validation.name,
                    "sha256": _sha256(validation),
                },
                "conversion_report": {
                    "path": report.name,
                    "sha256": _sha256(report),
                },
                "destination_opening": {
                    "passed": opening_passed,
                    "application_version": "18",
                    "notes": "Opened without repair messages.",
                },
                "expected_transformations": [
                    "jmp.column_property_omitted"
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_registry_never_claims_vendor_certification_without_evidence() -> None:
    statuses = certification_registry()

    assert statuses
    assert not any(
        direction.certified
        for status in statuses
        for direction in (status.read, status.write)
    )
    capability_statuses = ConversionService().capabilities()["certifications"]
    jmp = next(item for item in capability_statuses if item["format_id"] == "jmp")
    assert jmp["read"]["state"] == "fixture_tested"
    assert jmp["write"]["state"] == "pending"


def test_audit_accepts_complete_evidence_with_documented_changes(
    tmp_path,
) -> None:
    result = audit_certification_manifest(_evidence_package(tmp_path))

    assert result["status"] == "passed"
    assert result["eligible_for_registry_review"] is True
    assert result["claim"] == "verified_with_documented_changes"
    assert result["data_equivalent"] is True
    assert result["metadata_equivalent"] is False
    assert result["summary"] == {"errors": 0, "warnings": 0}


def test_audit_rejects_hash_mismatch(tmp_path) -> None:
    manifest = _evidence_package(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["fixture"]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = audit_certification_manifest(manifest)

    assert result["status"] == "failed"
    assert "evidence.hash_mismatch" in {
        issue["code"] for issue in result["issues"]
    }


def test_write_audit_requires_vendor_opening_check(tmp_path) -> None:
    result = audit_certification_manifest(
        _evidence_package(tmp_path, opening_passed=False)
    )

    assert result["status"] == "failed"
    assert "vendor_opening.not_passed" in {
        issue["code"] for issue in result["issues"]
    }


def test_audit_rejects_unknown_format(tmp_path) -> None:
    manifest = _evidence_package(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["format_id"] = "invented"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = audit_certification_manifest(manifest)

    assert result["status"] == "failed"
    assert "manifest.format_unknown" in {
        issue["code"] for issue in result["issues"]
    }


def test_audit_requires_reported_transformations_to_match(tmp_path) -> None:
    manifest = _evidence_package(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["expected_transformations"] = []
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = audit_certification_manifest(manifest)

    assert result["status"] == "failed"
    assert "report.transformations_mismatch" in {
        issue["code"] for issue in result["issues"]
    }


def test_audit_rejects_symbolic_linked_evidence(tmp_path) -> None:
    manifest = _evidence_package(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    linked = tmp_path / "linked-validation.json"
    linked.symlink_to(tmp_path / "validation.json")
    payload["validation_result"]["path"] = linked.name
    payload["validation_result"]["sha256"] = _sha256(linked)
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = audit_certification_manifest(manifest)

    assert result["status"] == "failed"
    assert "evidence.file_invalid" in {
        issue["code"] for issue in result["issues"]
    }
