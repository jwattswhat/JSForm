# JSForm SMTP credential storage specification

Status: Approved and implemented

Approved by: Rev. Jonathan C. Watt

Verified: August 29, 2026 — 415 JSForm tests passed (2 skipped) and 1,063
ChurchManager tests passed (25 skipped).

Date: August 28, 2026

Framework owner: JSForm

Application owner: SMTP account selection, credential target names, migration
initiation, transaction approval, and user-facing settings workflow

## 1. Purpose

JSForm shall stop treating an SMTP password stored in database configuration as
a supported delivery credential. Applications shall identify an
application-specific operating-system credential target, and JSForm shall
retrieve the username and secret from that protected provider only when an SMTP
connection needs authentication.

This specification addresses item 5 in the JSForm Codex Security remediation
queue: **Move historical SMTP secrets out of database configuration.**

## 2. Current condition

The historical `clsSMTP` facade reads the entire `SMTP` configuration family,
copies `SMTP/UserName` and `SMTP/Password` into attributes, and passes the
plaintext password to `yagmail.SMTP`. The newer `MailSettings` contract also
contains a plaintext `password` field and `SMTPTransport` retains the settings
object for the lifetime of the transport.

`credential_store.WindowsCredentialStore` already supports generic Windows
Credential Manager read, write, existence, and delete operations. It is not yet
connected to the mail contract, and JSForm has no verified migration path that
removes a legacy `SMTP/Password` row only after protected storage succeeds.

## 3. Security invariants

1. Normal SMTP delivery shall not read a password from `tblConfig` or
   `jsConfig`.
2. Database configuration may contain a credential target identifier, but not
   the corresponding secret.
3. A credential target shall be supplied by the application and shall not be
   guessed from ChurchManager names, database names, usernames, or server
   addresses.
4. Credential lookup shall occur as late as practical, immediately before
   authenticated connection use.
5. The resolved secret shall not be stored on the transport, returned in a
   result, placed in an exception, logged, or copied into diagnostic context.
6. Missing, unreadable, or mismatched credentials shall fail closed with a
   stable `MailConfigurationError` that does not reveal the target or secret.
7. Legacy migration shall delete the database password only after the
   operating-system store confirms an exact readback.
8. A failed migration shall leave the legacy database value intact and shall
   not claim completion.

## 4. Ownership boundary

JSForm owns:

- the application-neutral credential-target mail adapter;
- safe late credential resolution;
- a transactional, explicit migration service for the historical
  `SMTP/Password` row;
- protected error behavior and tests; and
- preservation of the historical `clsSMTP.sendeMail(...)` call surface.

Applications own:

- the target name and account to use;
- authorization to create, replace, or delete credentials;
- the UI that collects a new secret;
- when migration is offered and initiated;
- committing or rolling back the database transaction after migration;
- provider-specific settings and delivery testing; and
- deployment to each Windows user account that will send mail.

JSForm shall not contain ChurchManager terminology, permission names, database
IDs, congregation names, or provider-specific account policy.

## 5. Included scope

The implementation shall add or update:

- `MailSettings` credential-target support;
- `SMTPTransport` late credential resolution through an injected provider;
- `WindowsCredentialStore` use through a small testable protocol;
- an explicit SMTP legacy-migration service;
- the historical `clsSMTP` adapter;
- public exports and contract docstrings;
- focused tests and framework documentation; and
- the JSForm enhancement roadmap after verification.

The sole database secret covered by automatic migration is the historical
configuration row whose family is `SMTP` and type is `Password`.

## 6. Excluded scope

This item shall not:

- implement ChurchManager's settings screen or permissions;
- access or modify a production database during development or tests;
- silently migrate a credential during application startup;
- invent a default credential target;
- send a real email during automated verification;
- change SMTP transport-security rules, which remain roadmap item 6;
- change database-login credential handling, which remains roadmap item 8;
- migrate unrelated API keys, including an historical `SMTP/Key` row, without
  a separate inventory and approved specification; or
- remove the legacy `clsSMTP` facade.

## 7. Public mail-settings contract

`MailSettings` shall add an optional `credential_target` field without changing
the order or meaning of existing fields. Existing callers that explicitly pass
an in-memory password remain source-compatible for bounded transition use.

Authentication modes shall be:

1. `credential_target` supplied: resolve `(username, secret)` from the injected
   credential provider at delivery time;
2. no target, explicit `username` and `password` supplied: retain the existing
   in-memory compatibility path, without any database lookup; or
3. no target and no username/password: unauthenticated SMTP.

Supplying both a credential target and a plaintext password is invalid.
Supplying only one member of an explicit username/password pair is invalid.
The credential-store username is authoritative when a target is used; a
configured username, if also present for display or compatibility, must match
it after ordinary trimming and case-insensitive comparison.

This compatibility path does not authorize storing plaintext passwords in a
database, file, command line, log, or long-lived application object.

## 8. Credential-provider seam

Mail delivery shall depend on a minimal provider contract equivalent to:

```text
read(target) -> (username, secret)
```

`WindowsCredentialStore` is the default Windows implementation. Tests shall use
an in-memory fake and shall not read or write the developer's real credential
vault.

The transport shall not resolve credentials while constructing messages or
validating recipient addresses. It shall resolve them only when delivery is
about to authenticate. Every separate delivery may perform a fresh lookup so a
credential rotation takes effect without rebuilding the settings object.

## 9. Historical `clsSMTP` compatibility

`clsSMTP()` and `sendeMail(emailaddress, name, subject, msg, attachment)` shall
remain callable with their existing signatures.

The facade shall continue to read non-secret SMTP configuration such as server,
port, sender identity, security mode, and credential target. It shall not read
or retain `SMTP/Password`. If no credential target is configured, construction
or first delivery shall fail with a safe migration-required configuration
message. The facade shall delegate delivery to the supported mail transport
rather than creating a separate credential path.

No exception or attribute exposed by the facade shall contain the password.

## 10. Explicit legacy migration

JSForm shall provide an application-neutral migration operation receiving:

- the application configuration connection;
- a credential-store provider;
- an application-supplied target;
- and no implicit commit authority.

Within the caller's transaction, the operation shall:

1. lock and read the application `tblConfig` rows for `SMTP/UserName`,
   `SMTP/Password`, and `SMTP/CredentialTarget` using connector parameters;
2. reject missing, blank, or duplicate username/password rows;
3. reject a conflicting existing target rather than overwriting it silently;
4. write the username and password to the supplied credential target;
5. read the credential back and compare both values exactly;
6. insert or update the non-secret `SMTP/CredentialTarget` configuration row;
7. delete every verified legacy `SMTP/Password` application row using a static,
   parameterized predicate;
8. return a non-secret result describing whether migration occurred; and
9. leave commit or rollback to the application.

The migration shall never copy a password from framework fallback `jsConfig`.
If credential write/readback or any SQL operation fails, it shall raise a safe
typed error. The caller can then roll back the database transaction. If the
credential was newly written before a later SQL failure, the operation shall
attempt compensating credential deletion without masking the original error.

Migration shall be idempotent after success: a matching credential target with
no password row reports that no migration is needed. It shall not overwrite an
existing credential or delete a legacy password when the state is ambiguous.

## 11. Error handling and redaction

Credential-provider `KeyError`, operating-system errors, malformed provider
results, username mismatches, and blank secrets shall become safe
`MailConfigurationError` or a dedicated migration error. Exception chaining may
retain the technical cause for local diagnostics, but user-facing text and
structured diagnostic context shall not contain:

- the secret;
- the credential target;
- the stored username unless supplied separately as approved safe context; or
- raw credential-provider error text that may include sensitive values.

MailService delivery results shall continue to avoid exposing secrets.

## 12. Database and transaction behavior

All migration SQL structure shall be static. Family, type, target, username,
and other runtime values shall be connector parameters. Cursors shall close on
success and failure without masking the original error.

The migration service shall call neither `commit()` nor `rollback()`. This
preserves the application's authority over a change that spans its database and
the current Windows user's credential vault.

Because those two stores cannot participate in one atomic transaction, the
service shall document and test its compensation behavior. It shall never
delete a database password before verified credential readback.

## 13. Documentation changes

Implementation shall update `Documentation/JSForm_Framework.md` and relevant
sample documentation to explain:

- credential target configuration;
- current-user Windows Credential Manager scope;
- explicit migration and caller-owned transaction handling;
- the transitional in-memory password compatibility path;
- safe failure when a target or credential is unavailable; and
- the separation between this item and protected SMTP transport in item 6.

The obsolete SQL documentation example shall no longer recommend inserting an
`SMTP/Password` row. Historical evidence may be described as unsafe legacy
configuration, but no usable credential example shall remain.

## 14. Testing requirements

Focused tests shall prove:

1. target-backed settings validate without a plaintext password;
2. target plus plaintext password is rejected;
3. explicit in-memory username/password callers remain compatible;
4. unauthenticated settings remain compatible;
5. credentials are not read during settings construction or message creation;
6. credentials are read immediately before authenticated delivery;
7. rotation is observed on a later delivery;
8. missing, blank, malformed, and mismatched credentials fail safely;
9. errors, results, and retained transport state contain no secret;
10. the historical facade preserves its public signatures and delegates to the
    supported transport;
11. the facade does not query or retain `SMTP/Password`;
12. migration reads only application `tblConfig` with parameterized SQL;
13. migration verifies exact protected-store readback before deletion;
14. migration records the target and deletes only `SMTP/Password`;
15. migration does not commit or roll back;
16. ambiguous, missing, duplicate, and conflicting states fail closed;
17. successful migration is idempotent;
18. post-write SQL failure attempts credential compensation;
19. compensation failure does not mask the original failure;
20. no test accesses a real credential vault, production database, or SMTP
    provider;
21. public exports and documentation match the implemented contract;
22. the complete JSForm suite passes; and
23. ChurchManager's suite passes against the updated framework without any
    ChurchManager source change required by this framework item.

## 15. Acceptance criteria

The item is complete when:

1. supported database-backed SMTP delivery no longer reads a password row;
2. target-backed delivery retrieves the secret only at authentication time;
3. verified migration removes the application password row and preserves a
   non-secret target reference;
4. migration failures preserve the legacy database secret and provide tested
   compensation for a newly written credential;
5. existing public mail and historical facade calls remain source-compatible
   within the stated security boundary;
6. no secret appears in errors, logs, results, or long-lived transport state;
7. an independent read-only security and compatibility review finds no
   surviving included database-password path;
8. focused tests, the full JSForm suite, and ChurchManager's suite pass;
9. documentation matches the implemented behavior; and
10. roadmap item 5 is marked implemented only after verification.

## 16. Implementation sequence after approval

1. Add characterization tests for mail settings, the transport, `clsSMTP`, and
   the current credential adapter.
2. Add the credential-provider protocol and target-backed settings contract.
3. Resolve target credentials at the final SMTP authentication boundary.
4. Route `clsSMTP` through the supported transport without reading Password.
5. Implement explicit, parameterized, compensating legacy migration.
6. Update exports, docstrings, framework documentation, and obsolete SQL
   examples.
7. Run focused tests and challenge failure, ambiguity, rotation, and redaction
   paths.
8. Perform one independent read-only security and compatibility review.
9. Correct confirmed in-scope findings and rerun focused tests.
10. Run the complete JSForm and ChurchManager suites.
11. Mark the specification and roadmap implemented only after all acceptance
    criteria pass.

## 17. Approval

Approval authorizes implementation of this specification within JSForm only.
It does not authorize ChurchManager source changes, production database access,
reading or writing any real Windows credential, sending email, deployment,
roadmap item 6 transport-policy changes, roadmap item 8 database-password
changes, or migration of the historical `SMTP/Key` value.
