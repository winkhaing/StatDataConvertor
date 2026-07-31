# Optional SAS bridge

This bridge uses a separately installed, locally licensed SAS Foundation
runtime. It does not include or redistribute SAS.

It adds experimental SAS7BDAT writing and CPORT reading/writing. SAS7BDAT
reading remains available in the open core. CPORT archives can contain entire
libraries and catalogs; the bridge intentionally selects one data set and
reports that projection.

Build with `npm run bridge:sas:build`, then place either generated bridge folder
under `~/.statdata-converter/bridges` or add it to `STATDATA_BRIDGE_PATH`. Set
`STATDATA_SAS_EXECUTABLE` when SAS is not on the command path.

The bridge refuses to overwrite outputs. Its capabilities remain experimental
until vendor-created fixtures pass round-trip and destination-opening tests.
