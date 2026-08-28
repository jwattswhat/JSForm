# JSForm

JSForm is a Python and wxPython framework for building MariaDB/MySQL desktop
applications from JSON screen definitions. It supplies database-backed fields,
record navigation, validation, responsive layouts, visual screen and report
designers, PDF reporting, background operations, and support diagnostics.

**[Website](https://jwattswhat.github.io/JSForm-Website/)** ·
**[Documentation](Documentation/JSForm_Framework.md)** ·
**[Releases](https://github.com/jwattswhat/JSForm/releases)** ·
**[Issues](https://github.com/jwattswhat/JSForm/issues)**

The repository includes the deliberately small **School Bus Routes** sample in
[`examples/JSFormSample`](examples/JSFormSample/README.md). It is the preferred
place to learn or verify framework behavior without ChurchManager data or
security.

## Project status

The current development version is defined in [`version.py`](version.py).
JSForm is under active pre-release development and its public APIs may still
change. New applications should use the documented APIs and JSON schema rather
than depending on implementation details.

## Requirements

- Python 3.10 or a compatible newer Python 3 release
- wxPython
- MariaDB or MySQL
- The packages in [`requirements.txt`](requirements.txt)

Create a fresh virtual environment rather than copying one from another
computer. JSForm's distribution name is `jsform-desktop`; its Python import
remains `import JSForm`.

For framework development, install this checkout in editable mode:

```powershell
python -m pip install -e .
```

Applications can install a built wheel without requiring the JSForm repository
to remain beside the application.

## Quick start

The sample application has isolated setup and run instructions:

```powershell
python examples\JSFormSample\setup_sample.py
python examples\JSFormSample\app.py
```

For a full framework introduction, database contract, JSON properties, control
reference, reports, public API, and application checklist, read
[`Documentation/JSForm_Framework.md`](Documentation/JSForm_Framework.md).

### JSON application menus

Top-level wxPython frames can install a native menu bar from validated JSON.
JSON controls placement and presentation; Python registers the executable
handlers:

```json
{
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
    }
  ]
}
```

```python
registry = JSForm.CommandRegistry()
registry.register(JSForm.ApplicationCommand(
    "file.open", "&Open", open_file,
    help_text="Open a file",
))
registry.register_many(JSForm.standard_application_commands("My Application"))

definition = JSForm.MenuDefinitionLoader().load("Menus/main.menu.json")
installer = JSForm.MenuInstaller(frame, registry)
installer.install(definition)
```

The [School Bus Sample](examples/JSFormSample/README.md) demonstrates File,
Records, Reports, Tools, and Help menus whose commands are also used by visible
buttons.

## Tests

Run the safe framework suite from this directory:

```powershell
python run_jsform_tests.py
```

The default suite does not open the GUI, send mail, or modify a database.
Optional database checks are explained in [`tests/README.md`](tests/README.md).

## Build the package

Build the wheel and source archive from the repository root:

```powershell
python -m build
```

Generated distributions are written to `dist/` and are not committed. Release
acceptance installs the wheel into a clean environment and tests `import
JSForm` from outside the repository.

## Documentation map

- [Framework reference](Documentation/JSForm_Framework.md)
- [Architecture](Documentation/ARCHITECTURE.md)
- [Development guide](Documentation/DEVELOPMENT.md)
- [Public API policy](Documentation/PUBLIC_API.md)
- [Package release procedure](Documentation/RELEASING.md)
- [Versioning](Documentation/VERSIONING.md)
- [Enhancement backlog](JSFORM_ENHANCEMENTS.md)
- [Error-reporting specification](Documentation/JSForm.ErrorLogging.Specification.md)
- [Application-menu specification](Documentation/JSForm.ApplicationMenus.Specification.md)
- [Visual menu-designer specification](Documentation/JSForm.MenuDesigner.Specification.md)
- [Report Designer guide](Documentation/REPORT_DESIGNER.md)
- [Contributing](CONTRIBUTING.md)
- [Security](SECURITY.md)
- [Support](SUPPORT.md)

## Applications built with JSForm

JSForm contains reusable framework behavior. Application-specific workflows,
authorization policies, database migrations, and domain rules belong in the
application repository. ChurchManager is a separate application built on
JSForm; neither project imports application-specific behavior into the other.

## License

Copyright (C) 2026 Rev. Jonathan C. Watt.

JSForm is licensed under the GNU Lesser General Public License v3.0 or later
(`LGPL-3.0-or-later`). See [`LICENSE`](LICENSE).
