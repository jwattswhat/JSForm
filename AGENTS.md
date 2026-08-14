# JSForm Contribution Rules

- JSForm contains reusable framework behavior and must not import ChurchManager
  or encode church-specific tables, permissions, or terminology.
- Treat documentation as part of every implementation change. Update the schema,
  framework reference, sample, docstrings, and tests together when a public JSON
  or Python contract changes.
- New top-level Python modules require module docstrings; public interfaces
  require useful contract docstrings.
- Keep starter definitions recoverable and user customizations separate.
- Never commit credentials, logs, database dumps, generated reports, or virtual
  environments.
- Do not claim GUI or report layout is visually verified unless it was rendered
  and inspected.
