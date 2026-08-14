# Contributing to JSForm

Thank you for improving JSForm. Contributions should keep the framework useful
to applications other than ChurchManager.

## Before changing code

1. Describe the user-visible problem or framework capability.
2. Decide whether the behavior belongs in JSForm or in an application.
3. Add or update tests that express the intended behavior.
4. Preserve compatibility unless the change is intentionally documented as
   breaking.

## Development workflow

- Work on a focused branch and keep commits limited to one coherent change.
- Never commit credentials, database dumps, generated reports, logs, or local
  virtual environments.
- Use parameterized SQL. Do not construct SQL from user-provided values.
- Keep GUI work on the wxPython UI thread; use the background-operation API for
  long work.
- Validate JSON definitions against `jsformschema.json`.
- Run `python run_jsform_tests.py` before committing.

## Code documentation standard

- Every new Python module needs a short module docstring describing its role.
- Public classes and functions need docstrings that explain their contract,
  parameters, return value, side effects, and meaningful exceptions.
- Comments should explain *why* a non-obvious decision exists. Do not restate
  straightforward code.
- Public functions should use type hints where they clarify the interface.
- A new or changed JSON property must update the schema, framework reference,
  sample where useful, and tests in the same change.
- User-visible behavior, setup, security, or compatibility changes must update
  the relevant Markdown documentation in the same commit.

## Tests and review

Automated tests are necessary but do not replace GUI review. For layout or
report changes, record which screen sizes, interactions, and rendered outputs
were checked. Never describe a visual result as verified unless it was rendered
and inspected.

## Licensing contributions

By contributing, you agree that your contribution is licensed under
LGPL-3.0-or-later, the license used by JSForm.
