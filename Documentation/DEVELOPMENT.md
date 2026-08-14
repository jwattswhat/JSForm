# JSForm development guide

## Environment

Create a local virtual environment and install `requirements.txt`. Do not commit
the environment. The framework is currently developed and tested primarily on
Windows because its desktop applications use wxPython and Windows Credential
Manager, but portable behavior should remain isolated from Windows adapters.

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
