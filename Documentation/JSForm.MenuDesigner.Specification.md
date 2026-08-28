# JSForm Visual Menu Designer Specification

**Status:** Approved
**Version:** 0.1
**Date:** August 25, 2026

## 1. Purpose

Add an application-neutral visual designer for JSForm application-menu JSON.
The designer will let an authorized application developer arrange menus,
submenus, commands, and separators without manually editing JSON, while keeping
the existing validated runtime contract unchanged.

The designer is a development and controlled-customization tool. It does not
create Python handlers, permissions, SQL, or application workflows. Applications
continue to register executable commands in Python and expose only approved
command metadata to the designer.

## 2. Goals

The menu designer will:

- open existing `MenuDefinition` files;
- display the menu hierarchy as a reorderable tree;
- add, rename, move, duplicate, and delete presentation nodes;
- select command items from an application-supplied command catalog;
- edit labels, help text, accelerators, item kinds, and radio groups;
- validate continuously against the current menu-definition contract;
- preview the menu as a real native wxPython menu bar;
- support undo, redo, save, Save As, and restoration from starter or `.bak`;
- preserve protected starter definitions and write only approved customization
  locations; and
- produce JSON that the existing `MenuDefinitionLoader` and `MenuInstaller` can
  consume without conversion.

## 3. Non-goals

Version 0.1 will not:

- generate Python command handlers;
- discover commands by importing arbitrary application modules;
- place Python expressions, SQL, credentials, or permission logic in JSON;
- edit toolbar, ribbon, context-menu, or `StandardActionBar` layouts;
- infer every application form or report automatically;
- edit runtime authorization state;
- alter the menu schema silently;
- overwrite a protected starter file; or
- become a ChurchManager-specific designer.

## 4. Architectural boundaries

### 4.1 JSForm responsibilities

JSForm owns:

- the editable menu model and mutation commands;
- hierarchy, depth, accelerator, radio-group, and separator validation;
- designer, catalog, preview, and property-editor windows;
- safe file resolution and save/backup behavior;
- undo/redo history and dirty-state tracking;
- protected-starter and user-customization workflows; and
- public APIs, documentation, tests, and sample integration.

### 4.2 Application responsibilities

Each application owns:

- its starter and customization directories;
- the approved `ApplicationCommand` registrations;
- user-facing command categories and descriptions;
- authorization to open the designer or save a customization;
- audit handling for saved, restored, or deleted customizations; and
- any deployment or restart policy after a menu changes.

The designer must accept command metadata as data. It must never import an
application package to discover commands.

## 5. Proposed files and public API

| File | Responsibility |
| --- | --- |
| `menu_designer.py` | Editable model, undo/redo transactions, validation, and designer frame. |
| `menu_catalog.py` | Starter/customization catalog model and catalog dialog. |
| `tests/test_menu_designer.py` | Model, validation, undo/redo, and safe-save tests. |
| `tests/test_menu_catalog.py` | Catalog and starter/customization lifecycle tests. |

Proposed public exports:

- `MenuDesignerModel`
- `MenuDesignerFrame`
- `MenuCommandDescriptor`
- `MenuCatalogModel`
- `open_menu_designer`
- `open_menu_catalog`

`MenuDefinition`, `MenuDefinitionLoader`, `save_menu_definition`,
`ApplicationCommand`, and `CommandRegistry` remain the authoritative runtime
contracts.

## 6. Command catalog contract

The designer receives a bounded list of `MenuCommandDescriptor` values. Each
descriptor contains presentation metadata only:

| Field | Required | Meaning |
| --- | --- | --- |
| `name` | Yes | Stable command name such as `records.students`. |
| `label` | Yes | Default user-facing label, including optional mnemonic. |
| `help_text` | No | Default status/help description. |
| `category` | No | Designer grouping such as Records, Reports, or Tools. |
| `default_accelerator` | No | Suggested accelerator. |
| `allowed_kinds` | No | Allowed item kinds; defaults to `normal`. |

Descriptors may be derived explicitly from a `CommandRegistry`, but only the
approved fields above enter the designer. Handlers, state providers,
authorization policies, service objects, and application data are excluded.

Unknown command names already present in a JSON file remain visible and are
reported as validation errors. The designer must not silently delete them.

## 7. Editable model

`MenuDesignerModel` owns an in-memory copy of one validated or recoverably
invalid definition. It exposes deterministic operations rather than allowing
the wx interface to mutate dictionaries directly.

Required operations:

- add top-level menu;
- add command item;
- add submenu;
- add separator;
- rename menu or submenu;
- change command selection;
- set or clear label override;
- set or clear help-text override;
- set or clear accelerator;
- set item kind and radio group;
- move up, move down, indent, and outdent;
- drag and drop to another valid parent;
- duplicate a menu or item;
- delete selected nodes;
- replace the working definition;
- undo and redo; and
- serialize to `MenuDefinition`.

Every successful user operation is one undoable transaction. A rejected
operation does not alter the model or history.

Node identity used by the designer is transient and must not be written into the
runtime JSON contract.

## 8. Designer window

The main `MenuDesignerFrame` uses the configured JSForm application icon and
contains four primary regions:

1. **Command palette** — searchable approved commands grouped by category.
2. **Menu tree** — top-level menus and nested items in exact saved order.
3. **Properties** — fields appropriate to the selected node.
4. **Validation and preview** — current warnings/errors and a native preview.

Recommended command bar:

- Save
- Save As
- Undo
- Redo
- Add Menu
- Add Command
- Add Submenu
- Add Separator
- Duplicate
- Delete
- Move Up
- Move Down
- Indent
- Outdent
- Preview
- Validate
- Restore Starter
- Restore Previous

Buttons and menu actions must share the same internal designer commands.
Keyboard access must include Ctrl+S, Ctrl+Z, Ctrl+Y, Delete, and accessible
alternatives to drag and drop.

## 9. Property editing

### 9.1 Top-level menu and submenu

- label with mnemonic;
- optional help text; and
- read-only hierarchy level.

### 9.2 Command item

- approved command selection;
- optional label override;
- optional help-text override;
- optional accelerator;
- kind: normal, check, or radio; and
- radio-group name when kind is radio.

### 9.3 Separator

Separators have no editable properties. The designer may display a description
explaining that redundant separators will be rejected or normalized only through
an explicit user action.

## 10. Validation rules

Save is blocked while errors exist. Warnings do not block save unless the
application supplies a stricter policy.

Required errors include:

- schema violations;
- blank menu labels;
- unknown command names;
- duplicate accelerators within the menu bar;
- accelerator syntax errors;
- submenu depth greater than four levels;
- empty menus or submenus;
- first, last, or consecutive separators;
- radio items without a radio group;
- a radio group interrupted by an unrelated item;
- command items nested under a separator or command;
- more than 20 top-level menus;
- more than 100 items at one menu level; and
- output outside the approved customization directory.

Recommended warnings include:

- duplicate visible labels at the same level;
- missing mnemonic markers on top-level menus;
- duplicate mnemonic letters at the same level;
- label overrides that substantially differ from command defaults;
- unusually large menus; and
- standard commands placed in unconventional menus.

Validation messages identify the node by a human-readable path such as
`Records > Students` and never expose handlers or application state.

## 11. Native preview

Preview uses the existing `MenuInstaller` in a disposable wx frame. It shows
native labels, submenus, separators, check/radio styles, and accelerators.

Preview must not execute real application commands. The designer creates a
temporary inert registry containing only safe preview handlers. Selecting an
item may display its command name and help text in the preview status bar.

Preview failure leaves the working definition intact and reports a bounded,
user-facing error.

## 12. Starter and customization lifecycle

The menu catalog follows the established screen/report pattern:

- protected starters live in an application-supplied starter directory;
- editable definitions live in a separate approved user directory;
- opening a starter for editing creates a user customization;
- saving uses `save_menu_definition()` and retains the previous valid `.bak`;
- Restore Starter loads the starter into the model but does not change disk
  until Save;
- Restore Previous loads the `.bak` into the model but does not change disk
  until Save; and
- Delete Customization requires confirmation and restores starter resolution.

The designer never writes to a starter path, even when filesystem permissions
would allow it.

## 13. Menu catalog

`MenuCatalogModel` lists starter and custom menu definitions with:

- definition name;
- display filename;
- active source: Starter or Custom;
- validation status;
- customization status; and
- last-modified time when available.

The catalog supports:

- Open Designer;
- New from Selected;
- Delete Customization; and
- Refresh.

New definitions must use a schema-valid lowercase name and a safe `.json`
filename inside the approved customization directory.

## 14. Dirty state and close behavior

The designer is dirty when its current serialized definition differs from the
last loaded or saved baseline. Closing a dirty designer offers:

- Save;
- Discard; or
- Cancel.

Validation errors prevent Save but never prevent Discard or Cancel. A failed
save leaves the window open and dirty.

## 15. Authorization and auditing

JSForm supplies no menu-design permission names. The application decides who
may open or save the designer.

Optional audit hooks receive bounded events:

- menu customization opened;
- menu customization saved;
- starter loaded into the working model;
- previous version loaded;
- customization deleted; and
- validation failed at save.

Audit events may include definition name, path category, action, and error count.
They must not include handlers, credentials, database contents, or unrestricted
exception text.

## 16. Error handling and recovery

- Invalid existing JSON opens in a recovery view when its structure can be
  represented safely; otherwise the designer offers starter or `.bak` recovery.
- The invalid file is never overwritten until the user explicitly saves a valid
  replacement.
- Save is atomic and preserves the prior valid version.
- A preview or UI failure cannot damage the working file.
- Missing command descriptors are errors, not automatic deletions.

## 17. Accessibility and keyboard behavior

- Every toolbar operation has a labeled button, menu action, or shortcut.
- Tree position and item type are exposed through accessible labels.
- Drag and drop is optional; move and indent buttons are always available.
- Validation does not rely on color alone.
- Focus order follows command palette, tree, properties, validation, then action
  controls.
- Mnemonic characters are displayed and checked for conflicts.

## 18. Testing requirements

### 18.1 Model tests

- every mutation and its undo/redo inverse;
- move, indent, and outdent boundaries;
- depth and item-count limits;
- command catalog resolution;
- accelerator and mnemonic conflicts;
- radio-group rules;
- dirty-state transitions;
- deterministic serialization; and
- rejected operations leave state unchanged.

### 18.2 Catalog and persistence tests

- starter/custom resolution;
- opening a starter creates a separate custom file;
- safe approved paths only;
- atomic save and `.bak` retention;
- restore starter and previous version;
- delete customization; and
- malformed files remain recoverable.

### 18.3 wx integration tests

- native tree/property synchronization;
- command-palette search;
- button and keyboard action parity;
- close-with-unsaved-changes workflow;
- application icon application; and
- inert native preview construction.

### 18.4 Distribution tests

- new modules and documentation ship in wheel/source archives as appropriate;
- no application-specific command catalog ships in the framework; and
- sample designer definitions contain no Python, SQL, or credentials.

## 19. Sample acceptance scenario

The JSForm School Bus Sample supplies descriptors for its existing Records,
Reports, Tools, File, and Help commands. Acceptance requires demonstrating:

1. opening the protected `main.menu.json` starter;
2. creating a separate customization;
3. moving `Find Student` within Records;
4. adding a submenu and an approved command;
5. assigning and validating an accelerator;
6. previewing the native menu without executing database actions;
7. saving and reopening the customization;
8. confirming the application loads it through `MenuDefinitionLoader`; and
9. deleting the customization and returning to the starter.

No sample database records may change during this walkthrough.

## 20. Implementation roadmap

1. **Editable model** — node operations, validation, transactions, undo/redo,
   and deterministic serialization.
2. **Safe persistence and catalog** — customization creation, backup, restore,
   delete, and approved path handling.
3. **Designer interface** — tree, command palette, properties, actions, dirty
   state, and accessibility.
4. **Native preview** — inert registry and disposable `MenuInstaller` frame.
5. **Framework integration** — public exports, icons, error handling,
   documentation, and distribution checks.
6. **Sample and acceptance** — School Bus descriptors, customization directory,
   automated tests, and rendered walkthrough.

## 21. Acceptance criteria

The feature is complete when:

- all supported menu JSON can be opened, edited, validated, and saved;
- output loads unchanged through the existing runtime loader;
- undo/redo covers every editing operation;
- starter files cannot be overwritten by designer actions;
- unknown commands and invalid accelerators block save clearly;
- native preview is inert and visually inspected;
- the sample customization lifecycle is demonstrated without database writes;
- documentation and public API inventories are current;
- the full safe JSForm suite passes; and
- rebuilt distribution artifacts contain the documented designer surface.

## 22. Approval decisions

The following decisions require approval before implementation:

1. Whether version 0.1 supports editing only one menu definition at a time or
   also includes the catalog window. This specification recommends including the
   catalog.
2. Whether invalid JSON should have a raw-text repair mode. This specification
   recommends no raw editor in version 0.1; use starter/backup recovery instead.
3. Whether applications may mark selected commands as required and undeletable.
   This specification recommends an optional protected-command manifest modeled
   after protected report controls.
4. Whether saving a customization takes effect immediately or on next launch.
   This specification recommends application-controlled reload, with next launch
   as the safe default.
