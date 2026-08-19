# JSForm public API

Applications install the `jsform-desktop` distribution and use `import JSForm`.
Names re-exported by `JSForm/__init__.py` are the supported Python API during
the current pre-release series. Direct imports from internal modules may change
unless the framework reference specifically documents them.

The supported surface includes:

- database connections, records, SQL writing, choices, and form lifecycle;
- JSON form loading, controls, responsive layouts, and authorization policies;
- reusable list, grid, search/select, ordered-child, and compact-editor behavior;
- screen and report definitions, catalogs, designers, datasets, and PDF output;
- background operations, conditional status formatting, mail services,
  credential storage, error reporting, and support packages; and
- the constants and compatibility classes already re-exported by `JSForm`.

JSON contracts are versioned alongside the Python API. Applications should use
the bundled schemas and documented properties rather than relying on parser
implementation details.

## Compatibility policy

JSForm is pre-release software. Compatible additions may be made within the
`0.1` series. Renaming or removing an exported name, changing stored value
semantics, or changing a JSON property requires documentation, migration advice,
and a version decision before release. Application-specific workflows and
database rules are never part of the JSForm API.
