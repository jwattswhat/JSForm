# JSForm enhancement roadmap

Last reviewed: August 14, 2026

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

### 9. Background-operation dialog

- Run approved long operations without making the application appear frozen.
- Show Working, completion, failure, and restart-required states.
- Prevent duplicate execution while an operation is running.
- Allow the application to provide the operation and user-facing result while
  JSForm owns the reusable progress interface.

### 10. Consistent date, time, and choice controls

- Use consistent widths for date and time controls.
- Support separate side-by-side date and time fields.
- Pass normalized native values to the database layer.
- Store a choice identifier while displaying its descriptive text.
- Provide an optional All selection for filters without storing it as a record
  value.

### 11. Reusable linked-record and compact editor dialogs

- Provide read-only linked-record viewers.
- Provide compact add/edit dialogs with correct parent and sizer ownership.
- Supply standard Save, Cancel, Close, and validation behavior.
- Track parent and child windows so closing a parent safely closes its children.

### 12. Starter and customization catalogs

- Distinguish protected starters from user customizations.
- Display customized entries consistently, including the established blue
  indicator.
- Permit creating, deleting, restoring, and recovering customizations without
  overwriting starters.
- Constrain catalog access to application-approved directories.

### 13. Standard action bars and file-output behavior

- Provide compact navigation and action bars that do not consume unnecessary
  rows.
- Make actions available from menus where appropriate.
- Support sensible application-supplied default folders for save and export.
- Provide consistent confirmation and dependent-record warning dialogs.

## Capabilities that remain application-owned

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
