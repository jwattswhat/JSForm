# JSForm architecture

JSForm separates declarative application definitions from reusable runtime
services.

```text
Application
  -> JSON screen/report/menu definitions
  -> JSForm public APIs
       -> definition and schema validation
       -> command registry and native application menus
       -> layout and wxPython controls
       -> record state and database access
       -> choices, searches, and ordered children
       -> report datasets, designer, and renderer
       -> error reporting and support packages
  -> MariaDB/MySQL and local application files
```

## Dependency direction

Core JSForm modules must not import ChurchManager or encode church-specific
tables, permissions, or terminology. Applications may import JSForm and provide
callbacks, authorization adapters, audit hooks, datasets, and definitions.

The main public entry points are exported by `JSForm.__init__`. Internal module
names are not a stability promise unless the framework reference documents them
as public.

## Major components

| Area | Principal modules |
| --- | --- |
| Forms and controls | `clsForm.py`, `clsField.py`, `form_services.py` |
| Layout | `layout_engine.py`, `ui_dimensions` supplied by applications |
| Records and SQL | `clsDB.py`, `clsSQL.py`, `record_state.py`, `sql_statements.py` |
| Choices and selection | `clsChoice.py`, `choice_manager.py`, `search_select.py` |
| Screen design | `screen_definition.py`, `screen_catalog.py`, `screen_designer.py` |
| Reports | `report_definition.py`, `report_dataset.py`, `report_renderer.py`, `report_catalog.py`, `report_designer.py` |
| Application menus | `menu_definition.py`, `menu_commands.py`, `menu_builder.py`, `menu_catalog.py`, `menu_designer.py`, `standard_commands.py`, `action_ui.py` |
| Window icons | `window_icons.py` |
| Long operations | `background_operation.py` |
| Diagnostics | `error_reporting.py`, `error_redaction.py`, `support_package.py` |

## Stability rules

- JSON is validated before a definition is used.
- Menu JSON references stable registered command names and never executable code.
- Command authorization is checked for presentation state and again at dispatch.
- Database values are passed as native Python values through parameterized SQL.
- Dirty state compares normalized semantic values rather than display strings.
- Starter definitions remain recoverable; user customizations live separately.
- Long-running work must not freeze the GUI.
- Framework errors may include technical context but must redact secrets.

The detailed control and database contracts are maintained in
[`JSForm_Framework.md`](JSForm_Framework.md). Report design and customization
are covered in [`REPORT_DESIGNER.md`](REPORT_DESIGNER.md).
