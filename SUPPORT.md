# Support

Before requesting help:

1. Confirm the problem with the current development version.
2. Run `python run_jsform_tests.py`.
3. Reproduce it with the School Bus Routes sample when possible.
4. Create a redacted support package using JSForm's diagnostics facility.

Include the JSForm version, Python and wxPython versions, operating system,
steps to reproduce, expected behavior, and actual behavior. Remove credentials,
personal information, and production data. A traceback is valuable; a database
password is never required.

Application-specific failures should first be reported to that application's
maintainer. ChurchManager rules and data are outside JSForm's support boundary.

The standard logs are stored in `%LOCALAPPDATA%\<Application>\Logs`, rotate at
2 MiB, retain five rotated files, and discard rotations older than 30 days.
A support package contains those logs, safe version and platform information,
and a manifest of filenames and hashes. It does not contain databases, reports,
documents, email, images, configuration files, or source code, and creating it
does not transmit it. Review the destination and included-file list before
creating or sharing a package.

Support-package construction re-redacts retained JSONL records and application
diagnostics before hashing and archiving them. Malformed historical log lines
receive bounded text redaction. This is a final safeguard, not permission to
place credentials, personal information, or production data in diagnostics.
