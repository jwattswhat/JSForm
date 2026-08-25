# JSForm public API

Applications install the `jsform-desktop` distribution and use `import JSForm`.
Names re-exported by `JSForm/__init__.py` are the supported Python API during
the current pre-release series. Direct imports from internal modules may change
unless the framework reference specifically documents them.
`JSForm.__all__` is the machine-readable inventory of these exports. Its release
test requires an intentional review whenever a name is added or removed.

The supported surface includes:

- database connections, records, SQL writing, choices, and form lifecycle;
- JSON form loading, controls, responsive layouts, and authorization policies;
- reusable list, grid, search/select, ordered-child, and compact-editor behavior;
- screen and report definitions, catalogs, designers, datasets, and PDF output;
- background operations, conditional status formatting, mail services,
  credential storage, error reporting, and support packages;
- validated application-menu definitions, command registration and state,
  native menu installation, command-backed action bars, and standard application,
  Edit, and record command factories;
- bundled and application-selected Windows icon support; and
- the constants and compatibility classes already re-exported by `JSForm`.

JSON contracts are versioned alongside the Python API. Applications should use
the bundled schemas and documented properties rather than relying on parser
implementation details.

## Reports

| Name | Contract |
| --- | --- |
| `ReportDefinition` | Immutable validated report JSON. |
| `ReportDefinitionError` | Definition loading or schema-validation failure. |
| `ReportDefinitionLoader` | Load UTF-8 report JSON or validate a dictionary. |
| `save_report_definition` | Atomic validated-definition save with `.bak` retention. |
| `ReportProtectionManifest` | Application-required report settings, sections, and controls. |
| `ReportField` | One approved field and its data type and sensitivity. |
| `ReportCollection` | Named report rows and optional parent relationship. |
| `ReportDatasetContract` | Versioned collection and field allow-list. |
| `ReportDataset` | Immutable application-supplied report rows. |
| `ReportDatasetError` | Dataset or binding contract failure. |
| `PDFReportRenderer` | Deterministic validated-definition PDF renderer. |
| `ReportRenderError` | Bounded PDF rendering failure. |
| `ReportDesignerModel` | Undoable report-layout editing and validation model. |
| `ReportCanvas` | Native report layout canvas used by the designer. |
| `ReportDesignerFrame` | Visual report designer window. |
| `open_report_designer` | Open a modeless report designer. |
| `ReportCatalogModel` | Protected starter and separate customization lifecycle. |
| `open_report_catalog` | Open the modal report catalog. |

See [JSForm Report Designer](REPORT_DESIGNER.md) for the complete workflow.

## Screens

| Name | Contract |
| --- | --- |
| `ScreenDefinition` | Validated screen JSON. |
| `ScreenDefinitionLoader` | Load and validate screen definitions. |
| `save_screen_definition` | Atomic screen save with `.bak` retention. |
| `screen_definitions_equal` | Compare definitions with supported normalization. |
| `ScreenDesignerModel` | Undoable visual screen editing model. |
| `ScreenCanvas` | Native screen layout canvas. |
| `ScreenDesignerFrame` | Visual screen designer window. |
| `ScreenPreviewFrame` | Inert screen-definition preview window. |
| `open_screen_designer` | Open a modeless screen designer. |
| `open_screen_preview` | Open an inert screen preview. |
| `ScreenCatalogModel` | Protected starter and user customization lifecycle. |
| `open_screen_catalog` | Open the modal screen catalog. |

## Application menus and commands

The supported application-menu surface is:

| Name | Contract |
| --- | --- |
| `ApplicationCommand` | Immutable registered command metadata and handler. |
| `CommandContext` | Controlled frame, current-form, event, policy, and application-services context. |
| `CommandRegistry` | Unique registration, state evaluation, authorization, and dispatch. |
| `CommandState` | Enabled, visible, and checked presentation state. |
| `MenuDefinition` | Immutable validated menu JSON. |
| `MenuDefinitionError` | Definition read or validation failure. |
| `MenuDefinitionLoader` | Dictionary, UTF-8/BOM file, starter, and customization loading. |
| `save_menu_definition` | Validated atomic save with `.bak` retention. |
| `MenuInstallationError` | Command resolution or native construction failure. |
| `MenuInstaller` | Native wxPython construction, refresh, event binding, replacement, and disposal. |
| `action_from_command` | Adapter from a registered command to an `Action`. |
| `standard_application_commands` | Exit and About command factory. |
| `standard_edit_commands` | Focus-sensitive Cut, Copy, Paste, and Select All factory. |
| `standard_record_commands` | Current-form New, Save, Delete, and Refresh factory. |
| `MenuCommandDescriptor` | Safe application-supplied command metadata for design. |
| `MenuDesignerModel` | Undoable menu hierarchy and property editing model. |
| `MenuDesignerFrame` | Visual command palette, tree, properties, validation, and preview interface. |
| `MenuCatalogModel` | Protected starter and separate customization lifecycle. |
| `open_menu_designer` | Open one modeless visual designer. |
| `open_menu_catalog` | Open the modal starter/customization menu catalog. |

`Action`, `StandardActionBar`, and `install_action_menu()` remain public and
backward compatible. Command-backed actions require a `CommandRegistry` and use
the same dispatch authorization as native JSON menu items.

## Application icons

JSForm applies its bundled `assets/jsform.ico` to framework-created forms and
designer windows. Applications may call `configure_application_icon(path)`
before constructing forms to select their own `.ico` file. The selected icon is
process-wide and remains application-owned; calling the function with `None`
restores the JSForm default. `application_icon_path()` returns the active path,
and `apply_window_icon(window)` applies it to another wx top-level window.

## Compatibility policy

JSForm is pre-release software. Compatible additions may be made within the
`0.1` series. Renaming or removing an exported name, changing stored value
semantics, or changing a JSON property requires documentation, migration advice,
and a version decision before release. Application-specific workflows and
database rules are never part of the JSForm API.
