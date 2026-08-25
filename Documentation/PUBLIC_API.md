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
  credential storage, error reporting, and support packages; and
- validated application-menu definitions, command registration and state,
  native menu installation, command-backed action bars, and standard application,
  Edit, and record command factories; and
- the constants and compatibility classes already re-exported by `JSForm`.

JSON contracts are versioned alongside the Python API. Applications should use
the bundled schemas and documented properties rather than relying on parser
implementation details.

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

`Action`, `StandardActionBar`, and `install_action_menu()` remain public and
backward compatible. Command-backed actions require a `CommandRegistry` and use
the same dispatch authorization as native JSON menu items.

## Compatibility policy

JSForm is pre-release software. Compatible additions may be made within the
`0.1` series. Renaming or removing an exported name, changing stored value
semantics, or changing a JSON property requires documentation, migration advice,
and a version decision before release. Application-specific workflows and
database rules are never part of the JSForm API.
