# Contributing

Thank you for helping improve StatData Converter.

## Before opening a change

- Search existing issues and pull requests.
- Keep support claims evidence-based. A parser that opens one file is not
  automatically verified for an entire format family.
- Do not add proprietary vendor code, confidential fixtures, credentials, or
  licensed software to the repository.
- Add or update tests for every behavior change.

## Local development

Install Node.js 22 or newer, Rust 1.84 or newer, Python 3.12, and `uv`, then run:

```text
npm install
npm run engine:setup
npm test
npm run build
npm run engine:test
cargo check --manifest-path src-tauri/Cargo.toml
```

Run the desktop application with:

```text
npm run desktop:dev
```

Platform packages and optional bridges are described in `README.md` and
`docs/RELEASE_CANDIDATE.md`.

## Pull requests

Pull requests should:

- explain the user-visible problem and proposed behavior;
- identify affected formats and read/write directions;
- describe metadata or date/time transformations;
- include fixture provenance and redistribution rights;
- include test results; and
- update format-support or validation documentation when claims change.

By submitting a contribution, you agree that it is licensed under Apache-2.0.
