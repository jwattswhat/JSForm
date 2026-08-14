# JSForm centralized error logging and support package specification

Status: Approved

Date: August 14, 2026

Approved by: Rev. Jonathan C. Watt

Framework owner: JSForm

Application integration owner: Each JSForm application

## 1. Purpose

JSForm shall provide one centralized, reusable error-reporting service for the
framework and its applications. The service shall preserve the technical
information needed to diagnose failures while showing ordinary users a short,
understandable message and protecting credentials and private record data.

The facility shall capture unhandled Python errors, including errors raised by
wxPython event handlers. It shall also provide explicit interfaces for caught
database, reporting, background-task, and subprocess errors.

This feature is for support and diagnosis. It must not silently hide errors,
replace application validation, or turn expected user mistakes into crashes.

## 2. Goals

1. Capture every unexpected framework or application failure through a common
   service.
2. Retain the complete Python traceback and chained exception information.
3. Give each reported failure a stable error ID that the user can quote.
4. Keep the application responsive and avoid recursive logging failures.
5. Prevent passwords, credentials, and private database values from entering
   logs or support packages.
6. Keep log storage bounded through rotation and retention.
7. Let a user deliberately create one support package containing safe
   diagnostics.
8. Give applications controlled hooks for safe context, user messages, and
   redaction.

## 3. Non-goals

The first release will not:

- transmit logs automatically;
- send telemetry to JSForm, ChurchManager, or any third party;
- upload a support package;
- capture screenshots, database rows, report output, email content, or user
  documents;
- include database dumps, attachments, images, or JSON form customizations;
- replace audit logs, security logs, or accounting audit records;
- promise recovery from a corrupted Python process or operating-system crash;
- use the defunct `tblEnhancement` table.

## 4. Ownership boundary

### JSForm owns

- error-service configuration and lifecycle;
- Python, thread, and wxPython unhandled-exception hooks;
- structured log records and traceback formatting;
- error-ID generation;
- redaction and safe-value normalization;
- rotating log files and retention cleanup;
- the standard error dialog;
- safe support-package generation;
- public APIs and automated framework tests.

### Applications own

- the application name and version supplied during startup;
- classification of application operations;
- application-specific user guidance;
- any additional safe contextual fields;
- additional redaction rules;
- decisions to continue, close a screen, restart, or terminate after an error;
- the menu or settings entry that launches support-package creation;
- application tests confirming that integration does not expose private data.

Applications must not add whole records, SQL parameter values, email bodies,
password hashes, financial details, pastoral notes, or other unrestricted
objects as logging context.

## 5. Proposed public interface

The implementation shall expose a small public API from the `JSForm` package.
Names may be adjusted during implementation, but equivalent capabilities are
required.

```python
JSForm.configure_error_reporting(
    application_name="ChurchManager",
    application_version="1.0.0",
    log_directory=None,
    safe_context_provider=None,
    redactors=None,
)

JSForm.install_error_hooks(wx_application=None)

error_id = JSForm.report_exception(
    exception,
    operation="report.preview",
    screen="frmReports",
    severity="error",
    user_message=None,
    safe_context=None,
)

package_path = JSForm.create_support_package(destination)
```

Configuration and hook installation shall be idempotent. Calling either more
than once must not duplicate log records or replace an application's hooks
without preserving the existing chain.

Applications may use a context manager or decorator for expected integration
boundaries:

```python
with JSForm.error_boundary(operation="database.backup", screen="BackupRestore"):
    run_backup()
```

The context manager must re-raise by default after recording the failure.
Suppressing an exception must require an explicit option and must never be the
framework default.

## 6. Capture points

### 6.1 Main Python thread

Install a `sys.excepthook` wrapper that records unhandled exceptions and then
preserves the expected Python/application termination behavior. `KeyboardInterrupt`
and normal `SystemExit` are not errors and shall not create crash records.

### 6.2 wxPython event loop

Provide an approved wxPython integration that records exceptions escaping event
handlers. It shall display the standard error message on the UI thread and
permit the event loop to continue only when wxPython remains in a safe state.
Fatal initialization or state-corruption errors shall request an application
restart rather than pretending work may continue safely.

### 6.3 Worker threads

Install or chain `threading.excepthook` so unhandled worker-thread exceptions
are recorded. UI dialogs must be scheduled onto the wxPython UI thread. The
worker thread itself must never attempt to create or manipulate wx controls.

### 6.4 Caught operation errors

Database, report, file, email, background-operation, and subprocess boundaries
shall call `report_exception` when they catch an unexpected error. Expected
validation failures should continue to use ordinary field or workflow messages
and normally should not be recorded as exceptions.

### 6.5 Logging-system failures

The service shall guard against recursion. If the preferred log cannot be
written, it shall attempt a minimal fallback record in the operating-system
temporary directory. If that also fails, it may write a concise message to
standard error but must not raise a second exception into the application.

## 7. Error record format

The primary machine-readable log shall use UTF-8 JSON Lines: one JSON object per
error. Multiline tracebacks shall be stored as escaped JSON text so that each
physical line remains one complete record.

Each record shall include:

| Field | Required | Description |
|---|---:|---|
| `schema_version` | Yes | Version of the error-record contract. |
| `timestamp_utc` | Yes | ISO 8601 UTC timestamp. |
| `error_id` | Yes | Random, non-identifying support reference. |
| `severity` | Yes | `warning`, `error`, or `fatal`. |
| `exception_type` | Yes | Qualified Python exception type. |
| `message` | Yes | Redacted exception message. |
| `traceback` | Yes | Redacted complete traceback and exception chain. |
| `application_name` | Yes | Calling application. |
| `application_version` | When known | Calling application version. |
| `jsform_version` | When known | Installed JSForm version or commit identifier. |
| `python_version` | Yes | Python runtime version. |
| `wx_version` | When available | wxPython version. |
| `platform` | Yes | Windows and architecture summary. |
| `process_id` | Yes | Diagnostic process identifier. |
| `thread_name` | Yes | Thread that raised the exception. |
| `operation` | When known | Stable operation name supplied by caller. |
| `screen` | When known | Stable screen/form name, never its current field values. |
| `database_name` | When approved | Database name only, without credentials or connection string. |
| `database_scope` | When known | `test`, `production`, or `unknown`. |
| `context` | Optional | Allowlisted, redacted scalar diagnostic fields. |

Log records shall not contain memory addresses when a stable object name is
available. Arbitrary object `repr()` output is prohibited because it may expose
record data or credentials.

## 8. Error ID

- Every recorded failure receives a new random identifier.
- The displayed form should be short enough to read over the telephone, for
  example `CM-7F3A-29C1`.
- The full identifier may be retained internally to prevent collisions.
- The ID must not encode a username, computer name, database name, date, or
  other identifying information.
- Repeated exceptions receive separate IDs; optional fingerprinting for
  grouping may be added later and must not replace the occurrence ID.

## 9. Privacy and redaction

Redaction is mandatory and occurs before a record is serialized.

### 9.1 Always-sensitive keys

Keys containing the following terms, without regard to case, shall have their
values replaced with `[REDACTED]`:

- `password`, `passwd`, `pwd`, `secret`, `token`, `api_key`, `apikey`;
- `authorization`, `cookie`, `credential`, `connection_string`;
- `hash`, `salt`, `smtp_password`, `database_password`.

Applications may extend but not weaken this list.

### 9.2 Sensitive values

The standard redactor shall remove common credential-bearing URI forms,
authorization headers, and command-line password arguments. Database connector
objects and exception values must be converted through explicit safe adapters,
not serialized directly.

### 9.3 Context allowlist

Caller context accepts only booleans, bounded numbers, bounded strings, and
approved lists of those scalar types. Unknown nested objects are rejected or
replaced with a type label. Context field names must be registered or supplied
through the application's safe context provider.

### 9.4 User review

Before creating a support package, the dialog shall list exactly which files
will be included and state that no database or document files are included.
The user must explicitly choose the destination. Creation does not send the
package anywhere.

## 10. Storage, rotation, and retention

The default Windows location shall be:

```text
%LOCALAPPDATA%\<ApplicationName>\Logs\
```

The directory may be overridden during configuration for testing or an
approved application need. It must not default to the application source tree,
MariaDB data directory, database backup directory, or a shared network folder.

Defaults:

- active file: `errors.jsonl`;
- rotate at 2 MiB;
- retain five rotated files;
- delete files older than 30 days during startup and support-package creation;
- use process-safe unique names if exclusive access to the active file is not
  available.

The implementation shall use atomic creation/replacement where appropriate and
shall tolerate read-only or temporarily locked files.

## 11. User experience

For an unexpected recoverable error, JSForm shall show:

```text
ChurchManager could not complete this action.

Error ID: CM-7F3A-29C1
The technical details were saved in the support log.
```

The dialog may also show application-supplied next steps. Technical tracebacks
shall not be displayed in the ordinary dialog. A **Copy Error ID** action is
recommended. A **Create Support Package** action may be shown when the logging
service is fully initialized.

For a fatal error, the message shall state that the application must restart.
JSForm must not report that data was saved unless the relevant application
operation confirmed its transaction committed.

Repeated identical errors occurring in rapid succession may be grouped in the
UI to prevent a dialog storm, but each occurrence or an accurate repeat count
must remain in the log.

## 12. Support package

The support package shall be a ZIP file named approximately:

```text
ChurchManager-Support-20260814-153045.zip
```

It may contain only:

- current and retained JSForm error logs;
- a generated `manifest.json` describing included files and their SHA-256
  hashes;
- a generated `system-info.json` containing the safe version and platform
  fields from this specification;
- an optional application-supplied safe diagnostics file produced through a
  registered callback.

It shall never include:

- database dumps or database rows;
- configuration files that may contain credentials;
- email messages or recipient lists;
- reports, attachments, images, or user documents;
- audit records unless separately exported through an application-specific,
  authorized process;
- source files or Git history.

Package creation shall write to a temporary file, verify the ZIP and manifest,
and then atomically place it at the chosen destination. A failed package must
not replace an existing package.

## 13. Configuration

Framework defaults shall be safe without database configuration. Applications
may configure:

- application name, version, and short error-ID prefix;
- log directory;
- rotation size, retained-file count, and retention days within framework
  safety limits;
- safe context provider;
- additional redactors;
- user-message provider;
- fatal-error classification callback;
- optional support-package diagnostic callback.

Logging configuration must not be stored in `tblConfig` if doing so would make
error capture depend on a working database. Database options may override
nonessential preferences only after the base logger is operational.

## 14. Startup and shutdown sequence

Recommended application startup:

1. Configure the base file logger before connecting to a database.
2. Install Python and thread hooks.
3. Create `wx.App` or register the existing application instance.
4. Install the wxPython integration.
5. Add safe application version and database-scope context after each becomes
   known.
6. Start ordinary JSForm and application services.

On normal shutdown, flush and close handlers. The service must tolerate child
forms closing after the main form and late worker-thread exceptions during
shutdown.

## 15. Compatibility

- Existing JSForm applications that do not configure error reporting continue
  to work unchanged.
- Error reporting is opt-in during the first compatibility release.
- A later major version may install a minimal default logger automatically only
  after applications have had a migration period.
- No JSON form-definition changes are required for basic capture.
- A future optional form property may supply a stable operation name, but it is
  outside this first implementation.

## 16. Security considerations

- Support-package creation is a local file operation and never a network send.
- Log paths must reject traversal through application-supplied names.
- Symlinks/reparse points and destination replacement require safe handling on
  supported platforms.
- File permissions should be restricted to the current user where the operating
  system permits it.
- Exception text is untrusted; it must be rendered as plain text, never HTML.
- Logs must not serve as authorization or audit evidence.
- Redaction must run on the final formatted exception and traceback as well as
  on structured context.

## 17. Proposed modules

| Module | Responsibility |
|---|---|
| `error_reporting.py` | Configuration, reporting API, hooks, error IDs, and lifecycle. |
| `error_redaction.py` | Mandatory and application-supplied redaction. |
| `error_dialog.py` | wxPython-safe user messages and Copy Error ID behavior. |
| `support_package.py` | Safe diagnostics, manifest, hashing, ZIP creation, and verification. |

The public functions shall be exported through `JSForm.__init__`. Internal
modules must not import ChurchManager or any other application.

## 18. Testing requirements

Framework tests shall use a temporary directory and fictional values only.
They shall verify:

1. unhandled main-thread exceptions are recorded with a traceback;
2. chained exceptions preserve both causes;
3. wxPython event-handler exceptions are captured once;
4. worker-thread exceptions are captured and UI work is marshalled correctly;
5. caught database, report, subprocess, and background-operation errors can be
   reported explicitly;
6. `KeyboardInterrupt` and normal `SystemExit` do not create crash records;
7. passwords, tokens, connection strings, authorization headers, and registered
   application secrets are redacted from every field, including traceback text;
8. unsafe arbitrary context objects are not serialized;
9. rotation and 30-day cleanup enforce configured bounds;
10. a locked or unwritable primary log uses the safe fallback without a second
    exception;
11. repeated configuration and hook installation do not duplicate records;
12. error dialogs show the correct error ID and no traceback;
13. support packages contain only approved files and valid hashes;
14. support-package creation does not overwrite an existing file after failure;
15. no network calls occur during logging or package creation;
16. existing JSForm tests continue to pass without opting into the feature.

ChurchManager integration tests shall separately confirm that application
startup installs the hooks, database scope is classified correctly, sensitive
ChurchManager values are excluded, and the user can create a support package
from the approved menu location.

## 19. Acceptance criteria

The feature is complete when:

1. A deliberately raised Python error produces one redacted JSONL record with a
   full traceback and error ID.
2. A deliberately raised wxPython button-handler error produces the same result
   and a usable user dialog.
3. A deliberately raised worker-thread error is logged without manipulating wx
   controls from the worker.
4. The application can continue after a recoverable test error and requests a
   restart after a fatal test error.
5. Searching all generated logs and support-package contents finds none of the
   injected test passwords, tokens, connection strings, or private record
   values.
6. Rotation, retention, locked-file fallback, and package verification pass.
7. An ordinary user can locate the error ID and create—but not automatically
   transmit—a support package.
8. Existing applications remain functional when error reporting is not
   configured.
9. JSForm framework tests and ChurchManager integration tests both pass.
10. Documentation explains log location, retention, privacy, and the support
    workflow in nontechnical language.

## 20. Implementation sequence

1. Implement structured records, redaction, rotation, and fallback storage.
2. Add the reporting API and Python/thread hooks.
3. Add wxPython event-loop integration and the standard dialog.
4. Add support-package creation and verification.
5. Export the public API and document application startup integration.
6. Add JSForm automated tests.
7. Integrate with ChurchManager in a separate ChurchManager change.
8. Perform deliberate failure tests and user acceptance.
