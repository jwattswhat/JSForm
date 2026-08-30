# JSForm parameterized SELECT-condition specification

Status: Approved and implemented

Approved by: Rev. Jonathan C. Watt

Date: August 28, 2026

Framework owner: JSForm

Application integration owner: Each JSForm application

## 1. Purpose

JSForm shall bind every runtime value used by a table `condition` as connector
data instead of inserting that value into SQL text. Existing JSON condition
syntax, parent-record relationships, option lookups, forms, choices, linked
forms, subforms, and ordinary application calls shall retain their meaning.

This specification addresses the first item in the Codex Security remediation
queue: **Parameterize dynamic SELECT-condition values.**

## 2. Current vulnerability

`clsSQL.conditionCONFIG()` currently replaces an option placeholder with a
double-quoted option value inside the condition string. `clsSQL.condition()`
currently replaces a parent placeholder with `str(value)`. `clsSQL.select()`
then incorporates the resulting condition into a `WHERE` clause, and framework
callers execute that SQL without connector parameters.

For example, the supported definition:

```json
"condition": "PersonID = {ID}"
```

must select the child rows for the current parent. Under the current behavior,
a hostile or malformed parent value can change the SQL expression rather than
remaining one value. Option-backed placeholders have the same boundary defect.

The affected framework paths include record loading, lookup choices, linked
file lookup, and schedule helpers that execute `clsSQL.select()` output.

## 3. Security invariant

Every value obtained at runtime from a parent record or `JSForm.OPTION` shall be
passed to the MariaDB/MySQL connector as a parameter. Runtime values shall never
be SQL syntax, identifiers, operators, keywords, comments, quoting, or clause
structure, regardless of their Python type or textual contents.

Static condition expressions, table names, field lists, and `orderby` remain
trusted definition structure in this change. They are not converted into
parameters, because SQL connectors cannot bind identifiers or syntax. JSForm
shall continue to require form and table definitions to come from approved
application or framework sources.

## 4. Scope

### Included

- parent placeholders such as `{ID}` and `{PersonID}`;
- option placeholders such as `{OPTION:Lectionary:Current}`;
- multiple and repeated placeholders in one condition;
- `None`, Boolean, numeric, string, decimal, date, time, and datetime values
  supported by the database connector;
- every framework caller that executes a `clsSQL` SELECT statement;
- JSForm-owned legacy schedule helpers that currently preformat runtime values
  into SELECT conditions before calling `clsSQL`;
- compatibility tests for existing condition definitions;
- injection-regression tests for parent and option values;
- framework and public-reference documentation.

### Excluded

- parameterization of `CONFIG` and `OPTION` storage APIs, which is remediation
  item 3;
- identifier and `orderby` allowlisting;
- redesign of the JSON condition language;
- report filter conditions, which are a separate validated report expression
  language and are not SQL condition strings;
- write-statement authorization, which is remediation item 2;
- application-specific permission or record-visibility policy.

## 5. Compatibility contract

The following existing JSON remains valid and keeps the same meaning:

```json
{"condition": "Active = 1"}
{"condition": "PersonID = {ID}"}
{"condition": "Lectionary = {OPTION:Lectionary:Current}"}
{"condition": "ChurchID = {ChurchID} AND Active = 1"}
```

The placeholder spellings, field-name lookup, option lookup, table-description
keys, method names, and ordinary high-level application APIs shall not change.
Applications using `clsForm`, `clsRecord`, lookup choices, linked forms,
subforms, and framework schedule helpers shall not supply new arguments.

`clsSQL.select()` is a historically public low-level SQL-text builder. It shall
continue to return the SQL text for inspection and static definitions, but
dynamic output will contain connector placeholders rather than literal runtime
values. A new `clsSQL.select_statement()` method shall return:

```python
(sql_text, parameter_tuple)
```

All JSForm execution paths shall use `select_statement()` and call:

```python
cursor.execute(sql_text, parameter_tuple)
```

An application that directly executes `clsSQL.select()` output containing
runtime placeholders must migrate to `select_statement()`. This narrow
low-level migration is required because continuing parameterless execution
would preserve the vulnerability. Static `select()` consumers remain
compatible.

## 6. Placeholder compilation

JSForm shall compile conditions from left to right.

For each recognized runtime placeholder it shall:

1. append `%s` to the SQL condition text;
2. append the native Python value to the parameter tuple;
3. never add quotes around `%s`;
4. preserve all static condition text exactly except for placeholder
   substitution.

Example:

```text
Input condition:
ChurchID = {ChurchID} AND Status = {OPTION:Membership:Current}

Compiled SQL:
ChurchID = %s AND Status = %s

Parameters:
(42, "Active")
```

Repeated placeholders produce repeated parameters in occurrence order. JSForm
shall not deduplicate them because positional connector binding is explicit and
predictable.

## 7. Null and native-type behavior

`None` shall be passed to the connector as `None`; it shall not be rendered as
the text `NULL`. This preserves the existing result of expressions such as
`ID = {ParentID}` when the parent ID is absent: the comparison does not match a
row. Definitions that intentionally test nullness must continue to use trusted
static SQL such as `ParentID IS NULL`.

Booleans, numbers, decimals, dates, times, and datetimes shall remain native
Python values. JSForm shall not stringify, quote, locale-format, or otherwise
reinterpret them before binding.

Strings containing quotes, backslashes, semicolons, comment markers, SQL
keywords, Unicode, or line breaks shall remain one connector value.

## 8. Parser and validation behavior

Parent placeholders shall retain the current `{FieldName}` syntax. The field
must exist in the supplied parent record. A missing field shall continue to
raise a clear error rather than being treated as an empty string or SQL text.

Option placeholders shall retain the current
`{OPTION:OptionFor:OptionType}` spelling and historical argument mapping used by
`JSForm.OPTION.get_Option_Value()`. Parameterization shall not silently reverse
or rename those components.

Malformed or unterminated placeholders shall raise a condition-compilation
error before database execution. Unknown brace syntax shall not be passed
through as SQL. Error messages may identify the placeholder name and condition
location, but must not include private runtime values.

An option lookup returning `None` shall bind `None`. A lookup failure shall
retain its existing exception chain and shall not fall back to literal SQL.

## 9. Proposed implementation boundary

`clsSQL` shall own one condition compiler that returns condition text plus an
ordered parameter tuple. `select_statement()` shall combine that result with
the trusted SELECT structure. `select()` may delegate to the same compiler so
the displayed SQL and executable SQL cannot drift.

Every direct JSForm caller of `clsSQL.select()` shall be reviewed. Callers that
execute the result shall use `select_statement()` and pass both returned values
to `cursor.execute()`. Callers that only display or inspect SQL may continue to
use `select()`.

JSForm-owned helpers shall not bypass the compiler by applying `.format()` or
string interpolation to runtime SELECT-condition values first. Where a legacy
helper currently does so, it shall be converted to the existing parent-record
placeholder form and use the same compiled statement boundary. This does not
authorize JSForm to parse or reinterpret arbitrary application-supplied SQL.

No application-specific table, field, permission, or terminology shall be
added to JSForm.

## 10. Error handling

- Compilation errors occur before `cursor.execute()`.
- Database failures retain the current user-facing operation message and
  exception chaining.
- Error messages and diagnostic context must not interpolate parameter values.
- Cursor closing and existing transaction behavior remain unchanged.
- Parameterization must not convert a read failure into an empty successful
  result.

## 11. Documentation changes

The framework reference shall be updated to show parameterized behavior instead
of examples claiming that placeholders become literal SQL. It shall document
`select_statement()` for low-level callers and retain the warning that condition
structure and identifiers must come from trusted definitions.

No JSON schema change is required because the existing `condition` property and
placeholder syntax remain unchanged.

## 12. Testing requirements

Automated tests shall verify:

1. a parent integer produces `%s` and a one-item parameter tuple;
2. a parent string containing quotes, semicolons, comments, and SQL keywords is
   absent from SQL text and present unchanged as one parameter;
3. an option value containing the same hostile characters is bound identically;
4. multiple and repeated placeholders preserve occurrence order;
5. `None` is bound as native `None` and preserves current no-match semantics;
6. Boolean, numeric, decimal, date, time, and datetime values remain native;
7. a missing parent field fails before database execution;
8. malformed and unknown placeholders fail closed;
9. option placeholder component mapping remains historically compatible;
10. static conditions produce no parameters and retain their SQL text;
11. record loading, choices, linked-file lookup, and schedule helpers pass the
    parameter tuple to `cursor.execute()` and do not preformat runtime values;
12. connector failures retain existing wrapping and cursor cleanup;
13. existing JSForm tests pass without form-definition migrations;
14. the School Bus Routes sample definitions still validate and load;
15. a repository search finds no framework execution of dynamic
    `clsSQL.select()` output without its parameter tuple.

Database-independent tests shall use fake cursors and fictional values. The
read-only `JSFormTest` checks may be run as an additional integration gate but
are not required to prove that hostile values stay outside SQL text.

## 13. Acceptance criteria

The change is complete when:

1. the original parent-value injection example cannot place its value into SQL
   text;
2. the equivalent option-value injection example cannot place its value into
   SQL text;
3. every affected JSForm SELECT execution passes connector parameters;
4. ordinary parent, option, linked-form, subform, choice, and schedule behavior
   remains intact;
5. malformed placeholders fail before database access;
6. focused security tests and the full JSForm suite pass;
7. the framework documentation describes the final contract accurately;
8. the roadmap records implementation only after the tests pass.

## 14. Implementation sequence after approval

1. Add the shared condition compiler and `select_statement()` contract.
2. Convert all JSForm SELECT execution callers to pass parameters.
3. Add parent, option, native-type, malformed-placeholder, and injection tests.
4. Add caller-level tests proving parameter tuples reach fake cursors.
5. Update the framework reference and low-level migration guidance.
6. Run focused security reproductions and legitimate controls.
7. Perform an independent bypass and regression review.
8. Run the complete JSForm suite.
9. Mark roadmap item 1 implemented only after verification succeeds.

## 15. Approval

Approval authorizes implementation of this specification within JSForm. It does
not authorize the later security-remediation items, changes to ChurchManager,
database migrations, production-database access, or deployment.
