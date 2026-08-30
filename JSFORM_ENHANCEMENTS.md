# JSForm enhancement roadmap

Last reviewed: August 29, 2026

This is the maintained backlog for reusable JSForm framework improvements.
The former database-backed enhancement list is defunct. New framework
enhancements belong in this file.

## Ownership rule

JSForm owns reusable controls, layout behavior, screen lifecycle, validation,
and interaction patterns. Applications such as ChurchManager own their domain
rules, authorization decisions, transactional workflows, and report datasets.

The goal is to move reusable capabilities into JSForm without moving an entire
ChurchManager workflow into the framework.

## Prioritized enhancements

### 1. Centralized error logging and support package

Design: [JSForm centralized error logging and support package specification](Documentation/JSForm.ErrorLogging.Specification.md)

Implemented. JSForm provides opt-in structured JSONL error reporting with
redaction, bounded rotation and retention, chained Python/thread/wxPython hooks,
explicit caught-operation reporting, a re-raising error boundary, short support
references, UI-thread-safe user messages, and verified local support packages.
The School Bus Routes sample demonstrates configuration and user-controlled
package creation; applications remain responsible for their safe context and
the menu or settings entry that exposes the workflow.

- Capture unhandled Python exceptions, including full tracebacks.
- Capture errors raised by wxPython event handlers, worker threads, background
  operations, database calls, report generation, and approved subprocesses.
- Record the timestamp, application and JSForm versions, active screen,
  operation, database name, operating-system details, and a generated error ID.
- Never record passwords, connection credentials, message bodies, private
  record contents, or other unnecessary sensitive data.
- Show the user a concise message with the error ID and log location while
  preserving the technical traceback for support.
- Rotate logs and limit their age and total size.
- Provide a user-controlled **Create Support Package** action that gathers the
  relevant logs and safe diagnostic information into one file for support.
- Allow applications to add safe contextual details and apply additional
  redaction before anything is written or exported.
- Keep logging failures from causing a second application failure.
- Add automated coverage for Python, wxPython, worker-thread, database, and
  redaction behavior.

### 2. Standard data-grid behavior

Implemented. Catalog-style `wx.ListCtrl` screens now share double-click activation,
Delete-key permission checks, sortable columns, selection-aware actions, and
selection restoration. ID-backed application catalogs also use this sorting
and selection contract. Database-backed DataView grids preserve selection on
refresh and support explicitly enabled sortable columns. `wx.Grid` tables now
have a reusable behavior for one-click Boolean cells, row activation, sorting,
Delete-key permission checks, selection-aware actions, and selection/scroll
restoration.

- Double-click a row to edit it.
- Sort by a column header using a consistent gesture.
- Support Delete-key deletion when deletion is permitted.
- Enable or disable actions according to the current selection and record
  state.
- Provide consistent single-selection, multi-selection, and checkbox behavior.
- Preserve selection and scroll position after refreshing data.

### 3. Reliable dirty-record detection

Implemented. JSForm saves the normalized value shown by each loaded control as
its baseline and compares null/blank, numeric, Boolean, temporal, sequence,
mapping, choice, JSON, phone, and formatted control values semantically.

- Compare normalized database values rather than formatted screen text.
- Treat null, blank, date, time, datetime, numeric, Boolean, and choice values
  consistently.
- Do not report changes merely because a record was loaded, reformatted, or
  navigated.
- Provide automated tests for every supported field type.

### 4. Responsive master-detail layouts

Implemented. Forms can declare a `master_detail` layout and assign controls or
whole StaticBox groups to the master or detail pane. JSForm accounts for pane
minimums and scrollbar width, displays the panes side by side when space is
available, and stacks them below the configured breakpoint. The standalone
school-bus Route screen is the framework proof.

- Provide a reusable split or master-detail screen layout.
- Allow a scrollable list or grid beside an editing or detail panel.
- Account for scrollbars when calculating usable width.
- Support compact labels and fields, fields beneath wider labels, and
  side-by-side related fields.
- Fit the initial form to ordinary screen sizes without unnecessary scrolling
  or white space.

### 5. Ordered child-record editor

Implemented at the framework level. `OrderedChildModel` owns in-memory ordering,
simple resequencing, protected-row deletion checks, and dirty state. The standard
editor supplies Add, Edit, Delete, Move Up, Move Down, Save, Cancel, double-click,
and Delete-key behavior. Applications supply the row editor and transactional
save callback.

- Add, edit, delete, move up, and move down child rows.
- Resequence rows automatically when saved.
- Support protected rows and application-supplied deletion checks.
- Allow the application to save the parent and ordered children in one
  transaction.

### 6. Search-and-select dialog

Implemented at the framework level. Applications supply approved in-memory
rows, stable keys, displayed/searchable fields, and optional exact-value
filters. The reusable dialog provides incremental text search, sortable
columns, single or multiple selection, and returns stable record identifiers.

- Provide reusable text search, filters, sortable results, and selection.
- Support single and multiple selection.
- Allow an application to restrict the approved data source and displayed
  fields.
- Return stable record identifiers while displaying meaningful text.

### 7. Conditional formatting and status summaries

Implemented at the framework level. JSON controls may declare ordered
`conditionalformat` rules using named semantic styles. Reusable custom dialogs
may use the same formatter, direct style helper, or compact `StatusSummaryCtrl`.
Applications remain responsible for supplying status fields and summary values.

- Support declarative row and control colors based on values or validation
  state.
- Cover common states such as incomplete, customized, omitted, inactive, and
  warning.
- Provide a reusable summary area for messages such as completion counts,
  validation results, and fulfillment status.
- Keep application-specific calculations outside JSForm.

### 8. Image and database-blob control

Implemented. `ImagePickerCtrl` preserves database bytes, supports choose,
preview, replace, remove, and read-only display, retains aspect ratio, responds
to resizing, avoids enlargement unless requested, and enforces configurable
byte and pixel limits. Unsupported stored data displays a safe placeholder and
is never silently converted to `NULL`.

- Display an image stored as database bytes.
- Choose, preview, replace, and remove an image safely.
- Preserve aspect ratio and provide predictable scaling and size limits.
- Support read-only display and application-supplied validation.

### 9. Background-operation dialog — implemented

- Run approved long operations without making the application appear frozen.
- Show Working, completion, failure, and restart-required states.
- Prevent duplicate execution while an operation is running.
- Allow the application to provide the operation and user-facing result while
  JSForm owns the reusable progress interface.

### 10. Consistent date, time, and choice controls — implemented

- Use consistent widths for date and time controls.
- Support separate side-by-side date and time fields.
- Pass normalized native values to the database layer.
- Store a choice identifier while displaying its descriptive text.
- Provide an optional All selection for filters without storing it as a record
  value.

### 11. Reusable linked-record and compact editor dialogs — implemented

- Provide read-only linked-record viewers.
- Provide compact add/edit dialogs with correct parent and sizer ownership.
- Supply standard Save, Cancel, Close, and validation behavior.
- Track parent and child windows so closing a parent safely closes its children.

### 12. Starter and customization catalogs — implemented

- Distinguish protected starters from user customizations.
- Display customized entries consistently, including the established blue
  indicator.
- Permit creating, deleting, restoring, and recovering customizations without
  overwriting starters.
- Constrain catalog access to application-approved directories.

### 13. Standard action bars and file-output behavior — implemented

- Provide compact navigation and action bars that do not consume unnecessary
  rows.
- Make actions available from menus where appropriate.
- Support sensible application-supplied default folders for save and export.
- Provide consistent confirmation and dependent-record warning dialogs.

### 14. Full-screen Builder windows

Implemented. The Screen Designer, Report Designer, and Menu Designer use one
shared startup helper that maximizes each Builder before showing it, including
replacement designer windows. The helper does not alter the frame style, so
ordinary restore, minimize, maximize, and close controls remain available.
Automated coverage enforces use by all three designers. A Windows wxPython
runtime check on August 28, 2026 confirmed the window was shown and reported
`IsMaximized() == True`; this was a state check, not visual layout inspection.

### 15. Reusable GUI testing helpers

Implemented August 29, 2026. `gui_testing.py` provides bounded wx event draining,
stable named-control discovery with duplicate rejection, geometry inspection,
owned-window cleanup, client-area screenshot capture, and PNG comparison that
never overwrites an approved baseline. Applications own their screen fixtures,
fictional data, reviewed baselines, and application assertions.

- Open every JSForm Builder screen maximized by default.
- Apply the behavior consistently to the Screen Designer, Report Designer,
  Menu Designer, and future visual Builder tools.
- Preserve ordinary window controls so users can restore, minimize, or close
  a Builder after it opens.
- Add automated coverage for the shared Builder-window startup behavior and
  perform Windows GUI verification before marking this enhancement implemented.

## Codex Security remediation queue

These validated findings came from the August 28, 2026 standard Codex Security
scan. Each item records its own implementation status.

### Compatibility boundary

- Preserve existing application-facing Python calls, method names, arguments,
  JSON action names, and supported condition-placeholder syntax.
- Implement the fixes inside JSForm wherever possible. Applications should not
  need to rewrite ordinary calls or pass new required parameters.
- Security enforcement may reject configurations or values that were
  previously accepted but unsafe, including authenticated plaintext SMTP,
  executable or remote shell-open targets, and oversized image data.
- The obsolete internal `jsform.py` configuration launcher has been removed;
  this does not change applications that call `JSForm.clsDB(...)`.

1. **Parameterize dynamic SELECT-condition values — implemented.** The existing
   parent-record and option placeholder contract now compiles runtime values to
   connector parameters instead of SQL text. Record loading, lookup choices,
   linked-file lookup, and JSForm-owned schedule helpers execute the SQL and
   ordered native parameter tuple together. Malformed placeholders fail closed;
   injection, native-type, caller-propagation, and compatibility tests cover the
   boundary. See
   [the approved specification](Documentation/JSForm.SelectConditionParameterization.Specification.md).
2. **Authorize the database operation actually performed — implemented August
   28, 2026.** JSForm classifies a blank/new record as `create` and an existing
   loaded record as `update`, then delegates the matching permission decision
   to the application's policy at both the form workflow and final persistence
   boundary. Dynamic Save state, fail-closed policy errors, audit operation
   names, preassigned IDs, and compatibility are covered by automated tests.
   See [the approved specification](Documentation/JSForm.SaveAuthorization.Specification.md).
3. **Parameterize configuration and option APIs — implemented August 28,
   2026.** Existing `CONFIG` and `OPTION` calls and arguments are preserved,
   while application and framework fallback queries bind every family, type,
   and value as connector data. Cursor cleanup preserves original operation
   failures, and transaction ownership remains with the application. See
   [the approved specification](Documentation/JSForm.ConfigOptionParameterization.Specification.md).
4. **Constrain Windows file-opening actions — implemented August 28, 2026.**
   The existing `openfile` action now converges on a secure-default Windows
   boundary requiring application-approved local roots and passive extensions.
   Remote, device, URL, alternate-stream, reparse, outside-root, shortcut,
   script, installer, macro-enabled, and executable targets are rejected before
   launch. Applications retain ownership of their actual policy values. See
   [the approved specification](Documentation/JSForm.SafeFileOpening.Specification.md).
5. **Move historical SMTP secrets out of database configuration — implemented
   August 29, 2026.** Target-backed mail settings resolve protected credentials
   only at the SMTP authentication boundary. The historical facade no longer
   reads or retains `SMTP/Password`, and an explicit, parameterized migration
   verifies protected-store readback before deleting the legacy application
   row, with caller-owned transactions and compensation on failure. See
   [the approved specification](Documentation/JSForm.SMTPCredentialStorage.Specification.md).
6. **Require protected SMTP transport — implemented August 29, 2026.** The
   existing mail settings object now requires verified implicit TLS or
   STARTTLS before credential lookup or authentication. Plain SMTP is an
   explicit, unauthenticated, credential-free exception limited without DNS to
   canonical loopback addresses. See
   `Documentation/JSForm.ProtectedSMTPTransport.Specification.md`.
7. **Strengthen final diagnostic redaction — implemented August 29, 2026.**
   Common sensitive key-value, mapping, query-string, header, URI,
   command-line, and connector-error formats are redacted before persistence
   and at the final error-display boundary. Support-package construction
   recursively re-redacts valid JSONL and safely handles malformed historical
   text before hashing archive bytes. See
   `Documentation/JSForm.DiagnosticRedaction.Specification.md`.
8. **Protect database-password entry — implemented August 29, 2026.** The
   existing wxPython password field now uses native masking, `clsDB` supports
   late protected-target resolution, and connector settings plus historical
   compatibility dictionaries retain no plaintext password. The obsolete
   configuration launcher and its command-line password path have been removed;
   applications use `credential_target` or the masked prompt. See
   `Documentation/JSForm.DatabaseCredentialProtection.Specification.md`.
9. **Bound images before decoding — implemented August 29, 2026.** A shared
   header preflight now enforces encoded-byte, format, frame, width, height, and
   pixel ceilings before picker, database BLOB, ordinary report, or repeater
   image decoding. Selected files use a limit-plus-one bounded read, mutable
   report buffers use the exact validated immutable snapshot, and rejected
   stored BLOBs remain unchanged behind an unavailable placeholder. See
   `Documentation/JSForm.BoundedImageDecoding.Specification.md`.

## Repository cleanup roadmap

These items were identified by the August 29, 2026 stale-code audit. Complete
them in order, preserving reusable framework controls even when their old
bundled editor forms are retired.

1. **Remove the remaining obsolete bundled forms - implemented August 29,
   2026.** Deleted
   `frmChecklist.json`, `frmEditCheckList.json`, and `frmChoices.json`. They
   have no runtime references. The checklist forms encode application-owned
   `tblCheckList` and `tblService` behavior, while the choices form has been
   superseded by the native Choice Manager. Their package-data exposure was
   removed and distribution regression coverage added without removing reusable
   checklist controls, checklist actions, or `tblChoices` service APIs.
2. **Correct the sample connection shutdown - implemented August 29, 2026.**
   Replaced separate `DBConnection.close()` and `JSConnection.close()` calls in
   the sample with one `database.close()` call because both compatibility
   attributes now refer to the same application connection. Focused coverage
   prevents duplicate compatibility-handle shutdowns from returning.
3. **Remove tracked database dumps - implemented August 29, 2026.** Removed
   all five historical files under `BackupDB`, including four tracked dumps and
   one ignored local copy. Repository and distribution safeguards now reject
   their return while preserving legitimate sample schema SQL.
4. **Review and retire experimental development files - implemented August 29,
   2026.** A static, file-by-file inventory classified all 36 tracked artifacts
   as replaced or historical-only; no unique behavior required migration.
   Removed those files plus 32 generated bytecode files and the directory, then
   added a source-tree regression guard. The complete JSForm suite (457 passed,
   2 skipped), ChurchManager suite (1,081 passed, 25 skipped), and fresh wheel
   and source distribution verification passed. See
   `Documentation/JSForm.DevelopmentTestingCleanup.Specification.md` and
   `Documentation/JSForm.DevelopmentTestingCleanup.Inventory.md`.
5. **Prepare removal of the dual-database compatibility API - completed August
   29, 2026.** ChurchManager now uses the single application-database contract
   for startup, reports, backup/restore, test isolation, setup, and shutdown.
   This completed the supported-application prerequisite without moving
   ChurchManager behavior into JSForm.
6. **Remove the dual-database compatibility API - implemented August 29,
   2026.** Removed `jsform_database`, `JSConnection`, `JSCredintials`, and
   `framework_settings` after supported applications migrated. The public
   constructor, connection service, sample, documentation, and regression tests
   now enforce exactly one owned application database connection.

## Capabilities that remain application-owned

### Dynamic field host — implemented

- Accept an application-authorized bounded descriptor collection.
- Render short text, long text, integer, decimal, date, Boolean, single-choice,
  and multiple-choice controls in ordered sections.
- Validate and return native typed values and changed-value records without
  discovering definitions or writing application tables.
- Keep permissions, privacy, persistence, searching, reporting, and import or
  export policy application-owned.

The following ChurchManager behavior must not be moved into JSForm:

- worship-planning, Propers, reading, hymn, and participant rules;
- prayer and announcement recurrence meaning;
- attendance synchronization and visitor handling;
- accounting approval, posting, reconciliation, budgeting, and closing;
- ChurchManager authorization policy and protected operations;
- database backup identity and production/test safeguards;
- ChurchManager report datasets and email-recipient rules.

JSForm may supply reusable controls and hooks used by those workflows, but the
application remains responsible for their meaning and enforcement.

## Maintenance rules

1. Add a capability here only when it is useful beyond one ChurchManager
   screen.
2. Define a stable public interface before migrating application code.
3. Preserve compatibility for existing JSON forms unless an approved migration
   is supplied.
4. Test framework behavior in JSForm and application integration separately.
5. Update the JSForm schema and designer whenever a new declarative property is
   introduced.
6. Do not use the defunct `tblEnhancement` table as the development backlog.
