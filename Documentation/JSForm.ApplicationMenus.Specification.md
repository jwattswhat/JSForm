# JSForm JSON Application Menus Specification

**Status:** Approved
**Version:** 0.1
**Date:** August 24, 2026

## 1. Purpose

Add standard desktop application menus to JSForm applications by combining:

- wxPython's native `wx.MenuBar`, `wx.Menu`, and `wx.MenuItem` controls;
- validated JSON files that describe menu organization and presentation; and
- a Python command registry that supplies handlers, authorization, and runtime
  state.

The feature must fit the current JSForm architecture, remain application-neutral,
and allow a command to be presented consistently as a menu item, button, context
menu item, or `StandardActionBar` action.

## 2. Scope

Version 0.1 includes:

- application menu bars on top-level `wx.Frame` windows;
- conventional File, Edit, View, Records, Tools, Window, and Help menus;
- nested submenus, separators, check items, and radio-item groups;
- keyboard shortcuts and wxPython standard command identifiers;
- command enablement, visibility, checked state, and authorization;
- form opening, framework actions, and application callbacks through registered
  commands;
- JSON Schema validation, starter/customized definitions, tests, documentation,
  and a sample application menu.

Version 0.1 does not include:

- a visual menu designer;
- ribbon controls or operating-system global menus;
- arbitrary Python imports or expressions in JSON;
- persistence of application-specific recent-file lists;
- automatic generation of an entire menu from every form or report; or
- ChurchManager-specific menu names, permissions, tables, or workflows.

## 3. Architectural boundaries

JSForm owns the reusable contracts and runtime:

- menu-definition loading and validation;
- command and command-state abstractions;
- wxPython menu construction and event binding;
- integration with JSForm form actions and authorization policies;
- framework-provided commands; and
- safe starter/customization resolution.

Each application owns:

- its menu JSON file;
- application command names and handlers;
- application-specific permission meanings;
- which forms, reports, and tools appear; and
- application state used to enable, check, or hide commands.

JSForm must not import an application package or encode application terminology.
JSON is data only: it may reference a registered command name but may not name a
Python module, callable, SQL statement, or expression to execute.

## 4. Files and public interfaces

The implementation should add these framework files:

| File | Responsibility |
| --- | --- |
| `menu_definition.py` | Immutable menu-definition objects, validation, loading, and safe saving. |
| `menu_commands.py` | Command, command registry, command context, and state contracts. |
| `menu_builder.py` | Construction, binding, refresh, and disposal of wxPython menu objects. |
| `schema/menu_definition_schema.json` | JSON Schema for menu-definition files. |

The following names should be re-exported from `JSForm.__init__` and documented in
`Documentation/PUBLIC_API.md`:

- `ApplicationCommand`
- `CommandContext`
- `CommandRegistry`
- `CommandState`
- `MenuDefinition`
- `MenuDefinitionError`
- `MenuDefinitionLoader`
- `MenuInstaller`
- `save_menu_definition`

`action_ui.Action` remains supported. It should either adapt an
`ApplicationCommand` for button presentation or accept a command name resolved by
the same registry. Existing callers of `install_action_menu()` must continue to
work during the 0.1 series.

## 5. Definition location and resolution

Menu definitions use a distinct application-level JSON contract rather than being
embedded in an individual form definition. A recommended application layout is:

```text
Application/
  Menus/
    main.menu.json
  UserMenus/
    main.menu.json
  Forms/
```

Applications explicitly provide the starter and optional customization paths.
The loader selects a validated customization when present and otherwise selects
the protected starter. This follows JSForm's current rule that starter definitions
remain recoverable and user customizations stay separate.

A malformed customization must not silently replace the starter. The installer
must report a clear validation error and may offer the application a controlled
fallback to the starter. It must never rewrite or delete the invalid file without
an explicit application action.

## 6. JSON contract

### 6.1 Complete example

```json
{
  "$schema": "https://jsform.example/schema/menu-definition-0.1.json",
  "schema_version": 1,
  "name": "main",
  "menus": [
    {
      "label": "&File",
      "items": [
        { "command": "file.new" },
        { "command": "file.open" },
        { "separator": true },
        { "command": "app.exit" }
      ]
    },
    {
      "label": "&Records",
      "items": [
        { "command": "records.schools" },
        { "command": "records.drivers" },
        {
          "label": "&Routes",
          "items": [
            { "command": "records.routes" },
            { "command": "reports.route_manifest" }
          ]
        }
      ]
    },
    {
      "label": "&View",
      "items": [
        { "command": "view.status_bar", "kind": "check" }
      ]
    },
    {
      "label": "&Help",
      "items": [
        { "command": "help.contents" },
        { "separator": true },
        { "command": "app.about" }
      ]
    }
  ]
}
```

### 6.2 Root properties

| Property | Required | Contract |
| --- | --- | --- |
| `$schema` | No | Documentation/editor hint; not used to fetch a remote schema at runtime. |
| `schema_version` | Yes | Integer `1` for this specification. Unknown versions fail closed. |
| `name` | Yes | Stable identifier matching `^[a-z][a-z0-9_-]{0,63}$`. |
| `menus` | Yes | Nonempty ordered array of top-level menu objects. |

Unknown properties are rejected unless a later version explicitly permits them.

### 6.3 Menu objects

A top-level menu requires:

- `label`: nonempty text, with wxPython `&` mnemonic notation permitted; and
- `items`: an ordered, nonempty array.

An optional `help_text` supplies status-bar help where supported. A submenu has
the same `label`, `items`, and optional `help_text` properties inside an item
array. Nesting is limited to four levels to keep menus usable and validation
bounded.

### 6.4 Item objects

Each item must be exactly one of:

1. command item: `{ "command": "namespace.name" }`;
2. separator: `{ "separator": true }`; or
3. submenu: `{ "label": "...", "items": [...] }`.

A command item may override only presentation properties:

| Property | Meaning |
| --- | --- |
| `label` | Menu-specific label; otherwise use the registered command label. |
| `help_text` | Menu-specific help; otherwise use the command help text. |
| `accelerator` | Portable shortcut such as `Ctrl+O`, `Ctrl+Shift+S`, or `F1`. |
| `kind` | `normal`, `check`, or `radio`; default is `normal`. |
| `radio_group` | Required stable name when `kind` is `radio`. Adjacent items in one group form a wxPython radio group. |

Labels and help text are display strings only. The command name is the stable
identity used for event routing, state, logging, tests, and authorization.

Separators may not be first, last, or adjacent after visibility rules are
applied. The builder removes newly redundant separators during refresh.

## 7. Command contract

An `ApplicationCommand` is registered in Python before menu installation:

```python
registry.register(JSForm.ApplicationCommand(
    name="records.routes",
    label="&Routes",
    help_text="Open route records",
    handler=open_routes,
    permission="routes.view",
))
```

The command contains:

| Field | Required | Meaning |
| --- | --- | --- |
| `name` | Yes | Unique dotted lower-case identifier. |
| `label` | Yes | Default user-facing label. |
| `handler` | Yes | Callable receiving `CommandContext`. |
| `help_text` | No | Default status/tool-tip help. |
| `wx_id` | No | Standard wx ID such as `wx.ID_EXIT`; otherwise allocated safely. |
| `permission` | No | Application-neutral authorization key. |
| `state_provider` | No | Callable returning current `CommandState`. |
| `destructive` | No | Metadata for alternate presentations and confirmation policy. |

Command names must match
`^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$`. Duplicate registration is an error.
Every referenced JSON command must be registered; unresolved commands make menu
installation fail with a message identifying the definition path and command.

`CommandContext` provides only controlled runtime references, including the
application frame, current JSForm form when applicable, command name, source
presentation, wx event, authorization policy, and application-supplied services.

Handlers execute on the wx main thread. A long-running handler must use JSForm's
existing background-operation API and marshal UI updates back to the main thread.

## 8. Standard framework commands

JSForm should provide opt-in factories for commands it can implement generically:

| Command | Expected behavior |
| --- | --- |
| `app.exit` | Close the owning top-level frame through the normal close event. |
| `app.about` | Open an application-supplied About dialog or callback. |
| `edit.cut` | Send cut to the focused control when supported. |
| `edit.copy` | Send copy to the focused control when supported. |
| `edit.paste` | Send paste to the focused control when supported. |
| `edit.select_all` | Select all in the focused control when supported. |
| `record.new` | Invoke the current form's existing new-record action. |
| `record.save` | Invoke the current form's existing update/save action. |
| `record.delete` | Invoke the current form's existing delete action and confirmation behavior. |
| `record.refresh` | Reload through the current form's supported refresh path. |

Applications register commands for opening forms, running reports, opening
designers, showing diagnostics, mail previews, preferences, and domain workflows.
JSForm must not guess application commands from filenames or control labels.

Recommended wx IDs and shortcuts are:

| Command | wx ID | Default shortcut |
| --- | --- | --- |
| `file.new` or `record.new` | `wx.ID_NEW` | `Ctrl+N` |
| `file.open` | `wx.ID_OPEN` | `Ctrl+O` |
| `record.save` | `wx.ID_SAVE` | `Ctrl+S` |
| `app.exit` | `wx.ID_EXIT` | none in JSON unless application chooses one |
| `edit.cut` | `wx.ID_CUT` | `Ctrl+X` |
| `edit.copy` | `wx.ID_COPY` | `Ctrl+C` |
| `edit.paste` | `wx.ID_PASTE` | `Ctrl+V` |
| `app.about` | `wx.ID_ABOUT` | none |
| `help.contents` | `wx.ID_HELP` | `F1` |

The application chooses which standard menus and commands apply. Empty menus are
not displayed.

## 9. Installation and lifecycle

Typical application startup is:

```python
definition = JSForm.MenuDefinitionLoader().load("Menus/main.menu.json")
registry = JSForm.CommandRegistry()
register_application_commands(registry, main_form, database)
installer = JSForm.MenuInstaller(main_form.FRAME, registry)
installer.install(definition, current_form=lambda: main_form)
```

`MenuInstaller` must:

1. validate that the target is a top-level `wx.Frame`;
2. resolve all commands before mutating the frame;
3. build a complete `wx.MenuBar` in JSON order;
4. assign standard or collision-free generated wx IDs;
5. bind each ID once to registry dispatch;
6. attach the menu bar only after successful construction;
7. retain command-to-item mappings for refresh; and
8. unbind owned events and destroy replaced menu objects during disposal.

Installation is transactional from the application's perspective: if validation,
resolution, or building fails, the previous menu bar remains installed.

Only `Frame` forms receive a menu bar directly. Dialog and panel forms use their
own controls or the nearest owning frame's application menu. Opening a child form
may change the active command context and trigger a state refresh, but must not
silently replace the application's menu definition.

## 10. State, focus, and refresh

`CommandState` contains:

- `enabled` (default `True`);
- `visible` (default `True`); and
- `checked` (default `False`, meaningful only for check/radio items).

State is evaluated immediately before a menu opens and when the application calls
`installer.refresh()`. The implementation should bind `wx.EVT_MENU_OPEN` for
timely refresh without polling.

Typical rules include:

- Save is enabled only when the active form contains valid, savable changes.
- Delete is enabled only when a current record exists and deletion is authorized.
- Cut/copy/paste depend on the focused control's supported operations.
- A View check item reflects whether its associated pane is currently shown.
- A radio group has exactly one checked visible item when the application state
  supplies one.

A state-provider exception must disable the affected command and report the error
through JSForm's error-reporting boundary. It must not crash menu opening.

## 11. Authorization and safety

Authorization is checked both when state is refreshed and immediately before a
handler is invoked. A command that is hidden or disabled for presentation must
still be denied at dispatch if authorization fails.

The framework passes a command's permission key to the application-provided
authorization policy or adapter. Permission absence means the command has no
framework-level permission requirement; it does not override checks inside an
application service.

Security requirements:

- no `eval`, `exec`, dynamic imports, or dotted-callable lookup from JSON;
- no SQL, filesystem paths, credentials, or secrets embedded in framework menu
  definitions unless they are inert user-facing text;
- no authorization decision based only on a label, menu position, or visibility;
- accelerator dispatch must follow the same registry and authorization path as a
  mouse selection; and
- error and audit context should use the stable command name, not sensitive
  arguments.

Destructive commands must use the same confirmation and service-layer safeguards
as their button or form-action presentation. Marking a command `destructive` does
not itself delete anything and does not replace application confirmation logic.

## 12. Accessibility and platform behavior

- Use native wxPython menus rather than custom-drawn controls.
- Permit `&` mnemonics in labels and validate accelerators before installation.
- Do not encode platform-specific key names beyond the portable accelerator
  vocabulary supported by wxPython.
- Supply concise help text for commands whose result is not obvious.
- Do not rely on color or menu position to communicate state.
- Use standard wx IDs where their platform behavior is desirable, especially
  Exit, About, Help, and common Edit commands.
- Preserve JSON order except where wxPython or the operating system applies its
  native standard-command placement.

## 13. Errors and diagnostics

Definition failures raise `MenuDefinitionError` with:

- the source path when available;
- the JSON property path;
- a concise user-facing explanation; and
- the original exception chained for diagnostics where appropriate.

Runtime handler failures pass through JSForm's configured error reporter. The
context may include menu-definition name, command name, presentation type, and
active form name. It must use existing redaction rules.

## 14. Compatibility and migration

This is a compatible addition to the 0.1 pre-release API. Existing applications
without a menu JSON file continue unchanged.

Existing `Action` and `install_action_menu()` users may migrate incrementally:

1. give each action a stable dotted command name;
2. register its existing handler in `CommandRegistry`;
3. describe menu placement in JSON; and
4. reuse the registered command for action-bar buttons.

No current form JSON property changes are required. The menu schema is separate
from `schema/unified_schema.json` and legacy `jsformschema.json` because it defines
an application shell rather than a form or control.

## 15. Documentation and sample requirements

The implementation is incomplete until it also updates:

- `README.md` with a minimal menu example;
- `Documentation/ARCHITECTURE.md` with the menu components;
- `Documentation/JSForm_Framework.md` with the full contract;
- `Documentation/PUBLIC_API.md` with the exported names;
- `action_ui.py` docstrings describing command reuse; and
- `examples/JSFormSample` with a starter menu definition.

The School Bus Sample should move its top-level navigation commands into a JSON
menu while retaining enough visible buttons to demonstrate that a single command
can be shared by both presentations. Suggested sample menus are Records, Reports,
Tools, and Help, plus File containing Exit.

## 16. Test requirements

### 16.1 Definition and schema tests

- valid root, menu, submenu, command, separator, check, and radio definitions;
- rejection of unknown schema versions and unknown properties;
- rejection of malformed command names, accelerators, and radio groups;
- rejection of excess nesting, empty menus, and invalid separators;
- UTF-8 and UTF-8-with-BOM loading; and
- safe save with validation, temporary file, and `.bak` recovery copy.

### 16.2 Registry tests

- unique registration and deterministic lookup;
- missing and duplicate command errors;
- standard and generated wx ID handling without collisions;
- context construction and handler dispatch;
- authorization recheck at invocation; and
- state-provider failure containment.

### 16.3 wxPython integration tests

- correct menu and item order, labels, kinds, and shortcuts;
- nested submenu construction;
- one event binding and one handler call per selection;
- enabled, visible, and checked refresh behavior;
- focus-sensitive Edit commands;
- cleanup and safe replacement of an installed menu bar; and
- unchanged prior menu if new installation fails.

Tests requiring wxPython should use the project's supported wx runtime. Pure
definition and registry tests must remain runnable without creating visible
windows.

### 16.4 Application and regression tests

- the School Bus Sample launches with its menu definition;
- menu and button presentations invoke the same registered command;
- opening every sample record form from the menu succeeds;
- Exit follows the normal close event;
- unauthorized commands cannot be invoked through menus or accelerators; and
- all existing JSForm form, action-bar, schema, and public-export tests pass.

## 17. Acceptance criteria

The feature is accepted when:

1. a JSForm application can install a native wxPython menu bar from a validated
   JSON definition;
2. the JSON contains no executable Python or application service implementation;
3. registered commands can be shared by menu items and existing action controls;
4. standard, nested, check, radio, separator, and shortcut behavior works;
5. state and authorization are enforced at display and invocation time;
6. invalid or unresolved definitions fail clearly without damaging the current
   menu or protected starter;
7. the sample demonstrates the contract without ChurchManager dependencies;
8. public API, schema, framework reference, sample, docstrings, and tests are
   updated together; and
9. GUI behavior is not called visually verified until the rendered/running sample
   has been inspected on a supported Windows wxPython environment.

## 18. Implementation sequence

1. Add immutable definition objects, JSON Schema, loader, saver, and pure tests.
2. Add command registry, context, state, authorization dispatch, and pure tests.
3. Add `MenuInstaller` and wxPython integration tests.
4. Adapt `Action`/`StandardActionBar` for registered-command reuse while
   preserving compatibility.
5. Add standard framework command factories.
6. Update exports and all required documentation.
7. Convert the School Bus Sample shell to the JSON menu definition.
8. Run the complete JSForm suite and perform a Windows GUI walkthrough.

This specification is approved as the implementation baseline. The proposed
version 0.1 defaults in the following section apply unless they are explicitly
revised before or during implementation.

## 19. Approved version 0.1 defaults

1. **Customization:** Version 0.1 supports a protected starter definition and an
   optional user customization through the resolver described in section 5.
2. **Unauthorized commands:** Commands are disabled by default. An application
   state provider may hide them when revealing their existence would itself be
   inappropriate. Dispatch authorization is always enforced.
3. **Recent items:** Dynamic recent-item submenu providers are deferred beyond
   version 0.1.
4. **Form integration:** The application shell owns menu installation in version
   0.1. `clsForm` supplies current-form behavior through command context without
   acquiring a menu-definition or registry constructor parameter.
