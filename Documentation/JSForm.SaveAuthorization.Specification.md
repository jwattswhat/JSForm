# JSForm create-versus-update save authorization specification

Status: Approved and implemented

Approved by: Rev. Jonathan C. Watt

Date: August 28, 2026

Verified: August 28, 2026 — 369 JSForm tests passed (5 skipped) and 1,039
ChurchManager tests passed (25 skipped).

Framework owner: JSForm

Application integration owner: Each JSForm application

## Ownership boundary

The application owns authorization policy. It defines permission names, roles,
user assignments, policy meaning, administrative rules, and the final allow or
deny decision. JSForm shall not contain ChurchManager permissions, infer roles,
or decide which people may create or update application records.

JSForm owns only framework enforcement mechanics: determining whether its own
save path is about to perform an INSERT or UPDATE, selecting the corresponding
application-declared permission key, invoking the application-supplied policy,
and refusing to cross the persistence boundary when that policy denies or
fails. JSForm asks the application; it does not answer for it.

## 1. Purpose

JSForm shall enforce the application's authorization decision for the database
operation a save will actually perform.
Saving a new or automatically generated blank record shall require the form's
`create` permission. Saving a record that was loaded from the database shall
require its `update` permission. The matching application-declared permission
shall be checked through the application-supplied policy in the user-facing
form workflow and rechecked at the final persistence boundary.

This specification addresses item 2 in the Codex Security remediation queue:
**Authorize the database operation actually performed.**

## 2. Current vulnerability

`clsForm.save_record()` currently checks `update` permission before every save.
`clsRecord.update_current_record_in_DB()` later and independently chooses an
INSERT when the saved original record ID is blank, or an UPDATE when it is not.

This creates two broken authorization paths:

1. a user with `update` but without `create` can save a blank record and cause
   an INSERT; and
2. application or framework code that calls the record persistence method
   directly bypasses the form-level permission check entirely.

The standard Update button also reflects only `update` permission, even when
the current record is an automatically generated blank record whose save would
perform a create operation.

## 3. Security invariant

Immediately before a database write, JSForm shall derive the pending operation
from trusted record state and require the corresponding permission:

- original saved ID is blank: `create` permission and INSERT;
- original saved ID is present: `update` permission and UPDATE.

The current editable ID is not sufficient to classify the operation. A new
record may receive an application-assigned ID before its first save and must
still require `create` permission.

Authorization failure, policy failure, or indeterminate record state shall
prevent cursor creation, SQL execution, commit, original-snapshot replacement,
success auditing, and success notification.

## 4. Scope

### Included

- standard `clsForm.save_record()` calls;
- the standard Update/Save button and registered `record.save` command;
- records created through `new_record()`;
- blank records automatically created when a SELECT returns no rows;
- new records with database-generated IDs;
- new records with application-assigned IDs;
- existing records loaded from the database;
- the final `clsRecord` INSERT/UPDATE boundary;
- dynamic Update/Save button authorization for the current record state;
- correct create/update audit operation names and success messages;
- compatibility for forms without declared security permissions.

### Excluded

- delete authorization, which already has its own operation;
- field-level view and edit permissions;
- application role definitions or permission meanings;
- database-account privileges;
- schema or database migrations;
- bulk import, accounting posting, or application-owned transactional services;
- authorization of SELECT conditions, addressed by remediation item 1;
- redesign of record navigation or dirty-state behavior.

## 5. Existing JSON contract

The current form security declaration remains unchanged:

```json
"security": {
  "open": "people.records.view",
  "create": "people.records.create",
  "update": "people.records.edit",
  "delete": "people.records.delete"
}
```

No new JSON properties or permission-name conventions are introduced. Existing
schemas already define `create` and `update` separately.

When an operation has no declared permission, existing compatibility behavior
continues: that operation has no framework-level permission requirement. This
does not override an application policy or database restriction.

## 6. Canonical operation classification

`clsRecord` shall expose one operation-classification method, provisionally:

```python
operation = records.pending_save_operation()
```

It shall return exactly `"create"` or `"update"` by examining the saved
original-record identity used by persistence itself.

Rules:

1. If no current record exists, classification fails closed.
2. If no original snapshot exists for the current record, classification fails
   closed rather than guessing from the editable record.
3. An original ID of `None` or the framework's normalized blank value means
   `create`.
4. Any nonblank original ID means `update`.
5. Changing or preassigning the current record's ID does not change a pending
   create into an update.
6. The persistence branch shall use this same classification result; it shall
   not duplicate the test with different rules.

The operation may be computed again at the final boundary so a stale UI
decision cannot control persistence.

## 7. Form workflow authorization

`clsForm.save_record()` shall:

1. classify the pending operation;
2. call the existing user-facing authorization path for that operation;
3. stop before validation or persistence if authorization is denied;
4. perform required-field validation;
5. copy control values into the in-memory current record;
6. invoke the persistence method, which reclassifies and reauthorizes;
7. audit the actual `create` or `update` operation only after commit;
8. show an operation-appropriate success message.

The public method name and arguments remain unchanged. Standard buttons and
registered menu commands continue to call `save_record()`.

If authorization changes between the form check and persistence, the final
check wins. Control values already copied into the in-memory record may remain
as unsaved dirty values, but no database write, saved-original replacement, or
success indication may occur.

## 8. Final persistence authorization

`clsRecord` shall accept an optional application-supplied operation-authorizer
callback through a
backward-compatible constructor argument, provisionally:

```python
records = JSForm.clsRecord(
    connection,
    table,
    operation_authorizer=form_security.require,
)
```

Immediately before constructing or executing an INSERT or UPDATE,
`update_current_record_in_DB()` shall:

1. call `pending_save_operation()`;
2. call the configured authorizer with `"create"` or `"update"`;
3. propagate authorization denial without converting it into a database error;
4. execute only the SQL branch matching that operation.

JSForm-created secured forms shall pass their `FormSecurity.require` adapter,
which delegates the decision to the application's authorization policy, to
their primary `clsRecord`. The callback remains optional for direct
legacy `clsRecord` users that have no form security context, preserving the
existing low-level API. Applications using `clsRecord` directly and requiring
authorization shall supply the callback.

The default `FormSecurity` compatibility policy allows undeclared operations,
so existing forms that do not declare security continue to save normally while
still using the same final-boundary check.

## 9. Automatically generated blank records

When record loading returns no rows, JSForm creates a blank in-memory record.
That record's saved original ID is blank and its pending operation is `create`.

The standard Update/Save control shall therefore be enabled only when `create`
is allowed for that record. It shall not be enabled merely because `update` is
allowed. An existing loaded record shall use `update` authorization.

Starting a record through `new_record()` continues to require `create`
permission before the blank record is added. Saving it rechecks `create` at the
final boundary.

## 10. Navigation and presentation state

`apply_navigation_security()` shall determine the Update/Save button's required
operation from the current record state. Button state is advisory and shall
never replace the final authorization check.

- New button: based on `create`.
- Save/Update button on a new or automatic blank: based on `create`.
- Save/Update button on an existing record: based on `update`.
- Delete button: based on `delete`.

Navigation, refresh, or selection changes shall refresh this presentation state
using the newly current record. If state cannot be classified, the Save/Update
button shall be disabled.

## 11. Policy failures and error handling

An explicit denial and an exception raised by an application authorization
policy shall both fail closed.

- The ordinary form workflow shows the existing plain-language Access Denied
  message and no success message.
- The persistence boundary raises `AuthorizationDenied`, preserving the
  underlying exception chain when a policy failed.
- Authorization errors are not translated into insert/update database errors.
- Authorization error messages identify the operation and form, not private
  record values or permission internals.
- Database rollback behavior remains unchanged for failures after SQL execution.
- No rollback is required when authorization prevents opening a cursor.

## 12. Auditing

A successful INSERT shall invoke the application audit hook with operation
`create`. A successful UPDATE shall use operation `update`.

Denied or failed operations shall not produce success audit events. Applications
may separately log authorization denials through their policy or diagnostic
integration, but JSForm shall not invent application audit semantics.

The audit record ID for a successful create shall use the final assigned ID.

## 13. Compatibility

- Existing form JSON remains valid.
- `clsForm.save_record()` retains its name, arguments, and Boolean result.
- `clsRecord.update_current_record_in_DB()` retains its name and arguments.
- Existing two-argument `clsRecord(connection, table)` construction remains
  valid.
- Forms without security declarations retain allow-compatible behavior.
- Application-assigned primary keys on new records remain INSERTs.
- Existing records remain UPDATEs.
- Required-field validation, dirty tracking, transaction handling, record
  navigation, and confirmation behavior remain otherwise unchanged.

The security correction intentionally denies two previously accepted unsafe
cases: creating with update-only permission and updating with create-only
permission.

## 14. Documentation changes

The framework reference shall document:

- the canonical pending-operation rule;
- create versus update authorization during save;
- the final-boundary recheck;
- automatic blank-record behavior;
- the optional low-level authorizer callback; and
- audit operation names.

No JSON schema change is required because the separate create and update
properties already exist.

## 15. Testing requirements

Automated tests shall verify:

1. a blank new record requires `create`, not `update`;
2. an automatically generated blank record follows the same rule;
3. an existing loaded record requires `update`, not `create`;
4. an application-assigned ID on a new record still requires `create` and uses
   INSERT;
5. a database-generated ID on a new record requires `create` and uses INSERT;
6. an existing record uses UPDATE;
7. update-only permission cannot produce INSERT SQL;
8. create-only permission cannot produce UPDATE SQL;
9. direct persistence on a form-owned `clsRecord` rechecks authorization;
10. permission revocation between form check and persistence prevents SQL;
11. authorization-policy exceptions fail closed without opening a cursor;
12. absent or inconsistent record state fails closed without opening a cursor;
13. denied saves do not commit, replace the original snapshot, audit success,
    or show a success message;
14. successful creates audit `create` with the assigned ID;
15. successful updates audit `update`;
16. the Save/Update button uses create permission for blank records and update
    permission for loaded records;
17. navigation and refresh recalculate the button state;
18. undeclared permissions preserve legacy-compatible form saving;
19. existing preassigned-primary-key tests continue to pass;
20. registered `record.save` commands still use `form.save_record()`;
21. all JSForm tests pass; and
22. ChurchManager's application-only suite passes against the updated JSForm.

Tests shall use fictional records, fake policies, and fake database connections.
Denied-path tests shall assert that no cursor or SQL execution occurred.

## 16. Acceptance criteria

The change is complete when:

1. a deliberately attempted INSERT with update-only permission is denied before
   SQL execution;
2. a deliberately attempted UPDATE with create-only permission is denied before
   SQL execution;
3. revoking permission after the initial form check still prevents persistence;
4. new and existing records retain correct legitimate save behavior;
5. preassigned primary keys retain INSERT behavior;
6. presentation state matches the pending operation but cannot bypass the final
   check;
7. audit events use the actual committed operation;
8. focused authorization tests, the complete JSForm suite, and ChurchManager's
   application suite pass;
9. documentation describes the implemented contract accurately; and
10. the roadmap is marked implemented only after verification.

## 17. Implementation sequence after approval

1. Add canonical pending-operation classification to `clsRecord`.
2. Add the optional persistence authorizer and final-boundary requirement.
3. Pass `FormSecurity.require` when JSForm constructs a form-owned record set.
4. Make `save_record()` authorize and audit the classified operation.
5. Make Update/Save button state follow the current pending operation.
6. Add denied-path, policy-failure, preassigned-ID, audit, and button-state tests.
7. Update the framework reference and public docstrings.
8. Perform an independent bypass and regression review.
9. Run the complete JSForm and ChurchManager suites.
10. Mark roadmap item 2 implemented only after all acceptance checks pass.

## 18. Approval

Approval authorizes implementation of this specification within JSForm. It does
not authorize later security-remediation items, ChurchManager source changes,
database migrations, production-database access, deployment, or changes to
application-defined permission meanings.
