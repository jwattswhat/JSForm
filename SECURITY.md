# Security policy

## Supported versions

JSForm is currently pre-release. Security fixes are made on the active
development branch; no older release line is presently supported.

## Reporting a vulnerability

Do not put credentials, personal data, database dumps, or exploit details in a
public issue. Contact the project maintainer privately with:

- the affected version and module;
- steps to reproduce using non-sensitive test data;
- the likely impact; and
- any suggested mitigation.

The maintainer should acknowledge the report, reproduce it safely, prepare a
test and fix, and coordinate disclosure after users can update.

## Security boundaries

JSForm provides reusable mechanisms, not an application's authorization policy.
Applications remain responsible for least-privilege database accounts,
permissions, audit rules, privacy, backup protection, and safe report datasets.
Secrets must use an operating-system credential store or another appropriate
secret provider and must never be written to form JSON, logs, or source control.
