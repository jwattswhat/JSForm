# DevelopmentTesting cleanup inventory

Date: August 29, 2026

Specification: `JSForm.DevelopmentTestingCleanup.Specification.md`

Review method: Static inspection only. No historical script was executed and no
database, network service, document, or GUI was opened.

The review covered all 36 tracked artifacts. No temporarily retained or migrate
classifications were required. Current supported tests already protect every
reusable behavior worth retaining.

| File | Purpose and risk | Classification | Evidence and action |
| --- | --- | --- | --- |
| `JSON.makeOS.py` | Church-specific Order of Service/database conversion with live reads and file output | Historical only | Application behavior, obsolete APIs, and side effects; delete. |
| `Overrideform.py` | ChurchManager form-override dictionary experiment | Replaced | Current form loading and override behavior is covered by `test_form_loader_defaults.py` and `test_jsform.py`; delete. |
| `TestModal.py` | Standalone wx frame/dialog experiment | Replaced | Supported lifecycle and compact-dialog tests cover reusable behavior; delete. |
| `TestNoSQLForm.py` | Obsolete `clsForms`/`clsNoSQLForm` live GUI experiment | Historical only | Imports removed APIs and opens a database/GUI; delete. |
| `ap.py` | Generic argparse list-value experiment | Historical only | No JSForm contract; delete. |
| `datetest.py` | wx date conversion experiment | Replaced | Native date conversion and controls are covered by control-value and responsive-layout tests; delete. |
| `fld.py` | Church database text-rewrite script using interpolated SQL | Historical only | Application-specific, mutating, and unsafe; delete. |
| `frmDateTimeTest.json` | Old-schema Church service DateTime form | Replaced | Current schema and DateTime controls have supported schema/control tests; delete. |
| `frmTestComboBox.json` | Old-schema Church/Propers lookup form | Replaced | Current lookup choices and schemas are covered by choice and definition tests; delete. |
| `frmTestComboBox.py` | Obsolete base-form live database/GUI launcher | Historical only | Uses removed APIs and Church-specific data; delete. |
| `functions.py` | Incomplete wx/date conversion helpers | Replaced | `control_values.py` and `fnUtil.py` provide tested conversions; delete. |
| `ittest.py` | Broken undefined positioning experiment | Historical only | No executable or supported contract; delete. |
| `richtest.py` | Minimal wx rich-text experiment | Historical only | No JSForm behavior or assertions; delete. |
| `sqlinserttest.py` | String-built INSERT experiment | Replaced | `sql_statements.py` and parameterization tests cover safe INSERT construction; delete. |
| `sqlparse.py` | Broken string-substitution SELECT prototype | Replaced | `clsSQL.py` and select-condition tests cover validated parameterized behavior; delete. |
| `sqlupdatetext.py` | String-built UPDATE experiment | Replaced | Write-statement and identifier tests cover safe updates; delete. |
| `sundays.py` | Next-weekday calculation experiment | Replaced | Supported `fnUtil.next_weekday` behavior exists; delete. |
| `temp.json` | Empty temporary file | Historical only | Contains no behavior; delete. |
| `temp.py` | Empty temporary file | Historical only | Contains no behavior; delete. |
| `test.json` | Church worship checklist sample data | Historical only | Application-specific data outside JSForm ownership; delete. |
| `testSQL.py` | Empty temporary file | Historical only | Contains no behavior; delete. |
| `testcheckbox.py` | Minimal wx checkbox experiment | Historical only | No JSForm behavior or assertions; delete. |
| `testchoices.py` | Prototype display/field choice mapping | Replaced | `clsChoice.py`, `choice_manager.py`, and current choice tests cover this contract; delete. |
| `testclsRecord.py` | Live Church database record mutation script | Replaced | Record navigation, state, and parameterized persistence tests provide safe coverage; delete. |
| `testcondition.py` | Live option expansion using SQL text substitution | Replaced | Parameterized option and SELECT-condition tests cover the secured behavior; delete. |
| `testdescriptionupdate.py` | ChurchManager form-description mutation | Historical only | Application-specific and imports a removed module; delete. |
| `testerrortrap.py` | Print-only exception experiment | Replaced | Supported error reporting and dialog tests cover framework errors; delete. |
| `testmariadb.py` | Live Church database update with a personal absolute path | Historical only | Mutating, application-specific, and machine-specific; delete. |
| `testmultipleini.py` | Broken multiple-inheritance experiment | Historical only | No JSForm contract; delete. |
| `testsqlparse.py` | Broken SQL placeholder prototype | Replaced | Current parameterized condition compiler tests cover this behavior; delete. |
| `tstFontDialog.py` | Live database-backed font dialog experiment | Replaced | Current font defaults and control tests cover reusable initialization; delete. |
| `tstLog.py` | Direct writable log prototype | Replaced | Centralized error reporting, redaction, and support-package tests supersede it; delete. |
| `tstOpenWordFile.py` | Unrestricted opening of a personal Word path | Replaced | Safe file-opening policy and action tests explicitly replace this unsafe behavior; delete. |
| `tstSetFont.py` | Standalone wx font-dialog tutorial | Historical only | Generic sample code without JSForm assertions; delete. |
| `tstWindowPanel.py` | Standalone two-window wx experiment | Historical only | No JSForm contract or assertions; delete. |
| `tstmatch.py` | Generic structural-pattern-matching experiment | Historical only | No JSForm behavior; delete. |

Generated inventory: 32 untracked `*.pyc` files under
`DevelopmentTesting/__pycache__`. These are generated debris covered by the
repository's existing bytecode ignore rule and shall be deleted with the source
directory.
