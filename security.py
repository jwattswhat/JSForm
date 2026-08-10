"""Framework-neutral authorization helpers for JSON-defined forms."""

from __future__ import annotations


class AuthorizationDenied(PermissionError):
    """Raised when a protected JSForm operation is denied."""


class AllowAllAuthorizationPolicy:
    """Compatibility policy for applications that have not enabled security."""

    def has_permission(self, permission_name):
        return True


class DenyAllAuthorizationPolicy:
    """Fail-closed policy useful while a secured application is unavailable."""

    def has_permission(self, permission_name):
        return False


class FormSecurity:
    """Interpret a form definition without knowing application role semantics."""

    OPERATIONS = frozenset({"open", "create", "update", "delete", "report"})
    CONTROL_OPERATIONS = frozenset({"view", "edit", "invoke"})

    def __init__(self, form_name, form_description, control_descriptions, policy=None):
        self.form_name = form_name
        self.form_description = form_description
        self.control_descriptions = control_descriptions
        self.policy = policy or AllowAllAuthorizationPolicy()

    def permission_for(self, operation):
        if operation not in self.OPERATIONS:
            raise ValueError("Unknown form security operation: {}".format(operation))
        return (self.form_description.get("security") or {}).get(operation)

    def control_permission_for(self, control_name, operation):
        if operation not in self.CONTROL_OPERATIONS:
            raise ValueError("Unknown control security operation: {}".format(operation))
        description = self.control_descriptions.get(control_name, {})
        return (description.get("security") or {}).get(operation)

    def _allowed(self, permission_name):
        if permission_name is None:
            return True
        return bool(self.policy.has_permission(permission_name))

    def allows(self, operation):
        return self._allowed(self.permission_for(operation))

    def allows_control(self, control_name, operation):
        return self._allowed(self.control_permission_for(control_name, operation))

    def require(self, operation):
        permission = self.permission_for(operation)
        if not self._allowed(permission):
            raise AuthorizationDenied(
                "Access denied for {} on {}.".format(operation, self.form_name)
            )

    def require_control(self, control_name, operation):
        permission = self.control_permission_for(control_name, operation)
        if not self._allowed(permission):
            raise AuthorizationDenied(
                "Access denied for {} on {}.{}.".format(
                    operation, self.form_name, control_name
                )
            )

    def secured_control_descriptions(self):
        """Return copies with denied edits marked read-only and denied views hidden."""
        result = {}
        for name, source in self.control_descriptions.items():
            description = source.copy()
            if not self.allows_control(name, "edit"):
                description["readonly"] = True
            if not self.allows_control(name, "view"):
                layout = dict(description.get("layout") or {})
                layout["hidden"] = True
                description["layout"] = layout
                description["security_hidden"] = True
            result[name] = description
        return result
