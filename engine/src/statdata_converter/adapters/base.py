from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..models import Dataset
from ..report import ConversionReport


@dataclass(frozen=True, slots=True)
class FormatCapability:
    id: str
    family: str
    label: str
    extensions: tuple[str, ...]
    can_read: bool
    can_write: bool
    trust: str
    availability: str = "available"
    detail: str = ""
    requires: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["extensions"] = list(self.extensions)
        result["requires"] = list(self.requires)
        return result


class AdapterError(RuntimeError):
    pass


class Adapter(ABC):
    capability: FormatCapability
    metadata_features: frozenset[str] = frozenset()

    @abstractmethod
    def read(
        self,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> Dataset:
        raise NotImplementedError

    @abstractmethod
    def write(
        self,
        dataset: Dataset,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> None:
        raise NotImplementedError

    def analyze_metadata(
        self,
        dataset: Dataset,
        report: ConversionReport,
    ) -> None:
        unsupported = (
            dataset.metadata.populated_features() - self.metadata_features
        )
        for feature in sorted(unsupported):
            report.add(
                "warning",
                f"metadata_dropped.{feature}",
                f"The destination format cannot represent {feature.replace('_', ' ')}.",
            )


class UnavailableAdapter(Adapter):
    def __init__(self, capability: FormatCapability):
        self.capability = capability

    def read(
        self,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> Dataset:
        del path, options, report
        raise AdapterError(self.capability.detail or "Reader is not available.")

    def write(
        self,
        dataset: Dataset,
        path: Path,
        options: dict[str, Any],
        report: ConversionReport,
    ) -> None:
        del dataset, path, options, report
        raise AdapterError(self.capability.detail or "Writer is not available.")
