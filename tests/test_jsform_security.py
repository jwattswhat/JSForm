import unittest

from security import (
    AllowAllAuthorizationPolicy, AuthorizationDenied, DenyAllAuthorizationPolicy,
    FormSecurity,
)


class PermissionPolicy:
    def __init__(self, permissions=()):
        self.permissions = set(permissions)

    def has_permission(self, permission_name):
        return permission_name in self.permissions


class TestFormSecurity(unittest.TestCase):
    FORM = {
        "security": {
            "open": "people.records.view",
            "create": "people.records.create",
            "update": "people.records.edit",
            "delete": "people.records.delete",
        }
    }
    CONTROLS = {
        "Name": {
            "type": "TextCtrl",
            "security": {"view": "people.records.view", "edit": "people.records.edit"},
        },
        "PastoralNote": {
            "type": "MultiLine",
            "security": {
                "view": "pastoral.notes.view", "edit": "pastoral.notes.edit"
            },
        },
        "Unprotected": {"type": "TextCtrl"},
        "ProtectedAction": {
            "type": "Button",
            "security": {"invoke": "people.records.export"},
        },
    }

    def test_form_operations_use_declared_permissions(self):
        security = FormSecurity(
            "frmPerson", self.FORM, self.CONTROLS,
            PermissionPolicy({"people.records.view", "people.records.edit"}),
        )
        self.assertTrue(security.allows("open"))
        self.assertTrue(security.allows("update"))
        self.assertFalse(security.allows("delete"))
        with self.assertRaises(AuthorizationDenied):
            security.require("delete")

    def test_undeclared_operations_preserve_legacy_compatibility(self):
        security = FormSecurity("frmLegacy", {}, {}, DenyAllAuthorizationPolicy())
        self.assertTrue(security.allows("open"))

    def test_control_security_marks_denied_fields_hidden_or_readonly(self):
        security = FormSecurity(
            "frmPerson", self.FORM, self.CONTROLS,
            PermissionPolicy({"people.records.view"}),
        )
        secured = security.secured_control_descriptions()
        self.assertTrue(secured["Name"]["readonly"])
        self.assertTrue(secured["PastoralNote"]["security_hidden"])
        self.assertTrue(secured["PastoralNote"]["layout"]["hidden"])
        self.assertTrue(secured["ProtectedAction"]["security_disabled"])
        self.assertNotIn("readonly", secured["Unprotected"])

    def test_compatibility_and_fail_closed_policies_are_explicit(self):
        self.assertTrue(AllowAllAuthorizationPolicy().has_permission("anything"))
        self.assertFalse(DenyAllAuthorizationPolicy().has_permission("anything"))


if __name__ == "__main__":
    unittest.main()
