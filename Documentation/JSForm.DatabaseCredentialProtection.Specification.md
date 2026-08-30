# JSForm database credential protection specification

Status: Approved and implemented

Approved by: Rev. Jonathan C. Watt

Verified: August 29, 2026 — 444 JSForm tests passed (2 skipped) and 1,063
ChurchManager tests passed (25 skipped).

Date: August 29, 2026

> **Launcher retirement (August 29, 2026):** The obsolete standalone
> `jsform.py` configuration launcher and its `frmJSForm`, `frmConfig`, and
> `frmOptions` definitions have been removed. The launcher requirements below
> are retained only as historical implementation rationale.

> **Dual-database compatibility retirement (August 29, 2026):** After supported
> applications migrated to the single application-database contract, JSForm
> removed `jsform_database`, `JSConnection`, `JSCredintials`, and
> `framework_settings`. Compatibility requirements mentioning those names below
> are retained only as historical rationale and are no longer active.

Framework owner: JSForm

Application owner: database server and name, database account provisioning,
credential-target naming, credential enrollment and rotation, and authorization
after connection

## 1. Purpose

JSForm shall protect database-password entry and minimize the time and number of
places in which a plaintext database password is retained. Existing application
callers shall remain source-compatible while protected operating-system
credential targets become the preferred framework path.

This specification addresses item 8 in the JSForm Codex Security remediation
queue: **Protect database-password entry.**

## 2. Current condition

`clsDB._getcredentials` creates its password `wx.TextCtrl` without a password
masking style. `clsDB` accepts a plaintext password, constructs two
password-bearing `DatabaseSettings` objects, and copies connector arguments into
the long-lived public compatibility dictionaries `DBCredintials` and
`JSCredintials`. `DatabaseConnections` also retains password-bearing settings
after the connection opens.

The historical `jsform.py` launcher accepted `-p/--password`, which placed the
database password in command-line state visible to process inspection, shell
history, shortcuts, and diagnostic tooling.

JSForm already provides `WindowsCredentialStore`, but `clsDB` does not accept a
protected credential target directly.

## 3. Security invariants

1. A password typed into the framework dialog shall be visually masked from the
   first rendered frame.
2. A protected credential shall be resolved as late as practical, immediately
   before connector invocation.
3. A plaintext password shall not be copied into `clsDB` public attributes,
   compatibility dictionaries, or retained framework settings after connector
   invocation returns or raises.
4. Supplying both a protected target and an explicit plaintext password shall
   fail before credential lookup or connector use.
5. Credential-provider, validation, prompt, and connector failures shall not
   echo the password or attach it to framework exception text.
6. JSForm shall not silently write, replace, migrate, or delete a Windows
   credential while opening a database connection.
7. The command-line password option shall be deprecated, hidden from normal
   help, and rejected when combined with a protected credential target.
8. No framework change shall encode an application-specific target name,
   database account, table, permission, or environment policy.

## 4. Protected credential target

`clsDB` shall append optional `credential_target` and `credential_store`
parameters after all existing parameters. Existing positional and keyword calls
through `jsform_database` shall retain their meaning.

When `credential_target` is supplied:

1. normalize and require a nonblank target;
2. reject an explicit plaintext password;
3. use the injected provider, or `WindowsCredentialStore` by default;
4. read `(stored_username, secret)` only at the final connection boundary;
5. use the stored username when no username argument was supplied;
6. fail safely if a supplied username differs from the stored username; and
7. never fall back silently to an unprotected source or unmasked prompt.

Provider access shall remain behind the existing small credential-store
protocol so tests use fictional in-memory providers rather than a real vault.

## 5. Prompt behavior

The existing dialog and its Host, Database, Username, Password, Connect, and
Cancel behavior shall remain recognizable. The password control shall use the
native wx password style. Existing supplied host, database, and username values
may still prefill their controls.

An explicit in-memory password may prefill the masked password control only
when the existing prompt contract requires the dialog for another missing
value. The dialog shall not expose a reveal toggle, copy the password to another
control, log it, or store it automatically.

Cancel shall continue to avoid attempting a connection. Empty required values
shall fail with safe framework guidance before connector invocation.

## 6. Connection boundary and retained state

`DatabaseSettings` may continue to represent connector input during the bounded
connection operation, but framework-owned state retained afterward shall be a
non-secret description containing only host, database, username, and optional
port.

The connector argument dictionary containing `password` shall be created only
for the connector call and shall not be assigned to a framework attribute.
JSForm cannot control whether a third-party connector internally retains its
arguments; that external behavior is outside this specification.

`DBCredintials` and `JSCredintials` shall retain their historical names and
mapping shape for source compatibility, but their `password` value shall be
`None` after the connection attempt. They shall retain the effective non-secret
host, database, username, and port values. This is an intentional security
change: applications must not use these compatibility dictionaries as password
storage or to open additional connections.

`DBConnection`, `JSConnection`, `CONNECTIONS`, context-manager behavior, and
single-connection ownership shall remain unchanged.

## 7. Explicit plaintext compatibility

Existing calls of
`clsDB(host, databasename, username, password, jsform_database)` shall remain
accepted for bounded transition use. JSForm shall pass the explicit password to
the connector but shall not retain it in framework-owned state afterward.

This compatibility path does not authorize passwords in source files,
configuration databases, environment snapshots, launcher shortcuts, logs, or
JSON definitions. New application code should supply a protected credential
target or perform its own protected late resolution.

## 8. Retired historical command-line launcher

Before its removal, `jsform.py` added `--credential-target` and passed it to
`clsDB`. The existing
`-p/--password` option shall remain temporarily accepted to avoid an immediate
breaking removal, but shall:

- be suppressed from normal help output;
- emit a concise `DeprecationWarning` that does not include the value;
- be rejected when `--credential-target` is also present; and
- be documented as unsafe and scheduled for removal before a stable JSForm
  release.

The launcher shall not copy either value into another dictionary or print it.
Omitting both shall continue to use the masked interactive prompt. Complete
removal of `--password` is intentionally deferred to the announced compatibility
boundary rather than performed silently in this item.

## 9. Errors and cleanup

Validation and provider errors shall use fixed safe messages without exception
text or secret-bearing chains. Connector errors shall preserve the connector
exception as a cause for programmatic diagnosis, while user-visible and logged
representations remain subject to JSForm diagnostic redaction.

Dialog destruction shall occur on connect, cancel, validation failure, and
unexpected prompt failure. Temporary local references shall be overwritten with
`None` in a `finally` block after connector invocation. This reduces accidental
retention; it is not a guarantee that immutable Python string memory is erased.

## 10. Compatibility

The following behavior shall remain compatible:

- all existing `clsDB` parameters retain their order and meaning;
- the two historical database-name arguments remain accepted;
- explicit plaintext callers still connect during the transition;
- omitted values still invoke the framework dialog;
- `DBConnection` and `JSConnection` still refer to the same application
  connection;
- `DBCredintials` and `JSCredintials` remain mappings with historical keys;
- existing close and context-manager behavior remains unchanged; and
- applications may continue resolving credentials before calling `clsDB`.

The intentional compatibility exception is that the historical credential
dictionaries no longer retain a usable plaintext password.

## 11. Documentation

Implementation shall update the framework reference, public API documentation,
launcher guidance, relevant docstrings, sample guidance where applicable, and
the JSForm roadmap. Documentation shall recommend application-specific Windows
Credential Manager targets and shall not claim that JSForm provisions database
users or application permissions.

## 12. Verification

Automated tests shall prove at minimum:

1. the password control is created with the native password-masking style;
2. cancel and validation failures do not invoke the connector;
3. existing positional explicit-password calls still connect;
4. a connector receives the correct fictional password exactly once;
5. retained settings and compatibility dictionaries contain no plaintext after
   successful or failed connection attempts;
6. target-backed lookup occurs immediately before connector invocation;
7. target plus plaintext, blank target, missing target, provider failure, and
   username mismatch fail before connector use with safe messages;
8. target-backed and application-resolved compatibility paths both work;
9. the obsolete launcher and its form definitions are absent from source and
   distribution artifacts;
10. application credential-target and masked-prompt paths remain covered;
11. no launcher command-line password path remains;
12. exceptions, logs, and object representations do not expose fictional
    passwords; and
13. the complete JSForm and ChurchManager suites remain compatible.

Tests shall use injected fake connectors, fake dialogs, and fake credential
providers. They shall not access a real credential vault or database unless an
existing guarded integration suite explicitly does so.

## 13. Completion criteria

This item is complete when the implementation, documentation, and regression
tests satisfy this specification; focused and full JSForm verification passes;
ChurchManager passes without requiring an application-policy change; and the
roadmap records the verified result.

Visual verification shall distinguish structural proof of `wx.TE_PASSWORD`
from an actual rendered inspection. The automated requirement proves the style
flag; it does not by itself claim GUI visual verification.
