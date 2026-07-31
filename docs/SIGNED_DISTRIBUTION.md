# Signed distribution

Official v0.10 releases are built on GitHub Actions for Linux x64, Windows x64,
macOS ARM64, and macOS Intel. A version tag requires the available platform
installers to pass their signature and packaged-runtime checks before the draft
release is completed. Manual workflow runs
may deliberately produce unsigned test packages when `require_signing` is
disabled; those packages are not production releases.

## Release credentials

The repository administrator must configure these encrypted GitHub Actions
secrets:

### macOS

- `APPLE_CERTIFICATE`: base64-encoded Developer ID Application certificate in
  PKCS #12 (`.p12`) form;
- `APPLE_CERTIFICATE_PASSWORD`: password for the PKCS #12 file;
- `KEYCHAIN_PASSWORD`: temporary build-keychain password;
- `APPLE_ID`: Apple account used for notarization;
- `APPLE_PASSWORD`: app-specific password for that account; and
- `APPLE_TEAM_ID`: Apple Developer team identifier.

The workflow imports the certificate into a temporary keychain, signs the
application, submits the package through Tauri's notarization path, and runs
both `codesign` and Gatekeeper assessment. A local build without these
credentials is ad-hoc signed for testing and is not notarized.

The macOS app grants only the library-validation exception required for the
bundled Python engine to load its locally extracted, signed runtime libraries.
It does not enable the App Sandbox, network access, JIT compilation, or
unsigned executable memory.

The separately packaged macOS JMP and SAS bridge executables receive the same
narrow entitlement and code-signing identity because they use the same
single-file Python runtime.

The release job mounts the finished DMG, verifies its app signature, and
launches the engine from inside the mounted app. It checks the engine version,
essential format registry, local-only privacy contract, and certification
claims. This catches runtime-library signing failures that a static `codesign`
check alone may miss.

### Windows

- `WINDOWS_CERTIFICATE`: base64-encoded Authenticode certificate in PKCS #12
  (`.pfx`) form;
- `WINDOWS_CERTIFICATE_PASSWORD`: password for the PFX file; and
- `WINDOWS_TIMESTAMP_URL`: optional RFC 3161 timestamp service. The workflow
  uses DigiCert's public timestamp endpoint when this is omitted.

The certificate is imported into the current build user's certificate store.
Tauri signs installers with SHA-256 and the workflow rejects any generated
`.exe` or `.msi` whose Authenticode status is not valid. The same certificate
and timestamp service sign the bundled engine and separately packaged Windows
bridge executables before installer creation.

Linux packages do not currently have a platform signing identity. Their
checksums and GitHub build-provenance attestations are still published.
The release job extracts both the DEB and AppImage and executes the bundled
engine from each package.

On Windows, the release job performs an administrative extraction of the MSI
and executes its bundled engine. The NSIS installer is still signature-checked,
but is not silently installed in CI.

## Release procedure

1. Run the full test workflow from the intended release commit.
2. Confirm all signing secrets are available in the repository environment.
3. Create and push the exact version tag, for example `v0.10.0`.
4. Wait for all four platform jobs to finish.
5. Review the draft GitHub Release and its installer, bridge archive, manifest,
   checksum, and provenance assets.
6. Verify a downloaded installer independently before publishing the draft.

Every platform job writes a JSON artifact manifest and a
`SHA256SUMS-<platform>.txt` file, verifies both locally, and uploads them to the
draft release. Optional vendor bridges are distributed as a separate archive;
installing one does not certify its conversions.

The workflow also rejects a tag that does not match the synchronized desktop,
engine, and package version.

## User verification

Compare the downloaded file with its entry in the matching `SHA256SUMS` file.
Common local commands are:

```text
# macOS
shasum -a 256 "StatData Converter_0.10.0_aarch64.dmg"

# Linux
sha256sum "StatData Converter_0.10.0_amd64.AppImage"

# Windows PowerShell
Get-FileHash ".\StatData Converter_0.10.0_x64-setup.exe" -Algorithm SHA256
```

Check the platform signature after installation:

```text
# macOS
codesign --verify --deep --strict --verbose=2 "StatData Converter.app"
spctl --assess --type execute --verbose=2 "StatData Converter.app"

# Windows PowerShell
Get-AuthenticodeSignature ".\StatData Converter_0.10.0_x64-setup.exe"
```

GitHub CLI can verify that a file came from this repository's release workflow:

```text
gh attestation verify "/path/to/downloaded-file" -R OWNER/REPOSITORY
```

A valid provenance attestation establishes where and how an artifact was built.
It does not establish that the software is safe, that a conversion is lossless,
or that a vendor has certified a format direction.

## Trust boundary

Release signing authenticates the distributed application. Vendor
certification authenticates conversion evidence. These are intentionally
separate:

- a signed installer can contain an experimental adapter;
- an evidence package can pass automated checks without being approved;
- only a direction explicitly marked `vendor_verified` in the in-app registry
  may be described as vendor verified; and
- no v0.10 direction is promoted automatically from a submitted manifest.

The current workflow follows the official
[Tauri macOS signing](https://v2.tauri.app/distribute/sign/macos/),
[Tauri Windows signing](https://v2.tauri.app/distribute/sign/windows/), and
[GitHub artifact attestation](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)
procedures.
