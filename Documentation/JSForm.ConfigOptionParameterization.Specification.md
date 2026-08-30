# JSForm configuration and option API parameterization specification

> **Superseded storage boundary (August 28, 2026):** JSForm no longer owns or
> queries `jsConfig` or `jsOptions`. Only application-owned `tblConfig` and
> `tblOptions` remain. Framework-fallback requirements below are retained as
> historical rationale and are no longer active product requirements.

Status: Approved and implemented

Approved by: Rev. Jonathan C. Watt

Verified: August 28, 2026 — 382 JSForm tests passed (5 skipped) and 1,039
ChurchManager tests passed (25 skipped).

Date: August 28, 2026

Framework owner: JSForm

Application owner: Configuration and option meanings, permitted values, and
transaction boundaries

## 1. Purpose

JSForm shall prevent runtime configuration and option values from changing the
structure of SQL executed by the public `CONFIG` and `OPTION` storage APIs.
Every family, type, key, and stored value shall be passed separately through
MySQL Connector parameters.

This specification addresses item 3 in the Codex Security remediation queue:
**Parameterize configuration and option APIs.**

## 2. Current vulnerability

The five SQL-emitting methods in `clsConfig.py` and `clsOption.py` currently
insert their arguments into SQL text with Python string formatting:

- `CONFIG.get_Config_Value(ConfigFamily, ConfigType)`;
- `CONFIG.get_Config_Family(configfamily)`;
- `CONFIG.set_Config_Value(ConfigFamily, ConfigType, ConfigValue)`;
- `OPTION.get_Option_Value(optionfor, optiontype)`; and
- `OPTION.set_Option_Value(optionfor, optiontype, optionvalue)`.

Both the application-table lookup and framework-table fallback lookup are
affected. Quote-bearing input can alter lookup predicates, widen an update's
`WHERE` clause, or change its `SET` expression. Disabling stacked statements
does not prevent those attacks.

The inputs are reachable through the public Python API and, for some reads,
through application JSON definitions such as `{OPTION:...}` and configured
file-directory keys.

## 3. Security invariant

For every query executed by these APIs:

1. SQL structure, table names, and column names shall be static framework code.
2. Every runtime family, type, key, and value shall appear only in the
   connector parameter tuple.
3. No runtime value shall be quoted, escaped, concatenated, formatted, or
   otherwise copied into SQL text.
4. The application-table and framework fallback paths shall enforce the same
   rule.
5. Cursor cleanup shall occur on successful and failed execution paths.

Strings containing quotes, comment markers, semicolons, percent signs,
backslashes, Unicode, or SQL keywords must remain ordinary data.

## 4. Ownership boundary

Applications continue to own:

- the meanings of configuration families, option groups, types, and values;
- which values an application permits;
- who may edit configuration or options;
- transaction boundaries and commit policy; and
- any application-specific validation or authorization.

JSForm owns only safe execution of its reusable storage API. It shall not
introduce ChurchManager terminology, permission names, allowlists, or policy.

Parameterization does not make an application-supplied value semantically
valid; it only prevents that value from becoming SQL structure.

## 5. Included scope

The implementation shall update all SQL execution paths within:

- `clsConfig.get_Config_Value()`;
- `clsConfig.get_Config_Family()`;
- `clsConfig.set_Config_Value()`;
- `clsOption.get_Option_Value()`; and
- `clsOption.set_Option_Value()`.

This includes queries against:

- application `tblConfig`;
- framework `jsConfig`;
- application `tblOptions`; and
- framework `jsOptions`.

The framework reference, public docstrings, focused tests, and roadmap status
shall be updated with the implementation.

## 6. Excluded scope

This item shall not:

- change public method names, argument order, or singleton exports;
- change the historical `{OPTION:...}` component mapping;
- change table names, column names, or schemas;
- add inserts, upserts, deletes, affected-row results, commits, or rollbacks;
- redesign generic record persistence or SELECT-condition compilation;
- change application-versus-framework precedence;
- change missing-value or database-error behavior except as required for safe
  cursor cleanup;
- correct the historical tuple-shaped framework fallback result in
  `get_Option_Value()`;
- change `set_Config_Value()`'s historical update predicate;
- repair the separate two-argument font-setter calls; or
- parameterize unrelated legacy SQL APIs.

Those observable defects may be specified and corrected separately. They shall
not be bundled into this security boundary without separate approval.

## 7. Public compatibility contract

The following calls remain valid and retain their signatures:

```python
JSForm.CONFIG.get_Config_Value(family, config_type)
JSForm.CONFIG.get_Config_Family(family)
JSForm.CONFIG.set_Config_Value(family, config_type, value)
JSForm.OPTION.get_Option_Value(option_for, option_type)
JSForm.OPTION.set_Option_Value(option_for, option_type, value)
```

`CONFIG` and `OPTION` remain package-level singleton objects. Directly
constructed `clsConfig` and `clsOption` instances remain supported.

If no application connection has been configured, existing methods continue
to return `None`. Reads continue to check the application table first and use
the framework table only under the existing fallback conditions. Writes
continue to target the application table only.

## 8. Required SQL contract

Each execution shall use MySQL Connector's two-argument form:

```python
cursor.execute(sql_text, parameters)
```

Representative statements are:

```sql
SELECT ConfigValue FROM tblConfig
WHERE ConfigFamily = %s AND ConfigType = %s;

SELECT ConfigType, ConfigValue FROM jsConfig
WHERE ConfigFamily = %s;

UPDATE tblOptions SET OptionValue = %s
WHERE OptionFor = %s AND OptionType = %s;
```

The ordered parameter tuples shall match placeholder order exactly. Bound
values shall be passed in their supplied Python representation; JSForm shall
not manually quote or stringify them. `None`, when supplied, is therefore
connector data rather than SQL text.

Static identifiers cannot be connector parameters and remain hard-coded.

## 9. Lookup and fallback behavior

Configuration reads retain this order:

1. query application `tblConfig`;
2. if the existing behavior treats the result as missing, query framework
   `jsConfig`; and
3. return the historically produced value or row collection.

Option reads retain the equivalent `tblOptions` then `jsOptions` order.

Both queries must be independently parameterized. A safe primary query does
not compensate for an unsafe fallback query.

For compatibility, this item preserves the current broad application-read
fallback behavior and propagation of framework-fallback errors. It also
preserves current missing-result behavior and the option fallback's historical
return shape. Tests shall characterize these boundaries so parameterization
does not accidentally redesign them.

## 10. Update behavior and transactions

Updates shall retain their current table targets, predicates, and implicit
`None` return values. Only value transport changes.

In particular:

- `set_Config_Value()` retains its existing `ConfigType`-based predicate and
  assignment of `ConfigFamily` and `ConfigValue`;
- `set_Option_Value()` retains its existing `OptionFor` and `OptionType`
  predicate; and
- neither method shall call `commit()` or `rollback()`.

This preserves application-owned transaction behavior. Correcting predicates
or introducing upsert behavior requires a separate specification.

## 11. Error and resource handling

Parameterization shall not translate connector errors into new public exception
types. Existing fallback-versus-propagation behavior remains as described
above.

Every successfully created cursor shall be closed through a `finally` path,
including when `execute()`, `fetchone()`, or `fetchall()` raises. Cursor cleanup
must not mask the original connector failure. No cursor shall be referenced if
cursor creation itself failed.

## 12. Direct callers and integration behavior

Existing callers require no argument changes. This includes:

- form and JSON Schema locations;
- date, time, SQL-format, report, font, and SMTP configuration reads;
- file-picker and file-opening configuration keys;
- form-schema options;
- StaticText `{OPTION:...}` expansion; and
- option lookup performed while compiling a parameterized SELECT condition.

The outer SELECT-condition compiler shall continue to bind the fetched option
value separately. This specification additionally secures the inner option
table lookup that obtains that value.

## 13. Documentation changes

Implementation shall update `Documentation/JSForm_Framework.md` to state that:

- configuration and option keys and values are connector parameters;
- application-table and framework fallback reads are both protected;
- application meanings and validation remain application-owned; and
- setters retain caller-owned transaction behavior.

Public method docstrings shall describe the parameters, return behavior,
fallback order, and transaction boundary. No JSON Schema change is required.

## 14. Testing requirements

Focused tests shall use fake connections and cursors to verify:

1. application config-value lookup sends static SQL and an ordered parameter
   tuple;
2. config-value fallback parameterizes both application and framework queries;
3. config-family primary and fallback queries are parameterized;
4. config update binds family, type, and value separately;
5. option primary and fallback lookups are parameterized;
6. option update binds option group, type, and value separately;
7. hostile values containing quotes, comments, semicolons, Unicode, percent
   signs, and backslashes never appear in SQL text;
8. native values, including `None`, are not manually stringified;
9. every `execute()` receives `(sql_text, parameter_tuple)`;
10. cursors close after success and after execute/fetch failure;
11. the existing application-first fallback and error behavior remains;
12. current missing-result behavior remains characterized;
13. the current option fallback return shape remains characterized;
14. setters do not commit or roll back;
15. `set_Config_Value()` retains its existing predicate;
16. `clsSQL.compile_condition()` performs a parameterized inner option lookup
    and still binds the resulting value in the outer SELECT;
17. StaticText option expansion retains its current component mapping;
18. public method signatures and `CONFIG`/`OPTION` exports remain compatible;
19. the complete JSForm suite passes; and
20. ChurchManager's application suite passes against the updated framework.

Tests shall use fictional data and shall not connect to production databases.

## 15. Acceptance criteria

The change is complete when:

1. no runtime argument to the five included methods appears in executed SQL
   text;
2. both primary and fallback reads pass values only as connector parameters;
3. hostile lookup and update values cannot alter predicates or assignments;
4. all established public signatures, precedence, return, error, and
   transaction behavior remain within the approved compatibility boundary;
5. cursor cleanup is reliable and does not hide the original failure;
6. an independent bypass and compatibility review finds no surviving included
   path;
7. focused tests, the full JSForm suite, and ChurchManager's suite pass;
8. framework documentation matches the implemented behavior; and
9. roadmap item 3 is marked implemented only after verification.

## 16. Implementation sequence after approval

1. Add focused characterization and injection tests for both modules.
2. Replace formatted values in all five methods and both fallback paths with
   `%s` placeholders plus ordered parameter tuples.
3. Make cursor cleanup exception-safe without changing public error policy.
4. Challenge every changed method and direct caller for a surviving sink or
   legitimate-input regression.
5. Update docstrings and the framework reference.
6. Run focused tests.
7. Perform one independent read-only bypass and regression review.
8. Correct any confirmed in-scope findings and rerun focused tests.
9. Run the complete JSForm and ChurchManager suites.
10. Mark the specification and roadmap implemented only after all acceptance
    criteria pass.

## 17. Approval

Approval authorizes implementation of this specification within JSForm. It
does not authorize the excluded behavioral corrections, ChurchManager source
changes, schema changes, production-database access, deployment, or later
security-remediation items.
