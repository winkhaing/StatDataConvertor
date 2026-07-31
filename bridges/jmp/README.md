# StatData JMP bridge

StatData Converter now reads `.jmp` files natively without this bridge or JMP
software. This optional bridge uses a locally licensed JMP installation for
native `.jmp` writing and for comparison against the built-in reader. It does
not include or redistribute JMP.

The initial bridge deliberately exposes a tabular projection:

- values and column names are transferred through UTF-8 CSV;
- numeric storage types are inferred;
- column properties, row states, table scripts, formulas, value ordering, and
  JMP-specific modeling metadata are reported as unsupported; and
- every conversion remains unverified until vendor-generated fixtures pass the
  round-trip validator.

## Detection

The bridge searches standard JMP installation locations. To select a specific
installation, set:

```text
STATDATA_JMP_EXECUTABLE=/path/to/the/JMP/executable
```

On Windows, point to `jmp.exe`. On macOS, point to the executable inside the JMP
application's `Contents/MacOS` directory.

## Installation

Build the platform bridge:

```text
npm run bridge:jmp:build
```

Copy the contents of `bridges/jmp/bundle` into:

```text
~/.statdata-converter/bridges/jmp
```

Restart StatData Converter. The Formats screen will show whether the executable
and JMP installation passed their probes.

JMP can display license, quarantine, or security prompts while running a script.
The bridge times out rather than bypassing those prompts.
