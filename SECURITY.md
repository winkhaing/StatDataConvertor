# Security policy

## Supported version

Security fixes are applied to the latest published release and the `main`
branch.

## Reporting a vulnerability

Please use GitHub's private vulnerability-reporting feature:

1. open the repository's **Security** tab;
2. choose **Report a vulnerability**; and
3. include affected versions, reproduction steps, impact, and any suggested
   mitigation.

Do not open a public issue for an unpatched vulnerability. Please allow a
reasonable period for investigation and coordinated disclosure.

## Data-handling boundary

The application is designed to process datasets locally. A report should be
treated as a security issue if the application unexpectedly transmits dataset
content, credentials, file paths, or conversion metadata to a remote service.

Optional vendor bridges execute local vendor software and remain inside the
trust boundary documented in `docs/BRIDGES.md`.
