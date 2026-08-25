import unittest

from menu_commands import (
    ApplicationCommand, CommandContext, CommandRegistry, CommandState,
)
from security import AuthorizationDenied


class PermissionPolicy:
    def __init__(self, permissions=()):
        self.permissions = set(permissions)

    def has_permission(self, permission):
        return permission in self.permissions


class BrokenPermissionPolicy:
    def has_permission(self, _permission):
        raise RuntimeError("authorization unavailable")


def command(name="file.open", **overrides):
    values = {
        "name": name,
        "label": "&Open",
        "handler": lambda context: context.command_name,
    }
    values.update(overrides)
    return ApplicationCommand(**values)


class TestMenuCommands(unittest.TestCase):
    def setUp(self):
        self.reports = []
        self.registry = CommandRegistry(
            error_reporter=lambda error, **context: self.reports.append((error, context))
        )

    def test_command_validates_public_contract(self):
        self.assertEqual(command().name, "file.open")
        invalid = (
            {"name": "Open"},
            {"name": "file-open"},
            {"label": " "},
            {"handler": "not callable"},
            {"permission": "Admin"},
            {"wx_id": True},
            {"state_provider": "not callable"},
        )
        for overrides in invalid:
            with self.subTest(overrides=overrides), self.assertRaises((TypeError, ValueError)):
                command(**overrides)

    def test_context_copies_services_and_specializes_invocation(self):
        source = {"database": object()}
        context = CommandContext(frame="frame", services=source)
        source["later"] = object()
        self.assertNotIn("later", context.services)
        with self.assertRaises(TypeError):
            context.services["changed"] = True
        specialized = context.for_command("file.open", event="event", source="menu")
        self.assertEqual(specialized.command_name, "file.open")
        self.assertEqual(specialized.event, "event")
        self.assertEqual(specialized.source, "menu")
        self.assertEqual(specialized.frame, "frame")

    def test_registration_lookup_order_and_explicit_wx_ids(self):
        first = command("file.open", wx_id=5000)
        second = command("app.exit", label="E&xit", wx_id=5001)
        self.assertIs(self.registry.register(first), first)
        self.registry.register(second)
        self.assertEqual(self.registry.names, ("file.open", "app.exit"))
        self.assertIs(self.registry.get("file.open"), first)
        self.assertIs(self.registry.get_by_wx_id(5001), second)
        self.assertIn("file.open", self.registry)

    def test_duplicate_names_and_wx_ids_are_rejected(self):
        self.registry.register(command(wx_id=5000))
        with self.assertRaisesRegex(ValueError, "already registered"):
            self.registry.register(command())
        with self.assertRaisesRegex(ValueError, "already registered"):
            self.registry.register(command("file.save", wx_id=5000))

    def test_batch_registration_is_transactional(self):
        commands = (
            command("file.open", wx_id=5000),
            command("file.save", wx_id=5000),
        )
        with self.assertRaises(ValueError):
            self.registry.register_many(commands)
        self.assertEqual(len(self.registry), 0)

    def test_missing_names_and_ids_fail_clearly(self):
        with self.assertRaisesRegex(KeyError, "not registered"):
            self.registry.get("file.missing")
        with self.assertRaisesRegex(KeyError, "not registered"):
            self.registry.get_by_wx_id(9999)

    def test_default_and_provider_state_are_returned(self):
        self.registry.register(command())
        self.registry.register(command(
            "view.status_bar", label="Status Bar",
            state_provider=lambda _context: CommandState(
                enabled=False, visible=True, checked=True,
            ),
        ))
        self.assertEqual(self.registry.state("file.open"), CommandState())
        self.assertEqual(
            self.registry.state("view.status_bar"),
            CommandState(enabled=False, visible=True, checked=True),
        )

    def test_state_provider_failure_is_reported_and_disabled(self):
        def failing_state(_context):
            raise RuntimeError("state failed")

        self.registry.register(command(state_provider=failing_state))
        self.assertEqual(
            self.registry.state("file.open"), CommandState(enabled=False)
        )
        self.assertEqual(len(self.reports), 1)
        self.assertEqual(self.reports[0][1]["operation"], "command.state")
        self.assertEqual(self.reports[0][1]["command_name"], "file.open")

    def test_invalid_state_provider_result_is_contained(self):
        self.registry.register(command(state_provider=lambda _context: True))
        self.assertFalse(self.registry.state("file.open").enabled)
        self.assertIsInstance(self.reports[0][0], TypeError)

    def test_protected_command_fails_closed_without_policy(self):
        self.registry.register(command(permission="files.records.open"))
        self.assertFalse(self.registry.state("file.open").enabled)
        with self.assertRaises(AuthorizationDenied):
            self.registry.dispatch("file.open")

    def test_authorized_command_dispatches_with_runtime_context(self):
        observed = []
        self.registry.register(command(
            permission="files.records.open",
            handler=lambda context: observed.append(context) or "opened",
        ))
        base = CommandContext(
            frame="frame",
            authorization_policy=PermissionPolicy({"files.records.open"}),
        )
        result = self.registry.dispatch(
            "file.open", base, event="event", source="accelerator"
        )
        self.assertEqual(result, "opened")
        self.assertEqual(observed[0].command_name, "file.open")
        self.assertEqual(observed[0].source, "accelerator")
        self.assertEqual(observed[0].event, "event")

    def test_dispatch_rechecks_authorization_after_state(self):
        policy = PermissionPolicy({"files.records.open"})
        context = CommandContext(authorization_policy=policy)
        self.registry.register(command(permission="files.records.open"))
        self.assertTrue(self.registry.state("file.open", context).enabled)
        policy.permissions.clear()
        with self.assertRaises(AuthorizationDenied):
            self.registry.dispatch("file.open", context)

    def test_broken_authorization_policy_fails_closed_and_is_reported(self):
        context = CommandContext(authorization_policy=BrokenPermissionPolicy())
        self.registry.register(command(permission="files.records.open"))
        self.assertFalse(self.registry.state("file.open", context).enabled)
        with self.assertRaises(AuthorizationDenied):
            self.registry.dispatch("file.open", context)
        self.assertTrue(any(
            report[1]["operation"] == "command.authorization"
            for report in self.reports
        ))

    def test_disabled_or_hidden_command_cannot_dispatch(self):
        for state in (
            CommandState(enabled=False),
            CommandState(visible=False),
        ):
            registry = CommandRegistry(error_reporter=lambda *_args, **_kwargs: None)
            registry.register(command(state_provider=lambda _context, value=state: value))
            with self.subTest(state=state), self.assertRaises(AuthorizationDenied):
                registry.dispatch("file.open")

    def test_handler_failure_is_reported_and_reraised(self):
        def fail(_context):
            raise RuntimeError("handler failed")

        self.registry.register(command(handler=fail))
        with self.assertRaisesRegex(RuntimeError, "handler failed"):
            self.registry.dispatch("file.open", source="menu")
        self.assertEqual(len(self.reports), 1)
        self.assertEqual(self.reports[0][1]["operation"], "command.dispatch")
        self.assertEqual(self.reports[0][1]["command_source"], "menu")

    def test_error_reporter_failure_does_not_replace_original_failure(self):
        registry = CommandRegistry(
            error_reporter=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("reporting failed")
            )
        )
        registry.register(command(
            state_provider=lambda _context: (_ for _ in ()).throw(
                ValueError("state failed")
            )
        ))
        self.assertEqual(registry.state("file.open"), CommandState(enabled=False))


if __name__ == "__main__":
    unittest.main()
