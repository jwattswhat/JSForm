# JSForm package release procedure

Package releases are prepared only in the packaging worktree. The fixed source
baseline used by installed applications is not changed by release preparation.

1. Confirm the branch is clean and review the version in `version.py`.
2. Install development tooling with `python -m pip install -e ".[development]"`.
3. Run `python run_jsform_tests.py`.
4. Remove prior generated artifacts from `dist/`, then run `python -m build`.
5. Run `python verify_distribution.py`.
6. Install the wheel into an isolated location and verify `import JSForm` from
   outside the repository.
7. Run the School Bus sample against that installed distribution.
8. Record GUI and PDF visual checks separately; automated tests do not prove
   visual correctness.
9. Calculate SHA-256 hashes and retain the wheel and source archive together.

The wheel contains only the importable framework and bundled runtime data. The
source archive additionally contains project documentation, tests, and the
School Bus sample. Neither artifact may contain logs, credentials, database
dumps, backups, generated reports, virtual environments, or development
scratch files.
