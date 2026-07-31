# JMP validation fixtures

Do not commit confidential research data. Each sanitized fixture contribution
should include:

- the `.jmp` table;
- a CSV export made by the same JMP version;
- the JMP product and version;
- operating system;
- expected row and column counts;
- column names, storage types, modeling types, labels, formats, and value
  ordering;
- missing-value behavior;
- relevant column properties and table variables; and
- whether formulas, row states, or table scripts are present.

Use the adjacent `fixture-manifest.example.json` as the checklist. Fixtures must
be created by JMP itself, not only by StatData Converter.
