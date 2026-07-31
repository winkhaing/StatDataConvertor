# Optional Windows vendor COM bridges

These bridge kits automate separately installed, locally licensed copies of
Minitab or Statistica through their documented Windows COM interfaces. They do
not include or redistribute either vendor application.

Both bridges use a temporary XLSX worksheet. This preserves ordinary tabular
values and Excel-compatible date/time values, but it is not a project clone.
Minitab constants, matrices, design objects, project output, and history are
omitted. Statistica analyses, workbooks, reports, graphs, formulas, multimedia,
and application-specific spreadsheet properties are omitted. Every conversion
reports that projection.

Build on Windows with `npm run bridge:windows-com:build`. Install the desired
generated folder under `~/.statdata-converter/bridges`, or add it to
`STATDATA_BRIDGE_PATH`. A bridge is activated only after COM creates the vendor
application during its probe.

These bridges are experimental. They have source-level and protocol tests, but
this repository cannot claim vendor validation until representative licensed
installations and native fixtures pass the documented validation matrix.
