# Round-trip validation

Support claims are promoted with evidence, not only with a successful parser
call. The validation workflow reads a trusted source, converts it to a selected
target, reads the generated file back, and compares both canonical datasets.

## What is compared

- column names and order;
- row count;
- every cell value, with explicit missing-value handling and a small numeric
  tolerance;
- dataset and table labels;
- column and value labels;
- user-defined missing values and ranges;
- display formats, measures, notes, source, and update metadata.

Data integrity and metadata fidelity are reported separately. A validation can
therefore pass its data comparison while still refusing a lossless claim because
metadata changed.

The validator retains three artifacts:

1. the generated target file;
2. the normal conversion fidelity report; and
3. a `.statdata-validation.json` comparison result.

The comparison result also records the exact engine, Python, pandas, operating
system, adapter trust level, matching bridge, detected vendor runtimes, source
temporal profiles, and per-column temporal conversion decisions. Vendor test
operators should pair this result with a manifest conforming to
[`fixtures/vendor-validation-manifest.schema.json`](fixtures/vendor-validation-manifest.schema.json).

## Date and time preflight

Every conversion profiles temporal columns before the destination writer runs.
The profile distinguishes dates, datetimes, time-only values, and durations,
and records required precision, timezone, missing-value count, storage type,
and the original native display format when available.

Each temporal column receives one destination outcome:

- `exact`: the known destination path represents the value without a temporal
  transformation;
- `lossy`: conversion can continue, but type, precision, timezone, or duration
  meaning changes;
- `unsupported`: conversion stops before the destination file is created; or
- `unverified`: a bridge or future adapter has no verified temporal contract.

The desktop app defaults to safe handling, which stops on any non-exact
outcome. Users can instead continue in compatible mode and review every known
change in the result screen and JSON report. Engine and CLI callers choose the
same behavior with `output_options.temporal_policy`:

```text
{"temporal_policy": "safe"}
```

Use `"compatible"` to allow known lossy paths. Unsupported paths are blocked
under both policies.

## CLI

```text
uv run --project engine statdata-converter validate \
  survey.sav stata \
  --artifacts validation-output
```

Use `--json` for a machine-readable response. Format-specific writer options use
the same JSON object accepted by `convert`:

```text
uv run --project engine statdata-converter validate \
  survey.csv stata \
  --output-options '{"stata_version": 15, "temporal_policy": "safe"}' \
  --json
```

## Promotion policy

An adapter remains experimental until the fixture set includes:

- files created by the vendor application, not only by this engine;
- materially different software generations;
- numeric, text, boolean, date/time, and missing data;
- non-ASCII variable names and labels where the format permits them;
- value labels, user-missing definitions, and display formats; and
- a successful opening check in the destination vendor application when one
  exists.

Passing one fixture is useful evidence but does not certify an entire format
family.

The built-in reader fixtures for JMP 17.2 and 18.2.1 live in
[`../engine/tests/fixtures/jmp`](../engine/tests/fixtures/jmp). The broader
vendor fixture checklist and manifest template live in
[`../bridges/jmp/fixtures`](../bridges/jmp/fixtures).

The EViews tests include constructed WF1 layout coverage and WF2 JSON/gzip
round trips. The WF1 reader has also been exercised against vendor-published
tutorial workfiles, but support remains experimental until versioned fixtures
can be redistributed and WF2 output is opened in supported EViews releases.

Minitab Portable tests cover the historical text format through R's `foreign`
reader. This evidence does not apply to modern Minitab `.mtw`, `.mwx`, `.mpj`,
or `.mpx` files. Statistica `.sta` has no support claim until vendor-generated
fixtures and a licensed bridge or compatible open parser are available.

The v0.10 vendor bridge kits include protocol, safe-install, safe-probe, evidence
hash, and certification-manifest audit tests. Real conversion validation is
intentionally still pending because this development machine has no SAS, JMP,
Minitab, or Statistica installation. Required promotion fixtures must include
dates before and after each native epoch, date-times with fractional seconds,
time-only values, durations, missing values, Unicode text, labels, and at least
two supported vendor releases.

The complete vendor test procedure is documented in
[`VENDOR_VALIDATION.md`](VENDOR_VALIDATION.md).
