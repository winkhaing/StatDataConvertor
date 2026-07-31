from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .adapters import (
    Adapter,
    CsvAdapter,
    EViewsAdapter,
    EViewsWf1Adapter,
    ExcelAdapter,
    FormatCapability,
    JmpAdapter,
    JsonStatAdapter,
    LegacyExcelAdapter,
    MinitabPortableAdapter,
    RDataAdapter,
    ReadStatAdapter,
    SasProgramAdapter,
    UnavailableAdapter,
    discover_bridges,
)


def _placeholder(
    format_id: str,
    family: str,
    label: str,
    extensions: tuple[str, ...],
    detail: str,
    availability: str = "vendor_bridge",
) -> UnavailableAdapter:
    return UnavailableAdapter(
        FormatCapability(
            id=format_id,
            family=family,
            label=label,
            extensions=extensions,
            can_read=False,
            can_write=False,
            trust="planned",
            availability=availability,
            detail=detail,
        )
    )


class FormatRegistry:
    def __init__(self, bridge_paths: Iterable[Path] | None = None) -> None:
        adapters: list[Adapter] = [
            CsvAdapter(),
            ExcelAdapter(),
            LegacyExcelAdapter(),
            JsonStatAdapter(),
            ReadStatAdapter("stata"),
            ReadStatAdapter("spss_data"),
            ReadStatAdapter("spss_portable"),
            ReadStatAdapter("sas_data"),
            ReadStatAdapter("sas_xport"),
            RDataAdapter(),
            JmpAdapter(),
            MinitabPortableAdapter(),
            EViewsAdapter(),
            EViewsWf1Adapter(),
            SasProgramAdapter(),
            _placeholder(
                "sas_catalog",
                "SAS",
                "SAS format catalog",
                (".sas7bcat",),
                "Catalog conversion requires association with a dataset or a SAS bridge.",
            ),
            _placeholder(
                "sas_cport",
                "SAS",
                "SAS CPORT",
                (".cpo", ".cport"),
                "A local SAS installation bridge is required.",
            ),
            _placeholder(
                "spss_syntax",
                "IBM SPSS",
                "SPSS syntax + text data",
                (".sps",),
                "Syntax parsing and generation are planned.",
                "planned",
            ),
            _placeholder(
                "minitab",
                "Minitab",
                "Modern Minitab worksheet / project",
                (".mtw", ".mwx", ".mpj", ".mpx"),
                "Modern Minitab native formats require a separately installed "
                "Minitab bridge; the open core does not claim to parse them.",
            ),
            _placeholder(
                "statistica",
                "Statistica",
                "Statistica data file",
                (".sta",),
                "No maintained open STA parser has been independently verified. "
                "A local Statistica installation and validated bridge are required.",
            ),
        ]
        bridge_adapters, self.bridge_statuses = discover_bridges(bridge_paths)
        self._adapters = {adapter.capability.id: adapter for adapter in adapters}
        for adapter in bridge_adapters:
            self._adapters[adapter.capability.id] = adapter
        self._extensions: dict[str, str] = {}
        for adapter in self._adapters.values():
            for extension in adapter.capability.extensions:
                self._extensions[extension.lower()] = adapter.capability.id

    def capabilities(self) -> list[dict[str, object]]:
        return [
            adapter.capability.to_dict()
            for adapter in sorted(
                self._adapters.values(),
                key=lambda value: (
                    value.capability.family.lower(),
                    value.capability.label.lower(),
                ),
            )
        ]

    def get(self, format_id: str) -> Adapter:
        try:
            return self._adapters[format_id]
        except KeyError as exc:
            raise ValueError(f"Unknown format: {format_id}") from exc

    def detect(self, path: Path) -> Adapter:
        format_id = self._extensions.get(path.suffix.lower())
        if not format_id:
            raise ValueError(f"Cannot detect a format from extension {path.suffix!r}.")
        return self.get(format_id)
