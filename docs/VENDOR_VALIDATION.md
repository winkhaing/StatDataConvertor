# Vendor validation

Native vendor support is promoted only from evidence produced with a supported
vendor application. Installing a bridge or passing its protocol probe does not
establish lossless conversion.

For each vendor product and supported release:

1. Create an independent fixture in the vendor application.
2. Include numeric, text, boolean, labelled, missing, date, time, datetime, and
   duration columns where the format supports them.
3. Include boundary dates, subsecond values, timezones, non-ASCII text, long
   names, value labels, user-missing values, and application metadata.
4. Record the fixture checksum and expectations in a manifest conforming to
   `fixtures/vendor-validation-manifest.schema.json`.
5. Run read, write, and round-trip validation. Preserve the generated
   conversion and validation JSON files.
6. Open app-written files in the vendor application and record any repair,
   warning, or coercion message.

Evidence is evaluated per direction and vendor release. A successful read does
not certify writing; one vendor version does not certify all versions. Known
changes remain visible in the conversion report even after a bridge is promoted.

## Certification evidence package

Place the fixture, generated validation JSON, and conversion report beside a
certification manifest conforming to
[`fixtures/vendor-certification-manifest.schema.json`](fixtures/vendor-certification-manifest.schema.json).
All evidence paths must be relative to that folder. The audit rejects symbolic
links, files outside the package, missing files, changed SHA-256 hashes, failed
data comparisons, format-direction mismatches, and write evidence without a
successful vendor-application opening check.

List the exact warning/error and non-exact temporal report codes in
`expected_transformations`; the audit requires this list to match the conversion
report.

Audit the package from the desktop “Vendor bridges” screen or the CLI:

```text
uv run --project engine statdata-converter certification-audit \
  /path/to/evidence/certification.json \
  --json
```

A passing audit means the package is eligible for maintainer review. It does
not edit the certification registry and does not confer vendor certification.
Maintainers must confirm fixture independence, licensing, vendor versions,
expected transformations, and reproducibility before changing any direction to
`vendor_verified`.

The validation JSON includes engine, Python, pandas, operating-system, adapter,
bridge, vendor-runtime, and temporal-column evidence. These fields make a result
reproducible and prevent an installed-but-unavailable bridge from being mistaken
for a tested conversion path.
