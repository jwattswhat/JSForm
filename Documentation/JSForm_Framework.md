# JSForm Framework Documentation

## Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Requirements and project layout](#requirements-and-project-layout)
4. [Quick start](#quick-start)
5. [Application startup](#application-startup)
6. [Database contract](#database-contract)
7. [JSON form files](#json-form-files)
8. [Form properties](#form-properties)
9. [Table descriptions and record loading](#table-descriptions-and-record-loading)
10. [Common control properties](#common-control-properties)
11. [Control reference](#control-reference)
12. [Choices and lookups](#choices-and-lookups)
13. [Actions and event binding](#actions-and-event-binding)
14. [Linked forms and subforms](#linked-forms-and-subforms)
15. [Record lifecycle](#record-lifecycle)
16. [Configuration, options, and fonts](#configuration-options-and-fonts)
17. [Reports](#reports)
18. [Public Python API](#public-python-api)
19. [Schema validation](#schema-validation)
20. [Testing and debugging](#testing-and-debugging)
21. [Security](#security)
22. [Current limitations and compatibility notes](#current-limitations-and-compatibility-notes)
23. [Application-development checklist](#application-development-checklist)

## Overview

JSForm is a Python and wxPython framework for building MySQL/MariaDB desktop data-entry applications from JSON form definitions. A form file describes the window, database query, controls, positioning, choices, actions, and relationships to other forms. The Python framework turns that description into a working interface with record navigation and persistence.

The framework is especially suited to traditional line-of-business applications in which screens correspond closely to database tables. Its principal features are:

- JSON-defined windows and controls.
- Automatic conversion between character-based layout units and pixels.
- MySQL/MariaDB record loading, insertion, updating, and deletion.
- Built-in New, Update, Delete, First, Previous, Next, Last, and Close buttons.
- Database-backed combo-box choices and lookup IDs.
- Required-field checking and dirty-record detection.
- Linked forms and embedded subforms.
- Date, time, numeric, checklist, file, HTML, list, and data-view controls.
- Optional JSON Schema validation.
- Native JSON-defined PDF reports and visual report design.
- Database-backed configuration, options, and font settings.

This document describes the implementation in this repository. Where the older text documentation, JSON Schema, examples, and Python implementation disagree, the Python implementation is treated as authoritative and the disagreement is noted.

## Architecture

The principal modules are:

| Module | Responsibility |
| --- | --- |
| `__init__.py` | Exposes the framework's public classes, singletons, and utility functions. |
| `clsForm.py` | Loads a form definition, creates the window and controls, loads records, binds events, and manages record editing. |
| `clsField.py` | Implements the control factory and individual wxPython control wrappers. |
| `clsDB.py` | Opens application and JSForm database connections and implements the in-memory record collection. |
| `clsSQL.py` | Constructs SQL and converts values between database and control representations. |
| `clsChoice.py` | Supplies literal, shared, and table-backed choices. |
| `clsConfig.py` | Reads and writes configuration values. |
| `clsOption.py` | Reads and writes application options. |
| `clsFont.py` | Creates the configured wxPython font and performs layout conversions. |
| `clsConstant.py` | Defines framework constants, allowed wxPython parameters, and standard buttons. |
| `report_renderer.py` | Renders approved report datasets from JSON definitions to PDF. |
| `report_designer.py` | Provides the visual report-layout editor. |
| `report_catalog.py` | Manages protected report starters and user customizations. |
| `menu_designer.py` | Provides the visual application-menu editor. |
| `menu_catalog.py` | Manages protected menu starters and user customizations. |
| `window_icons.py` | Configures and applies framework or application icons. |
| `fnUtil.py` | Provides layout, date, connectivity, and database helper functions. |
| `clsSMTP.py` | Historical compatibility email wrapper. New work uses `mail_service.py`. |
| `mail_service.py` | Provider-neutral email validation, privacy-safe delivery, attachments, and SMTP transport. |
| `dynamic_fields.py` | Application-neutral typed dynamic-field descriptors, validation, controls, and change sets. |
| `fnSchedule.py` | Application-specific scheduling and notification functions. It is not required by the core form engine. |

A typical runtime flow is:

1. Create `wx.App`.
2. Create `JSForm.clsDB`.
3. Give the connection wrapper to `CONFIG`, `OPTION`, and `FONT`.
4. Load the configured font.
5. Create a `JSForm.clsForm` using a JSON form name.
6. Optionally bind application-specific events.
7. Show the form and enter the wxPython main loop.

## Requirements and project layout

The checked-in `requirements.txt` lists the historical runtime dependencies. The central dependencies are:

- Python 3.10 or a compatible Python 3 release.
- wxPython.
- MySQL Connector/Python.
- `jsonschema` for optional form validation.
- `requests` for the connectivity helper.
- `yagmail` for `clsSMTP`.

The repository's checked-in `.venv` is machine-specific and should not be considered portable. Create a fresh environment on each development machine.

The intended package layout is a directory named `JSForm` containing `__init__.py` and the framework modules. Application code normally runs from the parent directory so that `import JSForm` resolves the package correctly.

Important directories are:

| Directory | Contents |
| --- | --- |
| `Forms/` | JSON form definitions included with the framework. |
| `Documentation/` | Human-readable design and usage documentation. |
| `schema/` | Experimental or newer schema-validation work. |
| `reports/` | Generated or sample PDF reports. |
| `BackupDB/` | Historical SQL dumps. Treat these as sensitive. |
| `DevelopmentTesting/` | Exploratory scripts and control experiments. |

## Quick start

### 1. Create the table

Every editable table must expose a field named `ID`. The normal convention is an auto-incrementing integer primary key.

```sql
CREATE TABLE tblPerson (
    ID INT NOT NULL AUTO_INCREMENT,
    FirstName VARCHAR(100),
    LastName VARCHAR(100) NOT NULL,
    Active TINYINT(1) NOT NULL DEFAULT 1,
    Notes LONGTEXT,
    PRIMARY KEY (ID)
);
```

### 2. Create `Forms/frmPerson.json`

The filename is the form name plus `.json`. The root object key must be the form name plus `FORM`.

```json
{
  "frmPersonFORM": {
    "FORM": {
      "name": "frmPerson",
      "type": "Panel",
      "title": "People",
      "posch": [-1, -1],
      "sizech": [45, 24],
      "stylelist": ["CAPTION"],
      "controls": ["Navigation", "Close"],
      "table": {
        "name": "tblPerson",
        "fields": ["ID", "FirstName", "LastName", "Active", "Notes"],
        "orderby": "LastName, FirstName"
      }
    },
    "CONTROLS": {
      "lblFirstName": {
        "name": "lblFirstName",
        "type": "StaticText",
        "label": "First name:",
        "posch": [1, 1]
      },
      "FirstName": {
        "name": "FirstName",
        "type": "TextCtrl",
        "posch": [12, 1],
        "sizech": [25, 2]
      },
      "lblLastName": {
        "name": "lblLastName",
        "type": "StaticText",
        "label": "Last name:",
        "posch": [1, 4]
      },
      "LastName": {
        "name": "LastName",
        "type": "TextCtrl",
        "required": true,
        "posch": [12, 4],
        "sizech": [25, 2]
      },
      "Active": {
        "name": "Active",
        "type": "CheckBox",
        "label": "Active",
        "posch": [12, 7]
      },
      "Notes": {
        "name": "Notes",
        "type": "MultiLine",
        "stylelist": ["MULTILINE", "WORDWRAP"],
        "posch": [12, 10],
        "sizech": [25, 7]
      }
    }
  }
}
```

For data-bound controls, the control dictionary key and `name` should match the selected database field exactly. Labels and buttons are not database fields.

### 3. Create a launcher

Store credentials in environment variables, an operating-system credential store, or another protected configuration source. Do not place passwords in source code or JSON form files.

```python
import os
import wx
import JSForm

app = wx.App(0)

database = JSForm.clsDB(
    host=os.environ.get("APP_DB_HOST", "localhost"),
    databasename=os.environ.get("APP_DB_NAME", "MyApplication"),
    username=os.environ.get("APP_DB_USER"),
    password=os.environ.get("APP_DB_PASSWORD"),
)

JSForm.CONFIG.set_Config_DBConnection(database)
JSForm.OPTION.set_Option_DBConnection(database)
JSForm.FONT.set_Font_DBConnection(database)
JSForm.FONT.Get_Config_Font()

form = JSForm.clsForm(None, database.DBConnection, "frmPerson")
form.show()
app.MainLoop()
```

If a username or password is omitted, `clsDB` displays a wxPython credentials dialog.

### Application icon

Framework-created forms use the bundled JSForm Windows icon by default. To give
an application its own identity, configure an `.ico` file before constructing
forms:

```python
JSForm.configure_application_icon("assets/my-application.ico")
```

`application_icon_path()` reports the active icon. Use
`apply_window_icon(window)` for application-created wx frames that do not use
`clsForm`. Passing `None` to `configure_application_icon()` restores the bundled
JSForm icon.

## Refactored framework boundaries

JSForm keeps its historical public imports (`JSForm.clsForm`, `JSForm.clsDB`,
`JSForm.clsRecord` and `JSForm.clsSQL`) so existing
applications continue to work. Internally, focused services now separate the
framework's major responsibilities:

- `form_lifecycle.ChildFormRegistry` owns linked forms and subforms. It is
  dictionary-compatible, detaches children before close callbacks run, and
  makes repeated or already-deleted wx window cleanup harmless.
- `db_connections.DatabaseSettings` describes a database without opening it.
  `DatabaseConnections` owns the paired application and JSForm framework
  connections and closes the first connection if the second cannot open.
- `record_state.RecordState` provides database-independent navigation and dirty
  tracking. `clsRecord` adds loading and persistence while retaining the old
  record API.
- `sql_statements.WriteStatements` constructs parameterized insert, update, and
  delete operations and rejects unsafe table or field identifiers. The older
  SQL-string methods remain temporarily available for compatibility, but new
  persistence code should use the parameterized statement methods.
- `form_services.FormDefinitionLoader`, `ControlFactory`, and
  `required_fields` handle definition loading, schema validation, control
  creation, and required-value checks outside the form coordinator.
- `report_definition`, `report_dataset`, and `report_renderer` keep report
  layout, approved data, and PDF rendering separate and testable.

Database write failures now roll back and raise a contextual `RuntimeError`.
`clsForm` catches those errors at the user-interface boundary and displays a
specific failure dialog. Form-definition and report-process failures are no
longer silently treated as success.

### Compatibility and extension rules

1. Applications may continue importing the established names from `JSForm`.
2. New non-GUI logic should live in a focused module and be independently
   testable without wxPython or MariaDB.
3. New database writes must use parameterized values. Validate identifiers
   separately; connector placeholders cannot represent table or column names.
4. Child forms must be registered through `ChildFormRegistry`; do not maintain
   a second window-ownership dictionary.
5. External programs must be invoked through an injectable process boundary.
6. Add a characterization test before changing behavior relied on by
   ChurchManager.

The acceptance gate for framework changes is the complete JSForm suite followed
by the complete ChurchManager suite, including their read-only `JSFormTest` and
`ChurchDBTest` checks through Windows Credential Manager.

## Application startup

### Database wrapper

`JSForm.clsDB(host, databasename, username, password)` creates one connector
connection to the application database named by `databasename`. The compatibility
attributes `DBConnection` and `JSConnection` refer to that same connection.
JSForm owns no separate database, tables, or records.

### Framework singletons

Before constructing forms, initialize the exported singletons:

```python
JSForm.CONFIG.set_Config_DBConnection(database)
JSForm.OPTION.set_Option_DBConnection(database)
JSForm.FONT.set_Font_DBConnection(database)
JSForm.FONT.Get_Config_Font()
```

Forms depend on these values while loading JSON, validating schemas, calculating coordinates, formatting dates, and building controls.

### Creating a form

The complete constructor is:

```python
JSForm.clsForm(
    parent,
    dbconnection,
    formname,
    controls=None,
    frmdescription=None,
    position=None,
    parentrecord=None,
    fillonblank=None,
)
```

| Argument | Meaning |
| --- | --- |
| `parent` | Parent `clsForm`, or `None` for a top-level form. |
| `dbconnection` | Open MySQL Connector connection, normally `database.DBConnection`. |
| `formname` | JSON filename without `.json`; also determines the root JSON key. |
| `controls` | Optional replacement for the form's standard-control list. |
| `frmdescription` | Optional dictionary merged over the JSON `FORM` definition. |
| `position` | Optional pixel position overriding the JSON position. |
| `parentrecord` | Parent record used to resolve `{Field}` placeholders. |
| `fillonblank` | Alternating child-field and parent-field names used to initialize a new related record. |

Useful instance attributes include:

- `FORM`: the wxPython panel, dialog, or static box that owns the controls.
- `FRAME`: the top-level frame/dialog, or the static box for a subform.
- `CONTROLID`: dictionary mapping JSON control keys to live control objects.
- `CONTROLDESCRIPTION`: effective control definitions.
- `FORMDESCRIPTON`: effective form definition. The spelling is part of the current implementation.
- `RECORDS`: the associated `clsRecord`, if the form has a table.
- `LINKEDFORM` and `SUBFORM`: related `clsForm` instances.

## Database contract

### Required conventions

For automatically editable forms:

1. The table description must select a field exposed as `ID`.
2. New records use `ID = None`; after insertion the framework reads `LAST_INSERT_ID()`.
3. JSON data-control names must match selected field names or aliases.
4. Selected fields must be compatible with MySQL Connector's reported types.
5. Related-table conditions must resolve to valid SQL.

If an existing primary key has another name, alias it:

```json
"fields": ["PersonKey AS ID", "FirstName", "LastName"]
```

The SQL helper tracks simple `AS` aliases when preparing writes. Its alias detection currently looks for lowercase ` as `, so lowercase spelling is safest.

### Framework tables

The framework uses these conventional tables:

#### `tblConfig`

```sql
CREATE TABLE tblConfig (
    ID INT NOT NULL AUTO_INCREMENT,
    ConfigFamily VARCHAR(255) NOT NULL,
    ConfigType VARCHAR(100) NOT NULL,
    ConfigValue VARCHAR(255) NOT NULL,
    Note LONGTEXT,
    PRIMARY KEY (ID)
);
```

#### `tblOptions`

```sql
CREATE TABLE tblOptions (
    ID INT NOT NULL AUTO_INCREMENT,
    OptionFor VARCHAR(255) NOT NULL,
    OptionType VARCHAR(255) NOT NULL,
    OptionValue LONGTEXT NOT NULL,
    Note LONGTEXT,
    PRIMARY KEY (ID)
);
```

#### `tblChoices`

```sql
CREATE TABLE tblChoices (
    ID INT NOT NULL AUTO_INCREMENT,
    Field VARCHAR(255) NOT NULL,
    Choices LONGTEXT NOT NULL,
    Note LONGTEXT,
    PRIMARY KEY (ID)
);
```

The repository also includes `tblReports`, described in [Reports](#reports).

### Value conversion

`clsSQL` reads MySQL field metadata and performs conversions:

| MySQL connector type | Form representation |
| --- | --- |
| `TINY` | Python Boolean. |
| Integer and floating-point types | Native Python numeric value. |
| `NEWDECIMAL` | String representation. |
| `DATE` | Native Python `date`; formatted only by the screen control. |
| `TIME` | Native Python `timedelta`; formatted only by the screen control. |
| `DATETIME` | Native Python `datetime`; formatted only by the screen control. |
| `VAR_STRING`, `STRING`, `BLOB` | String, or a list if the stored text begins with `[`. |

Lists are historically stored as bracketed, carriage-return-separated text. `CheckListBox`, by contrast, stores a JSON object mapping labels to string values `"True"` and `"False"`.

## JSON form files

### Naming contract

For form name `frmPerson`:

- File: `Forms/frmPerson.json`
- Root key: `frmPersonFORM`
- Required sections: `FORM` and `CONTROLS`

```json
{
  "frmPersonFORM": {
    "FORM": {},
    "CONTROLS": {}
  }
}
```

The loader first checks the directory configured by `Location/Form`. If the file is not found, it falls back to the framework's own `Forms` directory.

### Layout units

Forms and controls can use either:

- `pos`: pixel coordinates `[x, y]`.
- `size`: pixel dimensions `[width, height]`.
- `posch`: character-based coordinates.
- `sizech`: character-based dimensions.

Pixel properties take precedence. If `pos` exists, `posch` is ignored; if `size` exists, `sizech` is ignored. Character values are converted using the configured font and monitor measurements.

Use `[-1, -1]` as a top-level position to center in both directions. A negative x or y centers only that axis.

## Form properties

| Property | Required | Description |
| --- | --- | --- |
| `name` | Yes | Form name. Conventionally matches the filename. |
| `type` | Yes | `Panel`, `Dialog`, or `StaticBox`. The schema also lists `Frame`, but `process_form_type` does not implement it. |
| `title` | Top-level forms | Window title. |
| `pos` / `posch` | Yes in normal use | Position in pixels or character units. |
| `size` / `sizech` | Yes | Size in pixels or character units. |
| `stylelist` | No | Framework style names such as `CAPTION`. |
| `table` | No | Database table/query description. Omit for menu and utility forms. |
| `controls` | No | Standard controls. Defaults to `["Navigation", "Close"]`. |
| `readonly` | No | When `true`, makes all controls read-only. A value of `false` leaves them enabled. |
| `readonlyfields` | No | List of individual control names made read-only. |
| `linkedform` | No | Definitions of related forms shown separately. |
| `subform` | No | Definitions of related forms embedded as static boxes. |

### Form types

#### `Panel`

Creates a top-level `wx.Frame` and places a `wx.Panel` inside it. This is the normal nonmodal form type.

#### `Dialog`

Creates a `wx.Dialog`. Use `showmodal()` for modal behavior.

#### `StaticBox`

Creates a `wx.StaticBox` owned by the parent form. This is intended for embedded subforms.

### Standard controls

The `controls` list supports:

- `"Navigation"`: New, Update, Delete, First, Previous, Next, and Last.
- `"Update"`: Update only.
- `"Close"`: Close button aligned to the right.

Standard controls are appended to `CONTROLS` automatically and placed along the bottom edge of the form.

## Table descriptions and record loading

A table description has this form:

```json
"table": {
  "name": "tblPerson",
  "fields": ["ID", "FirstName", "LastName"],
  "condition": "Active = 1",
  "orderby": "LastName, FirstName"
}
```

| Property | Description |
| --- | --- |
| `name` | SQL table name. |
| `fields` | SQL select expressions. Use `["*"]` or an explicit list. Explicit lists are safer for long-term maintenance. |
| `condition` | SQL expression placed after `WHERE`; do not include the word `WHERE`. |
| `orderby` | SQL expression placed after `ORDER BY`; do not include the words `ORDER BY`. |

### Parent-record placeholders

Related forms can substitute values from the parent record:

```json
"condition": "PersonID = {ID}"
```

For a parent record with `ID` 42, JSForm compiles this as `PersonID = %s` and
passes `(42,)` separately to the database connector. Quotes, comments, and SQL
keywords inside a parent value remain data and cannot change the query.

### Option placeholders

A condition can incorporate an option:

```json
"condition": "Lectionary = {OPTION:Lectionary:Current}"
```

The parser preserves the historical option-component mapping. The returned
option value is bound through a connector parameter and is never inserted into
the SQL text.

Low-level callers may use `clsSQL.select_statement()` to receive
`(sql_text, parameter_tuple)` for `cursor.execute()`. `clsSQL.select()` remains
available for inspecting SQL text, but dynamic output contains `%s` markers and
must not be executed without the corresponding parameters.

### Forms without tables

A form may omit `table`. It will still build and display, but it has no `RECORDS` collection. This is appropriate for menus, report selectors, and custom event-driven screens. Override the `controls` argument or JSON `controls` property so a tableless form does not receive inappropriate navigation controls.

## Common control properties

Every control definition is stored under `CONTROLS`:

```json
"LastName": {
  "name": "LastName",
  "type": "TextCtrl",
  "required": true,
  "posch": [12, 4],
  "sizech": [25, 2]
}
```

Common properties include:

| Property | Description |
| --- | --- |
| `name` | wxPython name and normally the selected database-field name. |
| `type` | Framework control type. |
| `label` | Visible text for labels, boxes, checkboxes, buttons, and list headings. |
| `tooltip` | Optional help bubble shown when the pointer pauses over the control. |
| `value` | Initial wxPython value where supported. Database loading usually replaces it. |
| `defaultvalue` | Value used when the database value is `NULL`. |
| `pos` / `posch` | Position in pixels or character units. |
| `size` / `sizech` | Size in pixels or character units. |
| `stylelist` | Symbolic styles converted to wxPython flags. |
| `required` | When true, the form refuses an update while the control is empty. |
| `readonly` | Makes a supported control read-only. |
| `choices` | Literal choices for choice-aware controls. |
| `lookupchoices` | Database table description used to produce choices. |
| `action` | Framework action binding. |

The control factory filters definitions before passing arguments into wxPython, so framework-only properties do not reach the native constructor.

### Supported style names

The current style converter recognizes:

| Style | wxPython flag |
| --- | --- |
| `CAPTION` | `wx.CAPTION` |
| `MINIMIZEBOX` | `wx.MINIMIZE_BOX` |
| `MAXIMIZEBOX` | `wx.MAXIMIZE_BOX` |
| `CLOSEBOX` | `wx.CLOSE_BOX` |
| `MULTILINE` | `wx.TE_MULTILINE` |
| `DONTWRAP` | `wx.TE_DONTWRAP` |
| `WORDWRAP` | `wx.TE_WORDWRAP` |
| `READONLY` | `wx.TE_READONLY` |
| `PROCESSENTER` | `wx.TE_PROCESS_ENTER` |
| `PROCESSTAB` | `wx.TE_PROCESS_TAB` |
| `FLPCHANGEDIR` | `wx.FLP_CHANGE_DIR` |
| `FLPSMALL` | `wx.FLP_SMALL` |
| `FLPUSETEXTCTRL` | `wx.FLP_USE_TEXTCTRL` |
| `ALLOWNONE` | `wx.adv.DP_ALLOWNONE` |
| `DROPDOWN` | `wx.adv.DP_DROPDOWN` |
| `MULTIPLE` | `wx.LB_MULTIPLE` |
| `JUSTIFYRIGHT` | `wx.TE_RIGHT` |

Unknown style names are silently ignored.

## Control reference

### `StaticBox`

A labeled visual grouping box. Common properties are `label`, position, and size. It is not data-bound.

```json
"DetailsBox": {
  "name": "DetailsBox",
  "type": "StaticBox",
  "label": "Details",
  "posch": [1, 1],
  "sizech": [40, 15]
}
```

### `StaticText`

A label or clickable text element. It is not written to the database.

```json
"lblName": {
  "name": "lblName",
  "type": "StaticText",
  "label": "Name:",
  "posch": [1, 2]
}
```

### `TextCtrl`

A normal single-line text field. Use `required`, `readonly`, `defaultvalue`, and text styles as needed.

Set `"format": "phone"` for a phone field. Ten-digit North American values are
displayed as `(999) 999-9999` and returned to the record as ten digits. Values
that do not contain exactly ten digits, including international numbers and
numbers with extensions, are preserved as entered.

```json
"Phone": {
  "name": "Phone",
  "type": "TextCtrl",
  "format": "phone",
  "maxlength": 50
}
```

### `MultiLine`

A multi-line text field. The implemented type name uses a capital `L`: `MultiLine`.

```json
"Notes": {
  "name": "Notes",
  "type": "MultiLine",
  "stylelist": ["MULTILINE", "WORDWRAP"],
  "posch": [10, 10],
  "sizech": [30, 8]
}
```

### `CheckListEdit`

A specialized multi-line representation used by the checklist merge, replace, and clear actions. It stores list-like checklist content in a text/blob field.

### `TextNumber`

A right-aligned numeric text field. The wrapper parses and returns numeric content according to its implementation. Validate database compatibility when using decimals or empty values.

### `Currency`

A text control specialized for currency display and input. Back it with a compatible numeric/decimal database field and test locale behavior on the target computer.

### `Float`

A numeric field specialized for floating-point values.

### `JSON`

A text control intended for JSON content. It serializes/deserializes control values through Python's JSON facilities. Use a text/blob database field.

### `ComboBox`

A combo box whose choices come from, in order:

1. The control's literal `choices` property.
2. A `tblChoices` record matching the control's `name`.
3. The control's `lookupchoices` table query.

For lookup choices, the first selected column is the stored ID and remaining columns are joined for display.

```json
"PersonID": {
  "name": "PersonID",
  "type": "ComboBox",
  "lookupchoices": {
    "name": "tblPerson",
    "fields": ["ID", "LastName", "FirstName"],
    "condition": "Active = 1",
    "orderby": "LastName, FirstName"
  },
  "posch": [12, 5],
  "sizech": [25, 2]
}
```

The control presents a joined display string but returns the lookup ID when the display value matches a loaded choice.

### `ListCtrl`

A list control that loads its rows from the normal choices system. `GetValue()` returns a list of selected display strings, or `None`.

Typical additional properties are `label`, `choices` or `lookupchoices`, position, and size.

### `ListCtrlID`

Like `ListCtrl`, but converts selected display strings back to choice IDs. `GetValue()` returns a list of string IDs.

### `CheckBox`

A Boolean checkbox. It treats `True` and `1` as checked and returns a Python Boolean.

### `CheckListBox`

A checkable list. Its stored value is a JSON object such as:

```json
{"Prepare altar": "True", "Print bulletin": "False"}
```

The values are strings, not JSON Boolean literals, in the current implementation.

### `Button`

A standard wxPython button. Buttons normally use an `action` or are bound from application Python code.

```json
"btnRun": {
  "name": "btnRun",
  "type": "Button",
  "label": "Run",
  "posch": [30, 20],
  "action": ["process", "RunSomething"]
}
```

### `DataViewListCtrl`

A read-oriented table/list display backed by its own table description.

```json
"Appointments": {
  "name": "Appointments",
  "type": "DataViewListCtrl",
  "posch": [1, 8],
  "sizech": [50, 12],
  "table": {
    "name": "tblAppointment",
    "fields": ["ID", "PersonID", "AppointmentDate"],
    "condition": "PersonID = {ID}",
    "orderby": "AppointmentDate"
  },
  "column": [
    {"name": "AppointmentDate", "label": "Date", "widthch": 15}
  ]
}
```

Each `column` needs `name`, `label`, and `widthch`. A column can contain a `lookup` object for display conversion. The live control provides `GetSelectedRow()` and `GetSelectedRowID()`.

### `DatePickerCtrl`

A date picker displayed according to `Format/Date`. `GetValue()` returns a native Python `date`. Add `ALLOWNONE` to permit a null date.

```json
"BirthDate": {
  "name": "BirthDate",
  "type": "DatePickerCtrl",
  "stylelist": ["ALLOWNONE"],
  "posch": [12, 8],
  "sizech": [15, 2]
}
```

Without `ALLOWNONE`, an empty value defaults to today's date.

### `TimePickerCtrl`

A time picker displayed according to `Format/Time`. `GetValue()` returns a native Python `timedelta`, matching MariaDB's `TIME` representation.

### `DateTime`

A composite control containing a date picker and time picker. It divides the configured width between those controls and returns a native Python `datetime`.

### `FilePickerCtrl`

A file picker. Its `directory` property identifies the configuration family and type used for the initial directory:

```json
"Document": {
  "name": "Document",
  "type": "FilePickerCtrl",
  "directory": ["Location", "Document"],
  "message": "Select a document",
  "wildcard": "PDF files (*.pdf)|*.pdf|All files (*.*)|*.*",
  "posch": [10, 5],
  "sizech": [30, 2]
}
```

The control stores the selected filename while maintaining its directory
separately. An `openfile` action resolves the remembered directory first and
then the configured initial directory. Before constructing forms that use
`openfile`, the application must configure its approved local document roots
and passive extensions:

```python
JSForm.configure_file_opening(
    approved_roots=[documents_directory],
    passive_extensions={".pdf", ".docx", ".xlsx", ".txt"},
)
```

No configured policy means file opening is denied. The configured picker
directory helps resolve a stored basename but does not itself grant approval.
The final existing regular file must resolve beneath an approved local root and
use an application-approved passive extension. JSForm rejects remote, device,
URL, shortcut, executable, script, installer, alternate-stream, reparse, and
outside-root targets before asking Windows to open the document with its
registered application.

### `HTMLCtrl`

A `wx.html.HtmlWindow`. `SetValue()` calls `SetPage()` and `GetValue()` returns the most recently assigned HTML string.

### `CalendarCtrl`

A calendar-style date selector. It accepts configured date strings, Python
`date`/`datetime` values, and returns a native Python `date`.

## Choices and lookups

### Literal choices

```json
"Priority": {
  "name": "Priority",
  "type": "ComboBox",
  "choices": ["1", "2", "3", "4", "5"],
  "posch": [10, 4]
}
```

### Shared `tblChoices` choices

If a choice-aware control has neither `choices` nor a successful literal load, `clsChoice` queries `tblChoices` using the control's `name` as `Field`.

For example, a `Priority` control can use a row whose `Field` is `Priority` and whose `Choices` contains one choice per line inside the framework's historical bracketed format.

### Table lookups

`lookupchoices` uses the same `name`, `fields`, `condition`, and `orderby` structure as a normal table description. The first returned field is treated as the stored ID. Remaining fields are joined with spaces for display.

Avoid using `sort`; `clsSQL.select()` recognizes `orderby`. One repository example uses `sort`, but that property is ignored by the current SQL builder.

## Actions and event binding

An action is a JSON array whose first item selects framework behavior:

```json
"action": ["action-name", "argument", "additional-argument"]
```

The current form binder recognizes:

| Action | Event and purpose |
| --- | --- |
| `mouse` | Binds a mouse gesture to the framework capture hook. The hook is marked TODO. |
| `refreshform` | Binds text change to related-form refresh behavior. |
| `openform` | Opens the named form. |
| `openlinkedform` | Opens a form declared in `linkedform`. |
| `openformfromfield` | Derives the form to open from a field value. |
| `openfile` | Opens an application-approved passive local file referenced by another control. |
| `editchecklist` | Performs merge, replace, or clear checklist operations. |
| `process` | Invokes application-specific processing through `_processaction`. |
| `onchange` | Handles a combo-box change through `_processaction`. |

The meaning of later array elements depends on the action. Existing form files are the best executable examples.

### Binding custom Python handlers

Application code can bind directly to a live control:

```python
def on_run(event):
    value = form.CONTROLID["PersonID"].GetValue()
    print(value)

form.CONTROLID["btnRun"].Bind(wx.EVT_BUTTON, on_run)
```

Use the native event appropriate to the control. The repository's launcher sometimes uses `wx.EVT_LEFT_DOWN`; `wx.EVT_BUTTON` is generally preferable for buttons because it preserves keyboard activation and normal button semantics.

### Shared Python commands

`Action` remains compatible with direct event handlers. It can also reference a
registered application command so an action-bar button and a menu item use the
same handler, state provider, and authorization path:

```python
command = JSForm.ApplicationCommand(
    "tools.export", "&Export", export_records,
    help_text="Export the current records",
)
registry.register(command)
action = JSForm.action_from_command(command)
bar = JSForm.StandardActionBar(
    parent, [action], registry=registry,
    context_provider=current_command_context,
)
```

Legacy `Action(name, label, handler)` construction and `install_action_menu()`
continue to work. A command-backed action requires a `CommandRegistry`.
`StandardActionBar.refresh()` applies the command's enabled and visible state.
The approved design contract is recorded in
`JSForm.ApplicationMenus.Specification.md`.

## JSON application menus

Application menu bars are application-shell definitions, not form controls.
They use `schema/menu_definition_schema.json` and are installed only on a
top-level `wx.Frame`. Individual panels and dialogs continue to use their own
controls or the owning frame's application menu.

### Definition shape

```json
{
  "$schema": "https://jsform.local/schema/menu-definition-v1.json",
  "schema_version": 1,
  "name": "main",
  "menus": [
    {
      "label": "&File",
      "items": [
        {"command": "file.open", "accelerator": "Ctrl+O"},
        {"separator": true},
        {"command": "app.exit"}
      ]
    },
    {
      "label": "&View",
      "items": [
        {"command": "view.status_bar", "kind": "check"},
        {
          "label": "&Theme",
          "items": [
            {"command": "view.theme.system", "kind": "radio", "radio_group": "theme"},
            {"command": "view.theme.light", "kind": "radio", "radio_group": "theme"}
          ]
        }
      ]
    }
  ]
}
```

Top-level menus and submenus require `label` and nonempty `items`. An item is
exactly one registered command, separator, or submenu. Command items may override
`label` and `help_text`, declare a portable `accelerator`, and use `normal`,
`check`, or `radio` kind. Radio items require an adjacent `radio_group`. Menu
nesting is limited to four levels. Unknown properties and schema versions fail
closed.

The loader accepts UTF-8 and UTF-8 with BOM:

```python
loader = JSForm.MenuDefinitionLoader()
definition = loader.load("Menus/main.menu.json")
```

For recoverable customization, keep the protected starter and user file apart:

```python
definition = loader.load_application(
    "Menus/main.menu.json",
    "UserMenus/main.menu.json",
    fallback_to_starter=True,
)
```

Without `fallback_to_starter=True`, an invalid existing customization raises
`MenuDefinitionError`. Neither source is silently rewritten or deleted.
`save_menu_definition()` validates before atomic replacement and preserves the
previous target as `<name>.bak`.

### Visual menu designer

Applications can expose an approved command catalog to the framework designer
without exposing handlers, services, permissions, or application modules:

```python
descriptors = (
    JSForm.MenuCommandDescriptor(
        "records.routes", "&Routes", "Open route records", category="Records"
    ),
)
frame = JSForm.open_menu_designer(
    "UserMenus/main.menu.json",
    descriptors,
    save_path="UserMenus/main.menu.json",
    starter_path="Menus/main.menu.json",
)
```

`MenuDesignerModel` provides undoable add, update, move, indent, outdent,
duplicate, delete, validation, and serialization operations. The wx designer
adds a searchable command palette, hierarchy tree, property editor, validation
results, Save As, starter/previous recovery, and an inert native preview.
Preview commands only identify themselves in a status bar; they never call the
application's real handlers.

Protected starters and editable files must be kept in separate directories.
`MenuCatalogModel` and `open_menu_catalog()` implement that lifecycle, including
creating a customization, listing invalid files for recovery, restoring the
starter after deletion, and retaining the prior valid `.bak`. A saved menu is
normally loaded on the application's next launch unless that application
explicitly implements a controlled reload.

### Registering commands

JSON never imports Python or contains a handler, SQL, expression, credential, or
service implementation. Applications register stable dotted names in Python:

```python
registry = JSForm.CommandRegistry()
registry.register(JSForm.ApplicationCommand(
    name="records.routes",
    label="&Routes",
    help_text="Open route records",
    handler=open_routes,
    permission="routes.records.view",
    state_provider=current_route_state,
))
```

Handlers and state providers receive `CommandContext`. It supplies the frame,
current JSForm form, source presentation, wx event, authorization policy, and a
read-only mapping of explicitly supplied application services. State providers
return `CommandState(enabled=..., visible=..., checked=...)`.

Names and explicit wx IDs must be unique. Batch registration is transactional.
A protected command with no usable authorization policy fails closed. State
evaluation disables unauthorized commands, and dispatch checks authorization
again immediately before calling the handler. Handler and state failures use
JSForm's configured error-reporting boundary.

### Installation and lifecycle

```python
installer = JSForm.MenuInstaller(
    main_form.FRAME,
    registry,
    context_provider=current_command_context,
)
installer.install(definition, current_form=lambda: main_form)
```

Installation resolves every command and constructs the complete native menu bar
before replacing the frame's existing bar. A failure preserves the previous bar
and removes partial bindings. `refresh()` applies current state, removes hidden
items, redundant separators, empty submenus, and empty top-level menus. State is
also refreshed on `wx.EVT_MENU_OPEN`. `dispose()` removes owned bindings and
restores the bar that preceded the first successful installation.

The same command may appear more than once and may also back a visible button:

```python
action = JSForm.action_from_command(registry.get("records.routes"))
bar = JSForm.StandardActionBar(
    parent, [action], registry=registry,
    context_provider=current_command_context,
)
```

Existing `Action(name, label, handler)` and `install_action_menu()` callers remain
supported.

### Standard command factories

- `standard_application_commands(name, application_version=...)` supplies Exit
  and About with standard wx IDs.
- `standard_edit_commands()` supplies focus-sensitive Cut, Copy, Paste, and
  Select All.
- `standard_record_commands()` supplies New, Save, Delete, and Refresh against
  `CommandContext.current_form`.

`clsForm.new_record()`, `save_record()`, `delete_record()`, and
`refresh_records()` are the shared public record workflows used by existing
buttons and standard commands. Long-running application handlers must use
JSForm's background-operation API rather than blocking the wx main thread.

## Enabling and disabling buttons

`clsForm` exposes:

```python
form.disable_button("btnRun")
form.enable_button("btnRun")
form.enable_buttons(["btnRun", "btnClose"])
form.disable_all_buttons()
form.enable_navigation_buttons()
form.disable_navigation_buttons()
```

## Linked forms and subforms

### Linked forms

Linked forms are separate related forms. The parent loads the linked form's normal JSON definition and merges the inline override over its `FORM` section.

```json
"linkedform": {
  "frmAddress": {
    "type": "Panel",
    "controls": ["Navigation", "Close"],
    "table": {
      "name": "tblAddress",
      "fields": ["ID", "PersonID", "Street", "City"],
      "condition": "PersonID = {ID}"
    },
    "fillonblank": ["PersonID", "ID"]
  }
}
```

`fillonblank` is an alternating list:

```text
[child field, parent field, child field, parent field, ...]
```

In the example, a blank address receives its `PersonID` from the parent record's `ID`.

If no control has an `openlinkedform` action for a declared linked form, the parent opens it automatically during initialization. If a matching action exists, the linked form opens when that control is activated.

### Subforms

Subforms are created within the parent and normally use `type: "StaticBox"`. Their table conditions can reference the current parent record in the same way.

```json
"subform": {
  "frmContactSummary": {
    "type": "StaticBox",
    "controls": [],
    "posch": [2, 15],
    "sizech": [40, 8],
    "table": {
      "name": "tblContact",
      "fields": ["ID", "PersonID", "Summary"],
      "condition": "PersonID = {ID}"
    }
  }
}
```

The current `initialize_sub_forms()` returns after creating the first subform. Therefore, only one subform is reliably initialized per parent form without modifying the framework.

## Record lifecycle

### Loading

When a data-bound form is constructed:

1. `clsRecord` creates a `clsSQL` helper.
2. The SQL helper reads field metadata with a one-row query.
3. The form's `SELECT` statement is executed.
4. Rows are converted to dictionaries.
5. If no rows are returned, a blank record is built from the field metadata.
6. The current record is copied into the controls.

### Navigation

`clsRecord` maintains a list and a zero-based position. It exposes:

- `current()`, `currentfield(field)`, and `currentnum()`.
- `first()`, `prev(loop=False)`, `next(loop=False)`, and `last()`.
- `getcurrentID()` and `getfield(name)`.
- `fieldisdirty(field)` and `recordisdirty()`.

The form's standard navigation buttons call these methods and refill the controls.

### New records

New-record handling creates/selects a blank record. Fields with defaults are filled when displayed. For linked forms, `fillonblank` can copy foreign keys from the parent.

Applications and registered commands may call `form.new_record()`. It returns
`True` when the blank record was created and `False` when authorization or dirty
state prevented the operation.

### Updates

Before saving, the form:

1. Checks required controls.
2. Reads control values into the current record.
3. Classifies the save from the original snapshot: an original blank ID is a
   create/INSERT, while an original populated ID is an update/UPDATE.
4. Commits the database transaction.
5. Saves a new original-record snapshot for dirty tracking.

Although comments say that only changed fields are updated, the current SQL builder constructs assignments from the supplied record. Do not rely on minimal-column updates without testing or revising `clsSQL.update()`.

`form.save_record()` asks the application's authorization policy for `create`
or `update`, matching the operation classified from the saved original record.
The form-owned `clsRecord` repeats that check immediately before persistence,
so a permission change after the initial UI check cannot permit SQL. A new
record with an application-assigned current ID remains a create because its
original ID was blank. Automatic blank records follow the same rule. Successful
audits identify the committed operation as `create` or `update`.

The Save/Update button and registered `record.save` command use that pending
operation when calculating their enabled state after record creation,
navigation, and refresh. This state is advisory; the persistence-boundary
authorization remains authoritative. `save_record()` otherwise runs the same
required-field, persistence, audit, navigation-state, and notification workflow
and returns whether the save completed.

Low-level applications may construct `clsRecord(connection, table,
operation_authorizer=callback)`. The optional callback receives `"create"` or
`"update"` immediately before the corresponding write. Form-owned records use
`FormSecurity.require`, which delegates permission meaning and the final
allow/deny decision to the application-supplied authorization policy. JSForm
does not define application permissions or roles.

### Deletes

Delete uses the current record's `ID`, commits the transaction, removes the record from the in-memory list, and moves to the previous record.

`form.delete_record()` runs the same authorization, dirty-state, persistence,
audit, notification, refill, and child-form cleanup workflow as the standard
Delete button. It returns whether the deletion completed.

### Refresh

`form.refresh_records()` reloads the form's declared table, preserves the current
record by `ID` when it still exists, refills the controls, and closes linked
forms whose data may now be stale. It returns `False` when the form is not
data-bound, dirty-state handling cancels the operation, or reloading fails.

### Required fields

Set `"required": true` on data-entry controls. Missing fields are highlighted and an explanatory dialog is shown when the user attempts to update.

### Dirty forms

The form compares live control values and the saved original record. Closing or navigating away from changes can produce a Continue/Cancel dialog.

## Configuration, options, and fonts

### Configuration lookup

```python
value = JSForm.CONFIG.get_Config_Value("Location", "Form")
family = JSForm.CONFIG.get_Config_Family("Font")
JSForm.CONFIG.set_Config_Value("Location", "Form", ".\\Forms\\")
```

Configuration is read only from the application's `tblConfig` table. Missing
values return `None` so the application or framework component can use an
explicit built-in default.

When `Location/Form` is absent, the form loader uses the application's bundled
fallback form directory. A missing configuration record must never be passed
to `pathlib.Path` as a path value.

Configuration families, types, and values are passed to MySQL Connector as
parameters on the application path. They remain
data even when they contain quotes, comments, or SQL keywords. Applications
remain responsible for deciding which configuration names and values are
meaningful and permitted. `set_Config_Value()` does not commit or roll back;
the application retains ownership of its transaction boundary.

Common configuration families used by this repository include:

| Family/type | Purpose |
| --- | --- |
| `Location/Form` | Application form directory. |
| `Location/JSONSchema` | JSON Schema directory. |
| `Location/Report` | Generated report directory. |
| `Format/Date` | Python/wx date display format. |
| `Format/Time` | Python/wx time display format. |
| `Format/DateTime` | Python/wx date-time display format. |
| `SQLFormat/Date` | MySQL `STR_TO_DATE` format. |
| `SQLFormat/Time` | MySQL `STR_TO_DATE` format. |
| `SQLFormat/DateTime` | MySQL `STR_TO_DATE` format. |

### Options

```python
value = JSForm.OPTION.get_Option_Value("JSONSchema", "CheckForms")
JSForm.OPTION.set_Option_Value("JSONSchema", "CheckForms", "Yes")
```

Options are read only from the application's `tblOptions` table.

Option groups, types, and values are connector parameters on lookup and update.
JSForm does not define their application meaning or authorize
who may change them. `set_Option_Value()` leaves commit and rollback decisions
to the application.

### Font configuration

`FONT.Get_Config_Font()` expects the `Font` configuration family to supply values such as:

- `PointSize`
- `Family`
- `Style`
- `Weight`
- `Face`
- `Underline`

The resulting font controls both display and conversion of `posch`/`sizech` values.

## Reports

JSForm reports use JSON definitions loaded by `ReportDefinitionLoader`. An
application supplies a `ReportDataset` that conforms to an approved
`ReportDatasetContract`; definitions cannot contain SQL or database
credentials. `PDFReportRenderer` produces the PDF, while `ReportDesignerModel`
and the report catalog support recoverable starters and separate user
customizations.

Applications own report selection, parameter collection, dataset construction,
authorization, output location, and opening the finished file. See the School
Bus Route Manifest for a small end-to-end example. The complete designer,
catalog, dataset, preview, protection, and recovery workflow is documented in
[JSForm Report Designer](REPORT_DESIGNER.md).

For dashboard-style forms made from several independent `StaticBox` groups,
set the form layout to `{"type": "columns"}`. Each top-level group's
`layout.column` selects its column and `layout.row` determines its order within
that column. Columns pack independently, so a short group no longer inherits
the height of a taller group beside it.

Repeating controls draw a light separator after each record by default. Set
`"separator": false` on a repeater when its items represent preprinted labels
or another layout where record-divider lines must not be rendered. Set the
report-level `"showdefaultpagenumber": false` when preprinted stationery or
labels must not receive JSForm's fallback page number. The default is `true`.

A repeater can fill fixed stock across the page before moving downward by
setting `"repeatcolumns"` and, when needed, `"columngap"`. This is useful for
mailing labels and other repeated cards. Multi-column repeaters do not support
report groups; use a single sorted collection for the repeated records.

Report-level `"filters"` use the same validated conditions as control
visibility. They remove collection rows before sorting and rendering, allowing
generic JSON reports to select records without embedding SQL or application
code in the definition.

## Public Python API

The package exports these main objects from `__init__.py`:

### Singletons

- `CONST`: constants and standard-control definitions.
- `CONFIG`: global `clsConfig` instance.
- `OPTION`: global `clsOption` instance.
- `FONT`: global `clsFont` instance.
- `LG`: global logger.
- `PMON`: monitor/font measurement helper.

### Classes

- `clsForm`
- `clsDB`
- `clsRecord`
- `clsChoice`
- `clsErrorHandler`
- `clsSMTP`
- `clsSQL`
- `clsField`

### Functions

- `getcontrolparameters(description)`: converts styles and filters framework descriptions into wxPython constructor arguments.
- `convertNavButtons(controls)`: converts standard controls to pixel measurements.
- `charactertopoint(form, controls)`: converts form/control character measurements.
- `date_to_datetime(date)`
- `next_weekday(date, weekday)`
- `sql_table_exists(connection, table)`
- `check_internetconnection(timeout)`

### Showing and closing forms

```python
form.show()
form.center()
form.centre()      # Alias
result = form.showmodal()
form.FORM.Close()
```

For a normal `Panel` form, application code will commonly close `form.FRAME`; follow the behavior of the specific form type and test close events.

## Schema validation

If the option `JSONSchema/CheckForms` equals `Yes`, `clsForm.load_form_from_json()` loads:

```text
<JSForm package>/schema/unified_schema.json
```

and calls `jsonschema.validate()` before building the form.

The repository contains legacy `jsformschema.json` copies, but runtime validation
now uses the bundled `schema/unified_schema.json` as its canonical schema. This
avoids selecting a stale schema based on the application's current working
directory. The configured `<Location/JSONSchema>/jsformschema.json` path remains
as a compatibility fallback only when the bundled schema is unavailable. The
automated suite validates every JSForm definition against this canonical schema.

## Testing and debugging

### Recommended test levels

1. **JSON parsing:** ensure every form is valid JSON and follows the filename/root-key contract.
2. **Schema validation:** validate every form independently against the bundled canonical schema.
3. **Database integration:** use a disposable database to test loading, inserting, updating, and deleting each supported SQL type.
4. **Control round trips:** confirm that `SetValue()` followed by `GetValue()` preserves the intended value.
5. **Relationship tests:** verify parent placeholders, linked forms, `fillonblank`, and subforms.
6. **Visual tests:** inspect layout at the supported font sizes, display scaling, and monitor configurations.
7. **Report tests:** use harmless sample reports and paths containing spaces.

### Logging

Framework methods call the global logger `JSForm.LG`. This legacy diagnostic
logger is disabled by default, opens its file only when diagnostics are enabled,
and stores an installed application's log under
`%LOCALAPPDATA%\<ApplicationName>\Logs\Log.txt`. An unavailable log location
must never prevent the application from starting. Avoid logging passwords,
tokens, or sensitive record content.

### Common failures

| Symptom | Likely cause |
| --- | --- |
| `ModuleNotFoundError: JSForm` | The package's parent directory is not on Python's import path, or the directory is not named `JSForm`. |
| Form JSON is not found | `Location/Form` is wrong and the file is not in the framework `Forms` directory. |
| Root-key error | Filename/form name and `<formname>FORM` root key do not match. |
| Control remains blank | Control key/name does not match a selected database field. |
| Combo box has no choices | No literal choices, no matching `tblChoices` row, and an invalid/missing `lookupchoices` query. |
| Lookup order is ignored | `sort` was used instead of `orderby`. |
| Date parsing fails | A JSON-supplied initial value does not match `Format/Date`, `Format/Time`, or `Format/DateTime`; database values should use native SQL temporal types. |
| Insert/update SQL error | Database metadata, field aliases, escaping, or value conversion does not match the table. |
| Only one subform appears | The current initializer returns after the first subform. |
| Schema check fails on an otherwise working form | Runtime/schema drift described above. |
| Included virtual environment will not start | It contains an absolute path from the computer on which it was created; rebuild it. |

## Security

### Credentials

Never store database passwords, SMTP passwords, API keys, or license secrets in:

- Python source.
- JSON form files.
- documentation.
- SQL backups committed to source control.
- logs.

Use environment variables, a credential manager, or a protected local configuration file excluded from version control. Historical backups in this repository contain credential-like values and must be treated as compromised. Rotate the corresponding credentials and remove them from the entire repository history if this repository is shared.

### SQL construction

Parent-record and option values in table conditions are parameterized. Modern
record writes and the public configuration and option storage APIs also use
connector parameters. Some older direct choice APIs still construct SQL with
string formatting and are tracked separately in the security-remediation
roadmap.

Table names, field expressions, static condition structure, and `orderby`
cannot be connector parameters. Use only trusted framework or application table
definitions, validate identifiers against allowlists, and never expose raw
condition or order-by strings to end users.

### Process launching

Report and file-opening features launch external processes. Paths and parameters must be trusted and validated. Prefer argument arrays with `shell=False` when modernizing the implementation.

### Database permissions

Use a dedicated database account with only the permissions the application needs. Do not use a server administrator account. Restrict network access to the database and require encrypted connections where appropriate.

## Current limitations and compatibility notes

This repository is a historical working framework rather than a polished distributable library. Important implementation facts are:

1. The package assumes the import name `JSForm` and is sensitive to directory placement.
2. The checked-in virtual environment is not portable.
3. The implementation, schema, old documentation, and experimental tests have drifted apart.
4. SQL values are not consistently parameterized.
5. Exception handling frequently uses broad `except` blocks, which can hide failures.
6. `Frame` is accepted by the schema but is not built by `process_form_type()`.
7. All control types advertised by the schemas are implemented by the factory; automated catalog checks keep these lists synchronized.
8. Only the first declared subform is initialized because of an early return.
9. One example uses `sort`, but the SQL implementation recognizes `orderby`.
10. Both form-level and control-level `readonly` honor their Boolean value.
11. `clsSQL` has edge cases in quoting, alias detection, and its default formatting branch; test every database type before production use.
12. Configuration setters do not visibly commit in their own methods; persistence depends on connector transaction behavior or outside commits.
13. `check_internetconnection()` loops indefinitely until a request succeeds.
14. The report runner and file opener assume Windows-oriented path and process behavior.
15. Some development scripts refer to an experimental package layout that is not present here.

These limitations do not prevent building an application with JSForm, but they should inform testing and modernization priorities.

## Application-development checklist

### Before coding

- [ ] Create a fresh Python environment.
- [ ] Install dependencies appropriate to the target Python version.
- [ ] Decide whether JSForm will remain a package named `JSForm` or be repackaged.
- [ ] Create a disposable development database.
- [ ] Create least-privilege database credentials outside the repository.

### Database

- [ ] Give every editable query a selected field named `ID`.
- [ ] Make JSON control names match selected field names.
- [ ] Add `tblConfig`, `tblOptions`, and `tblChoices` where required.
- [ ] Add date/time format configuration.
- [ ] Add font configuration before using character-based layout.
- [ ] Test nulls and defaults for every database type.

### Forms

- [ ] Match filename, constructor form name, and `<formname>FORM` root key.
- [ ] Use `orderby`, not `sort`.
- [ ] Give each data control an explicit `name`.
- [ ] Mark required fields.
- [ ] Use `ALLOWNONE` only when the database permits null dates.
- [ ] Define standard `controls` explicitly for tableless forms.
- [ ] Test related-form placeholders with actual parent records.

### Python launcher

- [ ] Create `wx.App` before dialogs/forms.
- [ ] Create `clsDB`.
- [ ] Initialize `CONFIG`, `OPTION`, and `FONT`.
- [ ] Load the configured font before creating forms.
- [ ] Bind application-specific handlers.
- [ ] Show the initial form and start `MainLoop()`.

### Verification

- [ ] Open every form.
- [ ] Exercise New, Update, Delete, and all navigation buttons.
- [ ] Confirm every control round-trips through the database.
- [ ] Check dirty-record and required-field dialogs.
- [ ] Test empty tables and null values.
- [ ] Test linked forms and subforms.
- [ ] Generate every report.
- [ ] Review logs and backups for secrets before sharing or committing.

---

This documentation reflects the framework files present in this repository as of August 2026. When behavior differs from this guide, inspect the installed version of `clsForm.py`, `clsField.py`, and `clsSQL.py`, because those modules determine runtime behavior.

## Application-assigned primary keys

JSForm normally accepts the database-generated `ID` after inserting a new
record. An application may instead assign a stable `ID` to the current blank
record before its first save. JSForm remembers that the record began as new,
performs an `INSERT` including that ID, and preserves the assigned value. This
supports permanent catalog identifiers without embedding any application-
specific allocation policy in JSForm.

Application-assigned IDs and other record-only system fields do not need visible
controls. Dirty-state and required-field highlighting safely ignores fields that
are absent from the form while still including them in record persistence.

## Database ownership

JSForm owns no database tables or records and opens no separate framework
database. Applications own their schema, configuration, options, and data.
The compatibility `JSConnection` attribute refers to the same connection as
`DBConnection`; it does not represent another database.
