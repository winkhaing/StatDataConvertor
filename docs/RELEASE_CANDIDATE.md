# Release-candidate package testing

Version 0.10 adds a packaging gate that runs for pull requests, main-branch
updates, and manual requests. It complements the faster source tests by checking
the files a user would actually download.

## Build matrix

| Target | GitHub runner | Finished packages tested |
|---|---|---|
| Linux x64 | Ubuntu 24.04 | DEB and AppImage |
| Windows x64 | Windows 2025 | MSI |
| macOS ARM64 | macOS 15 ARM64 | DMG |
| macOS Intel | macOS 15 Intel | DMG |

The Windows job also builds an NSIS installer. Its signature is checked in a
credentialed release, but the smoke test uses the MSI because it can be
extracted without changing the runner's installed applications.

## What the smoke test proves

The platform job first creates the bundled conversion engine and optional local
bridge kits, then creates the native installer. The smoke test works only from
the finished package:

- macOS mounts the DMG read-only, verifies the app and Applications shortcut,
  checks the app signature, and runs the engine inside the mounted app;
- Windows extracts the MSI to a temporary directory and runs its engine;
- Linux extracts the DEB and AppImage independently and runs each engine.

Every package must contain its desktop launcher. Every executed engine must
complete a two-row CSV-to-XLSX conversion, write its fidelity report, and
report:

- the same version as the desktop package;
- local-only processing with network access disabled;
- all essential format families in the capability registry;
- a certification registry; and
- no direction marked certified unless its state is `vendor_verified`.

The result is written to
`release-metadata/smoke-<platform>-<architecture>.json`. Installers, bridge
archives, manifests, checksums, and smoke diagnostics are retained as CI
artifacts for 14 days, including partial diagnostics from failed jobs.

Run the same check locally after building the native packages:

```text
npm run release:smoke-package
```

## What it does not prove

A passing smoke test establishes package integrity, bundled-engine launch, and
the declared runtime contract on that runner. It does not prove that every
format conversion is lossless, that an optional vendor application is
installed, that vendor bridge conversions work, or that a direction is vendor
certified. Those claims remain governed by the fixture, round-trip, destination
opening, and reviewed-evidence process in `VALIDATION.md`.

Pull-request packages are test builds and are not production-signed. Official
tagged releases additionally require the signing, notarization, checksum, and
provenance controls in `SIGNED_DISTRIBUTION.md`.
