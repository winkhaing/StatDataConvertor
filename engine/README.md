# Conversion engine

The engine reads a source dataset into a canonical table-and-metadata model,
writes the requested destination, and produces a JSON fidelity report.

The `statistical` extra installs the ReadStat-backed adapters for SAS, SPSS, and
Stata. CSV, modern and legacy Excel reading, JSON-stat, RDS/RData,
license-free native JMP reading, and EViews WF1/WF2 support are part of the core
installation.

Legacy Minitab Portable input is enabled when local `Rscript` and R's
recommended `foreign` package are detected. Modern Minitab native formats and
Statistica `.sta` remain optional vendor-bridge targets.

The open core also writes SAS DATA-step programs with UTF-8 CSV sidecars. The
optional v0.10 bridge kits add local SAS Foundation batch conversion and Windows
COM automation for modern Minitab and Statistica formats. Runtime detection and
direction-specific certification status are reported by
`statdata-converter capabilities --json`. Evidence packages can be checked
without changing the registry:

```text
statdata-converter certification-audit /path/to/certification.json --json
```

Round-trip validation is available through `statdata-converter validate`. Local
vendor bridges use the protocol documented in `../docs/BRIDGES.md`.
