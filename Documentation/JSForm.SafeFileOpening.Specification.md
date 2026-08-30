# JSForm safe Windows file-opening specification

Status: Approved and implemented

Approved by: Rev. Jonathan C. Watt

Verified: August 28, 2026 — 396 JSForm tests passed (6 skipped) and 1,039
ChurchManager tests passed (25 skipped). The real symlink test was skipped
because Windows symlink creation was unavailable; injected reparse metadata
coverage passed. No real document was launched and the denial dialog was not
visually inspected.

Date: August 28, 2026

Framework owner: JSForm

Application owner: Approved local document roots and passive file extensions

## 1. Purpose

JSForm shall preserve the existing JSON `openfile` action while preventing a
form, database value, configuration value, or edited control from causing
Windows to open an unapproved or active target.

This specification addresses item 4 in the Codex Security remediation queue:
**Constrain Windows file-opening actions.**

## 2. Current vulnerability

`clsForm._openfileevent()` accepts a path from three sources:

- a `FilePickerCtrl`, resolved with its remembered or configured directory;
- a `TextCtrl`, used directly; or
- a `ComboBox`, populated from a database query.

Every non-`None` result is converted to text and passed directly to
`os.startfile()`. The existing control-level `invoke` permission authorizes the
button action but does not validate the target.

Consequently, a path value can currently select an executable, script,
shortcut, URL, remote share, device namespace, alternate data stream, missing
file, directory, or local file outside the application's intended document
locations.

## 3. Security invariant

Immediately before any Windows shell-opening call, JSForm shall require all of
the following:

1. an application file-opening policy has been configured;
2. the candidate represents a local, absolute, drive-rooted filesystem path;
3. the existing target resolves beneath an application-approved local root;
4. the root, path components, and target do not cross an unapproved reparse
   point;
5. the target is an existing regular file;
6. the final case-insensitive extension is approved by the application;
7. the target is not an executable, installer, script, shortcut, URL file, or
   other framework-blocked active type; and
8. validation occurs through the one boundary used by every `openfile` source.

If any condition fails, JSForm shall not call `os.startfile()` or any alternate
launcher.

## 4. Ownership boundary

The application owns:

- the local directories containing documents it permits users to open;
- the passive extensions appropriate for those documents;
- the timing of policy configuration during startup; and
- any application audit meaning associated with opening a document.

JSForm owns:

- structural Windows-path validation;
- canonical containment enforcement;
- the non-overridable active-target safety floor;
- regular-file and reparse checks;
- convergence of all `openfile` sources on the final boundary; and
- safe, application-neutral failure presentation.

JSForm shall not embed ChurchManager directories, roles, document categories,
or permission names.

## 5. Application policy contract

JSForm shall add a process-level configuration API following the repository's
existing application-icon and error-reporting configuration pattern:

```python
JSForm.configure_file_opening(
    approved_roots=[documents_directory, sermon_directory],
    passive_extensions={".pdf", ".docx", ".xlsx", ".txt"},
)
```

The exact implementation may use an immutable `FileOpenPolicy`, but the public
configuration call shall accept application paths and extensions without
requiring changes to ordinary `clsForm` constructors or JSON actions.

Policy rules:

1. configuration is explicit and process-wide;
2. no configured policy means deny all `openfile` launches;
3. roots must be existing, local, absolute directories;
4. roots are canonicalized once and validated when configured;
5. extensions are normalized to a leading dot and case-insensitive form;
6. empty, wildcard, compound-pattern, and invalid extensions are rejected;
7. an application cannot approve a framework-blocked active type; and
8. reconfiguration replaces the complete prior policy rather than silently
   merging state.

Configured file-picker directories resolve filenames but do not automatically
become security-approved roots. Form JSON and database content cannot expand
the application's policy.

## 6. Secure default and compatibility

The existing JSON contract remains unchanged:

```json
"action": ["openfile", "Document"]
```

Existing stored basenames, remembered picker directories, and configured
picker-directory fallback continue to resolve as before. `FilePickerCtrl`,
`TextCtrl`, and `ComboBox` remain supported path sources.

The intentional compatibility tightening is that `openfile` is denied until
the application configures approved roots and extensions. Previously accepted
remote, active, relative, outside-root, missing, and non-file targets are also
denied. Applications need one startup configuration call but do not need to
rewrite forms or ordinary form construction.

## 7. Canonical boundary

`file_actions.py` shall provide the single final validation/opening boundary,
provisionally:

```python
opened_path = JSForm.open_approved_file(candidate)
```

The boundary shall:

1. reject an absent or malformed policy;
2. parse and validate the candidate's Windows representation;
3. reject unsafe namespaces and non-file representations before filesystem
   access;
4. resolve the existing target strictly;
5. verify type, extension, reparse safety, and canonical root containment;
6. recheck the final target immediately before launch where practical;
7. call the Windows launcher exactly once; and
8. return the canonical opened path on success.

`clsForm._openfileevent()` shall resolve its historical source and pass that
candidate to this boundary. No branch may call `os.startfile()` directly.

## 8. Unsafe Windows representations

JSForm shall reject, at minimum:

- UNC and network paths such as `\\server\share\file.pdf`;
- extended and device namespaces such as `\\?\`, `\\.\`, and `GLOBALROOT`;
- URLs and shell schemes, including `http:`, `https:`, `file:`, `shell:`, and
  similar scheme-shaped values;
- drive-relative paths such as `C:document.pdf`;
- ordinary relative paths that have not been safely resolved by the picker
  workflow beneath an approved root;
- alternate data streams and extra colon syntax after the drive designator;
- reserved DOS device names such as `CON`, `NUL`, `AUX`, `PRN`, `COM1`, and
  `LPT1`, including names with extensions;
- paths containing null characters or invalid Windows path forms;
- directories, missing targets, and non-regular filesystem objects; and
- targets that depend on a junction, symbolic link, mount point, or other
  reparse point to escape or redirect policy.

UNC roots are not an application option in this version. Remote document
opening requires a later threat model and separate approval.

## 9. Active-target safety floor

The application extension allowlist is necessary but not sufficient. JSForm
shall always reject active or redirecting target classes, including common:

- executables and command files;
- PowerShell, JavaScript, Visual Basic, Windows Script Host, and similar
  scripts;
- installers, control-panel modules, registry files, and screen savers;
- shortcuts and Internet shortcuts such as `.lnk` and `.url`; and
- HTML application or other shell-active formats identified during
  implementation investigation.

Comparison shall use the final suffix after canonicalization and shall be
case-insensitive. Thus `report.pdf.exe` is treated as `.exe`, not `.pdf`.
Wildcard approval such as `*`, `*.*`, or an empty extension is prohibited.

JSForm shall document the concrete blocked-extension set in code and tests.
Applications may approve only passive extensions outside that set.

## 10. Root containment and reparse handling

Containment shall be determined from canonical paths using Windows
case-insensitive path semantics, not string prefixes. For example,
`C:\Documents-Old` is not beneath `C:\Documents`.

An approved root and candidate must be resolved with strict existence checks.
The implementation shall inspect the approved root and relevant path
components for Windows reparse attributes and reject unapproved redirection.
A symlink or junction shall not make an outside file appear approved.

Validation and shell launch cannot be made perfectly atomic through
`os.startfile()`. The implementation shall minimize that time-of-check to
time-of-use interval and document the residual local race rather than claiming
handle-based atomic enforcement.

## 11. Source-specific behavior

### FilePickerCtrl

`resolve_picker_file()` retains its current selection order: absolute picker
value, remembered directory, configured directory, then unresolved relative
value. Its result is still subject to the final policy. An absolute picker
value does not bypass root checks.

### TextCtrl

The live text value is treated only as a candidate path. It receives no trust
because it was typed or loaded into a text control. Unresolved relative values
are denied.

### ComboBox

The parameterized database lookup remains unchanged. Its first returned value
is treated only as a candidate and receives the same final validation. Database
origin does not imply file-opening approval.

Unsupported target-control types shall fail without launch.

## 12. Authorization and auditing

Existing form/control `invoke` authorization remains the first check and is
not replaced by path policy. Both must permit the operation.

This specification does not invent application audit semantics. The framework
may expose the canonical successful path to an application hook in a future
specification, but it shall not log full document paths or user data by
default. Policy denials are expected user-facing outcomes, not successful
open events.

## 13. Error handling and user presentation

`file_actions.py` shall expose a stable application-neutral exception, such as
`FileOpenDenied`, for policy and path rejections.

`clsForm._openfileevent()` shall catch expected denial, missing-file, and
launcher errors and show a concise message such as:

> This file cannot be opened from this application.

Messages may distinguish no selection, missing file, disallowed location, and
disallowed type when helpful, but shall not expose unnecessary full paths,
device details, or a traceback. Dialogs shall be owned by the current form.

An empty or `None` source performs no launch and returns a normal false/no-op
result. Unexpected programming errors continue through the framework's normal
error-reporting boundary rather than being broadly swallowed.

## 14. Public and documentation changes

Implementation shall update:

- `file_actions.py` public policy and opening contracts;
- `__init__.py` exports;
- `Documentation/PUBLIC_API.md`;
- `Documentation/JSForm_Framework.md`;
- the sample application's safe local policy example;
- tests; and
- the roadmap after verification.

No JSON Schema change is required because the action spelling and arguments do
not change. Both schemas shall nevertheless be regression-tested to continue
accepting the existing action.

## 15. Testing requirements

Focused tests shall verify:

1. configuration rejects absent, nonexistent, relative, UNC, device, and
   reparse-root entries;
2. extension normalization is case-insensitive and rejects wildcards and the
   framework active-type floor;
3. a regular passive file beneath an approved local root launches exactly once;
4. no configured policy denies launch;
5. outside-root absolute paths and sibling-prefix paths are denied;
6. traversal cannot escape an approved root;
7. relative, drive-relative, UNC, extended, device, URL, shell-scheme, ADS,
   reserved-device, null-containing, missing, and directory targets are denied;
8. shortcuts, scripts, installers, executables, and double-extension active
   targets are denied regardless of application input;
9. extension checks use the final case-insensitive suffix;
10. symlinks, junctions, and other reparse redirects cannot escape policy;
11. every denial proves the launcher was not called;
12. launch failures produce safe GUI handling;
13. FilePicker, TextCtrl, and ComboBox candidates all use the same final
    boundary;
14. picker basename, remembered-directory, and configured-directory behavior
    remains intact for legitimate files;
15. existing `invoke` authorization remains enforced;
16. existing `openfile` JSON remains valid in both schemas;
17. the sample configures only fictional/local test roots and passive types;
18. the complete JSForm suite passes; and
19. ChurchManager's suite passes against the updated framework.

Windows-specific reparse tests shall run on Windows. Where creating a junction
or symlink is unavailable, injected filesystem metadata tests may supplement
but shall not be represented as real reparse verification.

## 16. Acceptance criteria

The change is complete when:

1. no `openfile` source can reach the launcher without the configured policy
   and all final checks;
2. executable, script, shortcut, URL, remote, device, outside-root, and
   non-file triggers demonstrably do not launch;
3. an approved passive local document still opens through the same JSON action;
4. policy configuration remains application-neutral and application-owned;
5. an independent bypass and compatibility review finds no surviving included
   path;
6. focused tests, Windows path/reparse checks, the complete JSForm suite, and
   ChurchManager's suite pass;
7. public documentation matches the implemented contract; and
8. roadmap item 4 is marked implemented only after verification.

Rendered GUI inspection is required only before claiming the denial dialog's
visual layout was verified. Structural and behavioral tests alone shall not be
described as visual verification.

## 17. Implementation sequence after approval

1. Add policy, path-classification, active-type, and legitimate-control tests.
2. Implement explicit process-level policy configuration in `file_actions.py`.
3. Implement the one final validation/opening boundary.
4. Route FilePicker, TextCtrl, and ComboBox candidates through it.
5. Add safe user-facing denial and launcher-error handling.
6. Export and document the public contract and add the sample policy setup.
7. Challenge every source and Windows representation for bypasses and ordinary
   document regressions.
8. Run focused tests, including real Windows filesystem checks where available.
9. Perform one independent read-only bypass and regression review.
10. Correct confirmed in-scope findings and rerun focused tests.
11. Run the complete JSForm and ChurchManager suites.
12. Mark the specification and roadmap implemented only after all acceptance
    criteria pass.

## 18. ChurchManager integration boundary

This specification defines and secures the JSForm mechanism. ChurchManager
owns the actual document, sermon, and outline roots and its passive extension
choices. JSForm implementation shall not guess or encode them.

After the framework change, ChurchManager must configure its policy during
application startup before its existing `openfile` actions can launch files.
That application policy change is outside this JSForm specification and shall
be reviewed in ChurchManager's own scope. Running ChurchManager's automated
suite against JSForm does not by itself prove that its real document roots have
been configured or visually exercised.

## 19. Approval

Approval authorizes implementation of this specification within JSForm. It
does not authorize ChurchManager policy values or source changes, production
file access, opening any real document, deployment, or later security-roadmap
items.
