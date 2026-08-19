# JSForm package release procedure

Package releases are prepared only in the packaging worktree. The fixed source
baseline used by installed applications is not changed by release preparation.

1. Confirm the branch is clean and review the version in `version.py`.
2. Install development tooling with `python -m pip install -e ".[development]"`.
3. Run `python run_jsform_tests.py`.
4. Remove prior generated artifacts from `dist/`, then run `python -m build`.
5. Run `python verify_distribution.py`.
6. Run `python accept_distribution.py`. It installs the wheel into an isolated
   temporary location, imports `JSForm` and the School Bus sample from that
   installation, and writes `dist/SHA256SUMS.txt` for the wheel and source
   archive.
7. Open the School Bus sample from the installed distribution for GUI review.
8. Record GUI and PDF visual checks separately; automated tests do not prove
   visual correctness.
9. Retain `SHA256SUMS.txt`, the wheel, and the source archive together.

Acceptance does not publish an artifact or change `version.py`. Promotion from
a development version to a beta or stable version is an explicit release
decision followed by a fresh build and acceptance run.

The wheel contains only the importable framework and bundled runtime data. The
source archive additionally contains project documentation, tests, and the
School Bus sample. Neither artifact may contain logs, credentials, database
dumps, backups, generated reports, virtual environments, or development
scratch files.
