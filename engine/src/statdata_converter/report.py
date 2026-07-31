from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal


Severity = Literal["info", "warning", "error"]


@dataclass(slots=True)
class ReportChange:
    severity: Severity
    code: str
    message: str
    columns: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TemporalReportEntry:
    column: str
    source_kind: str
    source_precision: str
    source_timezone: str | None
    destination_kind: str
    destination_precision: str
    destination_timezone: str | None
    outcome: str
    code: str
    message: str


@dataclass(slots=True)
class ConversionReport:
    input_path: str
    output_path: str
    input_format: str
    output_format: str
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at: str | None = None
    status: Literal["running", "completed", "failed"] = "running"
    rows: int = 0
    columns: int = 0
    changes: list[ReportChange] = field(default_factory=list)
    temporal: list[TemporalReportEntry] = field(default_factory=list)
    engine: dict[str, str] = field(default_factory=dict)

    def add(
        self,
        severity: Severity,
        code: str,
        message: str,
        columns: list[str] | None = None,
    ) -> None:
        self.changes.append(
            ReportChange(
                severity=severity,
                code=code,
                message=message,
                columns=columns or [],
            )
        )

    def add_temporal(
        self,
        *,
        column: str,
        source_kind: str,
        source_precision: str,
        source_timezone: str | None,
        destination_kind: str,
        destination_precision: str,
        destination_timezone: str | None,
        outcome: str,
        code: str,
        message: str,
    ) -> None:
        self.temporal.append(
            TemporalReportEntry(
                column=column,
                source_kind=source_kind,
                source_precision=source_precision,
                source_timezone=source_timezone,
                destination_kind=destination_kind,
                destination_precision=destination_precision,
                destination_timezone=destination_timezone,
                outcome=outcome,
                code=code,
                message=message,
            )
        )

    def complete(self, rows: int, columns: int) -> None:
        self.rows = rows
        self.columns = columns
        self.finished_at = datetime.now(UTC).isoformat()
        self.status = "completed"

    def fail(self, message: str) -> None:
        self.add("error", "conversion_failed", message)
        self.finished_at = datetime.now(UTC).isoformat()
        self.status = "failed"

    @property
    def lossless(self) -> bool:
        return self.status == "completed" and not any(
            change.severity in {"warning", "error"} for change in self.changes
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["lossless"] = self.lossless
        value["summary"] = {
            severity: sum(change.severity == severity for change in self.changes)
            for severity in ("info", "warning", "error")
        }
        value["summary"]["temporal_columns"] = len(self.temporal)
        value["summary"]["temporal_lossy"] = sum(
            item.outcome in {"lossy", "unsupported", "unverified"}
            for item in self.temporal
        )
        return value
