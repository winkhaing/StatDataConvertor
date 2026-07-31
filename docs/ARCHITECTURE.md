# Architecture

## Shape of the application

The desktop UI is a Tauri application. A bundled Python executable performs all
inspection and conversion locally. The same executable exposes a CLI, so desktop,
batch, and future automation workflows share one conversion implementation.

The desktop keeps the engine process alive and communicates over newline-delimited
JSON on its standard input and output. The bundled runtime is unpacked once per
application session instead of once per conversion.

```text
React desktop UI
      |
      | typed Tauri commands
      v
Tauri process boundary
      |
      | JSON request / JSON response
      v
statdata-engine
      |
      +-- format registry
      +-- canonical Dataset + Metadata model
      +-- read adapter
      +-- fidelity analyzer
      +-- write adapter
      +-- conversion report
      +-- round-trip validator
      +-- direction-specific certification registry
      +-- immutable evidence-package auditor
      +-- optional vendor bridges
```

Files are passed by absolute path. Dataset contents are never sent through the
webview and no network client exists in the conversion engine.

## Canonical model

Adapters read into a canonical `Dataset`:

- a tabular data frame;
- dataset and table labels;
- column labels and storage/display formats;
- value labels;
- user-defined missing values, including distinct SPSS ranges and Stata
  extended-missing codes;
- measures and roles;
- notes, source, and update time; and
- per-column temporal kind, precision, timezone, missingness, storage type, and
  original native display format; and
- adapter-specific metadata in an extension map.

The writer declares which metadata features it can represent. Before writing,
the engine profiles temporal columns and compares both data and metadata with
the destination capabilities. Unsupported temporal values are rejected before
file creation. Exact, lossy, unsupported, and unverified temporal decisions are
recorded per column. Reports are JSON and include adapter versions so results
can be reproduced.

The validator reads a trusted source and a generated target back into this same
model. It compares table structure, every value, and each populated metadata
feature. Data equivalence, metadata equivalence, and the stricter lossless result
remain separate signals.

## Trust levels

- **Verified:** covered by round-trip fixtures and metadata assertions.
- **Experimental:** implemented but not yet validated against representative
  files from multiple software versions.
- **Read-only / write-only:** only one reliable direction exists.
- **Vendor bridge:** support depends on locally installed licensed software.
- **Planned:** no conversion claim is made.

## Proprietary formats

The open core contains an independently implemented, read-only native JMP
adapter. It does not invoke JMP and reports every unsupported metadata class.
Optional JMP writing, Minitab, EViews, Statistica, SAS catalogs/CPORT, and some
project formats are isolated behind the versioned process protocol documented in
[`BRIDGES.md`](BRIDGES.md). A bridge must:

1. detect the local vendor installation without uploading data;
2. state its supported application versions;
3. return the canonical model or accept it for writing;
4. emit warnings for unsupported metadata; and
5. ship separately when vendor redistribution terms require it.

This boundary also allows native parsers to replace bridges later without
changing the UI or CLI.

## Certification and distribution

Certification is tracked per native format direction. Fixture-tested and
vendor-verified are different states, and a read result cannot promote writing.
The evidence auditor checks the package boundary, SHA-256 hashes, validation
outcome, format direction, and destination-opening record. A passing package is
only eligible for manual registry review.

Platform signing is a separate release boundary. The GitHub workflow requires
Apple signing plus notarization and Windows Authenticode credentials for tagged
releases, verifies the generated signatures, writes and rechecks an artifact
manifest, and publishes GitHub provenance attestations. See
[`SIGNED_DISTRIBUTION.md`](SIGNED_DISTRIBUTION.md).
