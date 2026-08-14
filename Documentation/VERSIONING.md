# JSForm versioning

JSForm uses semantic versioning and has one authoritative version in
`version.py`. The formal development baseline is `0.1.0-dev`.

- Patch versions identify compatible bug fixes.
- Minor versions identify compatible framework features.
- Major versions identify incompatible framework changes.
- The `-dev` suffix remains until a supported release is prepared.

Code and support diagnostics must read `JSForm.__version__`; version strings
must not be copied into individual screens or modules.
