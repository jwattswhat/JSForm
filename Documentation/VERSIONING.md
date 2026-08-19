# JSForm versioning

JSForm uses semantic versioning and has one authoritative version in
`version.py`. The first public beta is `0.1.0-beta.1`.

- Patch versions identify compatible bug fixes.
- Minor versions identify compatible framework features.
- Major versions identify incompatible framework changes.
- Development work uses a `-dev` suffix; reviewed prereleases use
  `-beta.N`; stable releases use only the semantic version.

Code and support diagnostics must read `JSForm.__version__`; version strings
must not be copied into individual screens or modules.
