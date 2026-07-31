# Format support

This table describes the tenth milestone, not an aspirational compatibility
claim. “Experimental” directions require broader real-world fixture validation.

| Family | Native type | Read | Write | Initial implementation |
|---|---|---:|---:|---|
| CSV | `.csv`, `.tsv` | Verified | Verified | pandas |
| Excel | `.xlsx` | Verified | Verified | pandas + openpyxl |
| Excel legacy | `.xls` | Experimental | Planned | pandas + xlrd |
| JSON-stat | v1/v2 dataset | Experimental | Experimental (v2) | native adapter |
| Stata | `.dta` | Experimental | Experimental | ReadStat / pyreadstat |
| SPSS data | `.sav`, `.zsav` | Experimental | Experimental | ReadStat / pyreadstat |
| SPSS portable | `.por` | Experimental | Planned | ReadStat / pyreadstat |
| SPSS syntax | `.sps` + text data | Planned | Planned | future parser/generator |
| SAS data | `.sas7bdat` | Experimental | Vendor bridge | ReadStat reader / optional local SAS batch writer |
| SAS XPORT | `.xpt` v5/v8 | Experimental | Experimental | ReadStat / pyreadstat |
| SAS catalog | `.sas7bcat` | Vendor bridge | Vendor bridge | dataset association / optional SAS bridge |
| SAS CPORT | `.cpo`, `.cport` | Vendor bridge | Vendor bridge | optional local SAS CIMPORT/CPORT bridge; one selected data set |
| SAS program | `.sas` + `.csv` | Planned | Experimental | open DATA-step + UTF-8 CSV generator |
| R single object | `.rds` | Experimental | Experimental | bundled `rdata` Python library |
| R workspace | `.RData`, `.rda` | Experimental | Experimental | bundled `rdata` Python library |
| JMP | `.jmp` | Experimental | Vendor bridge | built-in Python reader; optional bidirectional JSL bridge |
| Minitab Portable | `.mtp` | Experimental | Planned | local R `foreign::read.mtp` compatibility bridge |
| Minitab worksheet/project | `.mtw`, `.mwx`, `.mpj`, `.mpx` | Vendor bridge | Vendor bridge | optional Windows Minitab COM bridge through XLSX |
| EViews binary workfile | `.wf1` | Experimental | Vendor bridge | built-in Python reader adapted from BSD-licensed MathWorks reader |
| EViews open workfile | `.wf2` | Experimental | Experimental | native JSON/gzip reader and minimal-profile writer |
| Statistica | `.sta` | Vendor bridge | Vendor bridge | optional Windows Statistica COM bridge through XLSX |

## Scope notes

- A dataset conversion preserves the data table and representable metadata. It
  does not promise to reproduce analyses, graphs, scripts, or UI state stored in
  vendor project files.
- JSON-stat is a multidimensional cube rather than a general data frame. Writing
  requires a value column and one or more dimension columns. The engine preserves
  a JSON-stat cube's original mapping on round trip and uses a documented
  inference for ordinary tables.
- Native SAS7BDAT writing is deliberately not claimed by the open core because
  the selected open library does not provide a writer.
- The SAS program writer is write-only because arbitrary SAS code is not a
  declarative data format. Generated programs and their CSV sidecars must stay
  together. Date/time informats are emitted from the canonical temporal model.
- The SAS batch bridge is unavailable unless a local licensed SAS Foundation
  executable passes its probe. CPORT libraries are projected to one selected
  data set; catalogs and additional members are reported, not silently merged.
- Native JMP reading is local and does not require JMP. The initial reader
  covers values and common physical types but not formulas, table scripts,
  value labels, column properties, or modeling metadata. Durations are exposed
  as numeric seconds and row-state colors are reported as omitted.
- Native JMP writing is deliberately not claimed because no maintained,
  independently verified open-source writer was found.
- R workspaces can contain many objects. The reader selects a requested data
  frame, or the first data frame and reports that choice. Custom R classes and
  arbitrary attributes are outside the tabular conversion model. Base `Date`,
  `POSIXct`/`POSIXt`, and `difftime` classes are represented by the canonical
  temporal model. Time-only output is rejected instead of being silently
  changed to a duration or string.
- Minitab Portable is an obsolete compatibility format and is not a substitute
  for current `.mtw`, `.mwx`, `.mpj`, or `.mpx` support. The selected R reader
  was written for the historical portable format and preserves tabular columns,
  not modern design objects or project state.
- EViews WF1 reading supports standard and compressed numeric series. EViews
  equations, groups, VARs, graphs, tables, models, and UI state are reported as
  omitted. Multi-page WF2 files require a page selection; the first page is
  selected and reported when no page is specified.
- EViews WF2 output uses the vendor's open JSON concept, but the writer remains
  experimental until generated fixtures are opened and compared in supported
  EViews releases.
- Statistica `.sta` remains evidence-gated because no maintained,
  independently verified open parser or writer has been found. Availability
  requires a separately installed Statistica bridge and fixture validation.
- Modern Minitab and Statistica bridge conversions use temporary XLSX tables.
  Their conversion reports identify project output, analyses, design objects,
  constants, matrices, formulas, and other vendor properties that this tabular
  projection cannot carry.
- All experimental entries move to verified only after versioned fixtures pass
  data, metadata, and vendor-application opening tests.
- The in-app certification registry reports read and write evidence separately.
  `Fixture tested` is not vendor certification; only an explicitly reviewed
  `Vendor verified` direction may use that claim.
