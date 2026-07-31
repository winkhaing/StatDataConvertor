# Local vendor bridge protocol

Vendor bridges are separate local executables. They let a licensed installation
of JMP, SAS, Minitab, EViews, Statistica, or another product participate without
putting proprietary code in the Apache-2.0 core.

The core discovers manifests from:

- paths listed in `STATDATA_BRIDGE_PATH`, separated by the operating system path
  separator; and
- `~/.statdata-converter/bridges`.

A configured path may be a manifest file or a directory containing
`*.statdata-bridge.json` files or child folders with `bridge.json`.

The desktop “Vendor bridges” screen can install a trusted bundle by selecting
its manifest. The installer copies the bundle into the local bridge folder,
refuses symbolic links and oversized bundles, never replaces an existing bridge
silently, and refreshes runtime checks immediately. Installation alone does not
activate conversion: the bridge must still pass its probe.

The same workflow is available from the CLI:

```text
statdata-converter bridge-install /path/to/bundle/bridge.json
statdata-converter bridge-diagnostics
```

## Manifest

```json
{
  "protocol_version": 1,
  "name": "Example JMP Bridge",
  "executable": "./statdata-jmp-bridge",
  "arguments": [],
  "timeout_seconds": 300,
  "format": {
    "id": "jmp",
    "family": "JMP",
    "label": "JMP data table",
    "extensions": [".jmp"],
    "can_read": true,
    "can_write": true,
    "trust": "experimental",
    "metadata_features": [
      "dataset_label",
      "table_name",
      "column_labels",
      "value_labels",
      "formats",
      "notes"
    ]
  }
}
```

Relative executable paths are resolved from the manifest directory. A manifest
is not activated until its executable passes a protocol probe.

## Process contract

The core launches the executable with one action argument and writes one JSON
request to standard input. The bridge must write one JSON response to standard
output. Diagnostics belong on standard error.

### Probe

Command:

```text
statdata-jmp-bridge probe
```

Request:

```json
{"protocol_version": 1}
```

Response:

```json
{
  "status": "ok",
  "protocol_version": 1,
  "version": "1.0.0",
  "can_read": true,
  "can_write": true
}
```

### Read

The request contains `input_path`, an empty `package_path`, and an `options`
object. The bridge reads the proprietary file and creates the canonical package
directory.

### Write

The request contains `package_path`, `output_path`, and `options`. The bridge
reads the canonical package and creates the requested proprietary file.

Both operations return:

```json
{
  "status": "ok",
  "changes": [
    {
      "severity": "warning",
      "code": "jmp.example_transformation",
      "message": "Describe every transformation or metadata loss.",
      "columns": ["column_name"]
    }
  ]
}
```

Errors return a non-zero exit status or a response such as
`{"status":"error","error":"message"}`.

## Canonical package

The package directory contains:

- `manifest.json` with `package_version: 1`;
- `data.json`, a pandas-compatible JSON Table Schema document; and
- `metadata.json`, including labels, missing definitions, formats, measures,
  notes, and extension metadata.

Every external bridge conversion is marked unverified until representative
vendor-generated fixtures pass the round-trip validation workflow. Bridges are a
separate process trust boundary; operators should install only bridges they
trust.

## Included optional JMP writer bridge

Native JMP reading is built into the open core and does not require this bridge.
`bridges/jmp` remains available for environments that need JMP-assisted writing
or comparison with the native reader. It:

- detects a separately installed JMP executable;
- launches an auto-running JSL script supplied as a file argument;
- blocks embedded scripts when reading a quarantined JMP table;
- transfers values and column names through UTF-8 CSV;
- reports type inference and all unsupported JMP metadata; and
- refuses to overwrite an existing `.jmp` output.

It remains experimental and unavailable unless its probe detects JMP. The
built-in read-only adapter remains available when this probe fails. See
[`../bridges/jmp/README.md`](../bridges/jmp/README.md).

## Modern Minitab and Statistica

The core reserves the `minitab` format ID for current `.mtw`, `.mwx`, `.mpj`,
and `.mpx` files, and `statistica` for `.sta`. A bridge manifest using either ID
replaces the unavailable core placeholder after its executable passes the
probe. Such a bridge must:

- use a separately installed, locally licensed vendor application or redistributable
  vendor runtime;
- refuse silent fallback to CSV renamed with a native extension;
- report worksheet/page selection and every omitted analysis or design object;
- preserve the source file and refuse destructive in-place conversion; and
- remain experimental until vendor-created fixtures pass round-trip and
  destination-opening validation.

`bridges/windows-com` now contains source and build recipes for both bridges.
They use the vendors' documented Windows COM interfaces and XLSX interchange.
The probe must instantiate the installed application before the bridge replaces
the unavailable core placeholder. See
[`../bridges/windows-com/README.md`](../bridges/windows-com/README.md).

These bridge kits are source-complete but vendor-unverified in this repository:
they cannot be promoted until licensed Windows installations and representative
native fixtures pass the validation matrix.

## SAS Foundation

`bridges/sas` contains two manifests backed by one local SAS batch bridge:

- `sas_data` adds SAS7BDAT writing while retaining open-core reading; and
- `sas_cport` imports or exports one selected data set using PROC CIMPORT/CPORT.

The bridge invokes SAS with `-SYSIN`, inspects the batch log for errors, refuses
overwrites, and reports its temporary XPORT interchange. It is unavailable
unless `sas` is on the command path or `STATDATA_SAS_EXECUTABLE` points to a
licensed SAS Foundation executable. See
[`../bridges/sas/README.md`](../bridges/sas/README.md).
