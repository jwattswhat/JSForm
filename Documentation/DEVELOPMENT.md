# JSForm development guide

## Environment

Create a local virtual environment and install the framework in editable mode
with `python -m pip install -e .`. Do not commit the environment. Runtime
dependencies and package metadata are authoritative in `pyproject.toml`;
`requirements.txt` remains a temporary compatibility input until dependency
cleanup is completed. The framework is currently developed and tested primarily
on Windows because its desktop applications use wxPython and Windows Credential
Manager, but portable behavior should remain isolated from Windows adapters.

The Python distribution is named `jsform-desktop`; applications continue to use
`import JSForm`. Packaging development must not introduce application-specific
behavior or require ChurchManager to be present.

## Package verification

1. Run `python run_jsform_tests.py` in a complete development environment.
2. Run `python -m build` to create the wheel and source archive.
3. Inspect both archives and confirm that `Forms/*.json` and `schema/*.json` are
   included while tests, logs, reports, backups, and virtual environments are
   excluded from the wheel.
   Run `python verify_distribution.py` to enforce the artifact contents.
4. Install the wheel into a clean environment without the repository on
   `sys.path`.
5. Import `JSForm`, verify `JSForm.__version__`, and resolve the bundled schema.
6. Run the School Bus Routes sample against the installed distribution before a
   packaging release is accepted.

## Verification levels

1. **Unit tests:** `python run_jsform_tests.py`
2. **Sample integration:** set up and run `examples/JSFormSample`
3. **GUI review:** resize, navigate, edit, cancel, save, reopen, and exercise
   keyboard and double-click behavior
4. **Report review:** render PDFs and inspect pagination, alignment, clipping,
   and fallback from customized definitions to starters

Database tests must use an isolated test database and restricted account.

## Definition changes

When adding a JSON capability, update together:

- `jsformschema.json`;
- parsing/runtime code;
- the framework reference;
- a focused automated test; and
- the sample application when it provides a useful demonstration.

## Documentation maintenance

Documentation is part of the feature. During every change, review the README,
framework reference, architecture, development guide, version notes, sample,
and enhancement backlog that the change affects. Broken links, obsolete names,
and instructions that cannot be followed are defects.

Release preparation must replace `-dev` in `version.py`, update version notes,
run the complete test suite, and review the license and dependency notices.
