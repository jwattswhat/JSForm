import importlib.util
from pathlib import Path
import sys
import types
import unittest


class FakeMenuItem:
    def __init__(self, item_id, label="", help_text="", kind=0, submenu=None):
        self.item_id = item_id
        self.label = label
        self.help_text = help_text
        self.kind = kind
        self.submenu = submenu
        self.enabled = True
        self.checked = False

    def GetId(self):
        return self.item_id

    def Enable(self, enabled=True):
        self.enabled = bool(enabled)

    def Check(self, checked=True):
        self.checked = bool(checked)


class FakeMenu:
    def __init__(self):
        self.items = []

    def Append(self, item_id, label, help_text="", kind=0):
        item = FakeMenuItem(item_id, label, help_text, kind)
        self.items.append(item)
        return item

    def AppendSeparator(self):
        item = FakeMenuItem(-1, kind=3)
        self.items.append(item)
        return item

    def AppendSubMenu(self, submenu, label, help_text=""):
        item = FakeMenuItem(-1, label, help_text, submenu=submenu)
        self.items.append(item)
        return item

    def Remove(self, item):
        self.items.remove(item)
        return item

    def Insert(self, position, item):
        self.items.insert(position, item)
        return item

    def GetMenuItems(self):
        return list(self.items)


class FakeMenuBar:
    def __init__(self):
        self.entries = []
        self.destroyed = False

    def Append(self, menu, label):
        self.entries.append((menu, label))
        return True

    def Insert(self, position, menu, label):
        self.entries.insert(position, (menu, label))
        return True

    def Remove(self, position):
        return self.entries.pop(position)[0]

    def GetMenuCount(self):
        return len(self.entries)

    def GetMenu(self, position):
        return self.entries[position][0]

    def Destroy(self):
        self.destroyed = True


class FakeFrame:
    def __init__(self):
        self.menu_bar = None
        self.bindings = []
        self.fail_set_menu_bar = False
        self.closed = False

    def GetMenuBar(self):
        return self.menu_bar

    def SetMenuBar(self, menu_bar):
        if self.fail_set_menu_bar:
            raise RuntimeError("cannot install menu bar")
        self.menu_bar = menu_bar

    def Close(self):
        self.closed = True
        return True

    def Bind(self, event_type, handler, id=None):
        self.bindings.append((event_type, handler, id))
        return True

    def Unbind(self, event_type, handler=None, id=None):
        candidate = (event_type, handler, id)
        if candidate in self.bindings:
            self.bindings.remove(candidate)
            return True
        return False

    def fire(self, event_type, item_id=None, event=None):
        for bound_type, handler, bound_id in tuple(self.bindings):
            if bound_type == event_type and bound_id == item_id:
                handler(event or FakeEvent())


class FakeEvent:
    def __init__(self):
        self.skipped = False

    def Skip(self):
        self.skipped = True


class FakeWindowIDRef:
    live = []

    def __init__(self, value):
        self.value = value
        self.live.append(self)

    def __int__(self):
        return self.value


class FakePanel:
    def __init__(self, parent=None):
        self.parent = parent
        self.sizer = None
        self.layout_count = 0

    def SetSizer(self, sizer):
        self.sizer = sizer

    def SetWindowStyle(self, _style):
        return None

    def GetWindowStyle(self):
        return 0

    def Layout(self):
        self.layout_count += 1


class FakeButton:
    def __init__(self, parent, item_id=-1, label=""):
        self.parent = parent
        self.item_id = item_id
        self.label = label
        self.enabled = True
        self.shown = True
        self.handlers = []
        self.tooltip = ""

    def Bind(self, event_type, handler):
        self.handlers.append((event_type, handler))

    def click(self, event=None):
        for _event_type, handler in self.handlers:
            handler(event or FakeEvent())

    def Enable(self, enabled=True):
        self.enabled = bool(enabled)

    def Disable(self):
        self.enabled = False

    def Show(self, shown=True):
        self.shown = bool(shown)

    def SetToolTip(self, tooltip):
        self.tooltip = tooltip

    def SetForegroundColour(self, _colour):
        return None


class FakeBoxSizer:
    def __init__(self, _orientation):
        self.items = []

    def Add(self, item, *_args):
        self.items.append(item)

    def AddStretchSpacer(self):
        self.items.append("stretch")


class FakeWindow:
    focused = None

    @classmethod
    def FindFocus(cls):
        return cls.focused


_next_id = 7000


def new_id_ref():
    global _next_id
    _next_id += 1
    return FakeWindowIDRef(_next_id)


fake_wx = types.ModuleType("wx")
fake_wx.Frame = FakeFrame
fake_wx.Panel = FakePanel
fake_wx.Button = FakeButton
fake_wx.BoxSizer = FakeBoxSizer
fake_wx.Window = FakeWindow
fake_wx.Menu = FakeMenu
fake_wx.MenuBar = FakeMenuBar
fake_wx.NewIdRef = new_id_ref
fake_wx.EVT_MENU = "EVT_MENU"
fake_wx.EVT_MENU_OPEN = "EVT_MENU_OPEN"
fake_wx.ITEM_NORMAL = 0
fake_wx.ITEM_CHECK = 1
fake_wx.ITEM_RADIO = 2
fake_wx.ID_ANY = -1
fake_wx.ID_EXIT = 5001
fake_wx.ID_ABOUT = 5002
fake_wx.ID_CUT = 5003
fake_wx.ID_COPY = 5004
fake_wx.ID_PASTE = 5005
fake_wx.ID_SELECTALL = 5006
fake_wx.ID_NEW = 5007
fake_wx.ID_SAVE = 5008
fake_wx.ID_DELETE = 5009
fake_wx.ID_REFRESH = 5010
fake_wx.OK = 1
fake_wx.HORIZONTAL = 1
fake_wx.RIGHT = 2
fake_wx.BORDER_SIMPLE = 4
fake_wx.EVT_BUTTON = "EVT_BUTTON"
fake_wx.Colour = lambda *_args: object()
fake_wx.MessageBox = lambda *_args, **_kwargs: fake_wx.OK
from menu_commands import (
    ApplicationCommand, CommandContext, CommandRegistry, CommandState,
)
from menu_definition import MenuDefinitionLoader


def load_with_fake_wx(module_name, filename):
    path = Path(__file__).resolve().parents[1] / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_real_wx = sys.modules.get("wx")
sys.modules["wx"] = fake_wx
try:
    _menu_builder = load_with_fake_wx("_jsform_test_menu_builder", "menu_builder.py")
    _action_ui = load_with_fake_wx("_jsform_test_action_ui", "action_ui.py")
    _standard_commands = load_with_fake_wx(
        "_jsform_test_standard_commands", "standard_commands.py"
    )
finally:
    if _real_wx is None:
        sys.modules.pop("wx", None)
    else:
        sys.modules["wx"] = _real_wx

MenuInstallationError = _menu_builder.MenuInstallationError
MenuInstaller = _menu_builder.MenuInstaller
Action = _action_ui.Action
StandardActionBar = _action_ui.StandardActionBar
action_from_command = _action_ui.action_from_command
standard_application_commands = _standard_commands.standard_application_commands
standard_edit_commands = _standard_commands.standard_edit_commands
standard_record_commands = _standard_commands.standard_record_commands


def definition_data():
    return {
        "schema_version": 1,
        "name": "main",
        "menus": [
            {
                "label": "&File",
                "items": [
                    {"command": "file.open", "accelerator": "Ctrl+O"},
                    {"separator": True},
                    {"command": "app.exit"},
                ],
            },
            {
                "label": "&View",
                "items": [
                    {"command": "view.status", "kind": "check"},
                    {
                        "label": "&Theme",
                        "items": [
                            {
                                "command": "view.theme.system", "kind": "radio",
                                "radio_group": "theme",
                            },
                            {
                                "command": "view.theme.light", "kind": "radio",
                                "radio_group": "theme",
                            },
                        ],
                    },
                ],
            },
        ],
    }


class MutableStates:
    def __init__(self):
        self.values = {}

    def for_name(self, name):
        return lambda _context: self.values.get(name, CommandState())


class TestMenuBuilder(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.states = MutableStates()
        self.registry = CommandRegistry(error_reporter=lambda *_args, **_kwargs: None)
        for index, name in enumerate((
            "file.open", "app.exit", "view.status",
            "view.theme.system", "view.theme.light",
        )):
            self.registry.register(ApplicationCommand(
                name=name,
                label={"app.exit": "E&xit", "view.status": "Status &Bar"}.get(
                    name, name
                ),
                handler=lambda context, selected=name: self.calls.append(
                    (selected, context.source, context.event)
                ),
                wx_id=5100 if name == "app.exit" else None,
                state_provider=self.states.for_name(name),
            ))
        self.definition = MenuDefinitionLoader().from_dict(definition_data())
        self.frame = FakeFrame()
        self.installer = MenuInstaller(self.frame, self.registry)

    def test_requires_frame_registry_and_validated_definition(self):
        with self.assertRaises(TypeError):
            MenuInstaller(object(), self.registry)
        with self.assertRaises(TypeError):
            MenuInstaller(self.frame, object())
        with self.assertRaises(TypeError):
            self.installer.install(definition_data())

    def test_builds_native_order_labels_kinds_submenu_and_accelerator(self):
        bar = self.installer.install(self.definition)
        self.assertIs(self.frame.GetMenuBar(), bar)
        self.assertEqual([label for _menu, label in bar.entries], ["&File", "&View"])
        file_items = bar.GetMenu(0).GetMenuItems()
        self.assertEqual(file_items[0].label, "file.open\tCtrl+O")
        self.assertEqual(file_items[1].kind, 3)
        self.assertEqual(file_items[2].label, "E&xit")
        view_items = bar.GetMenu(1).GetMenuItems()
        self.assertEqual(view_items[0].kind, fake_wx.ITEM_CHECK)
        self.assertIsNotNone(view_items[1].submenu)
        self.assertEqual(
            [item.kind for item in view_items[1].submenu.GetMenuItems()],
            [fake_wx.ITEM_RADIO, fake_wx.ITEM_RADIO],
        )

    def test_resolves_all_commands_before_mutating_frame(self):
        data = definition_data()
        data["menus"][0]["items"][0]["command"] = "file.missing"
        definition = MenuDefinitionLoader().from_dict(data)
        previous = FakeMenuBar()
        self.frame.SetMenuBar(previous)
        with self.assertRaisesRegex(MenuInstallationError, "file.missing"):
            self.installer.install(definition)
        self.assertIs(self.frame.GetMenuBar(), previous)
        self.assertEqual(self.frame.bindings, [])

    def test_set_menu_failure_rolls_back_bindings_and_preserves_previous(self):
        previous = FakeMenuBar()
        self.frame.SetMenuBar(previous)
        self.frame.fail_set_menu_bar = True
        with self.assertRaisesRegex(RuntimeError, "cannot install"):
            self.installer.install(self.definition)
        self.frame.fail_set_menu_bar = False
        self.assertIs(self.frame.GetMenuBar(), previous)
        self.assertEqual(self.frame.bindings, [])
        self.assertIsNone(self.installer.menu_bar)

    def test_selection_dispatches_once_with_menu_context(self):
        self.installer.install(self.definition)
        file_item = self.frame.menu_bar.GetMenu(0).GetMenuItems()[0]
        event = FakeEvent()
        self.frame.fire(fake_wx.EVT_MENU, file_item.GetId(), event)
        self.assertEqual(self.calls, [("file.open", "menu", event)])

    def test_explicit_id_is_used_and_generated_ids_do_not_collide(self):
        self.installer.install(self.definition)
        ids = [
            int(item.GetId())
            for menu, _label in self.frame.menu_bar.entries
            for item in menu.GetMenuItems()
            if item.kind != 3
        ]
        self.assertIn(5100, ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_generated_window_id_references_remain_owned_by_installer(self):
        self.installer.install(self.definition)
        generated = [
            node.item.GetId()
            for nodes in self.installer._command_nodes.values()
            for node in nodes
            if node.command_name != "app.exit"
        ]
        self.assertTrue(generated)
        self.assertTrue(all(isinstance(item_id, FakeWindowIDRef) for item_id in generated))

    def test_refresh_applies_enabled_checked_and_visibility(self):
        self.states.values.update({
            "file.open": CommandState(enabled=False),
            "view.status": CommandState(checked=True),
            "view.theme.system": CommandState(visible=False),
        })
        self.installer.install(self.definition)
        file_items = self.frame.menu_bar.GetMenu(0).GetMenuItems()
        self.assertFalse(file_items[0].enabled)
        view_items = self.frame.menu_bar.GetMenu(1).GetMenuItems()
        self.assertTrue(view_items[0].checked)
        theme_items = view_items[1].submenu.GetMenuItems()
        self.assertEqual([item.label for item in theme_items], ["view.theme.light"])

    def test_visibility_removes_redundant_separator_and_empty_top_menu(self):
        self.installer.install(self.definition)
        self.states.values.update({
            "file.open": CommandState(visible=False),
            "app.exit": CommandState(visible=False),
        })
        self.installer.refresh()
        self.assertEqual(
            [label for _menu, label in self.frame.menu_bar.entries], ["&View"]
        )
        self.states.values["app.exit"] = CommandState()
        self.installer.refresh()
        self.assertEqual(
            [label for _menu, label in self.frame.menu_bar.entries], ["&File", "&View"]
        )
        file_items = self.frame.menu_bar.GetMenu(0).GetMenuItems()
        self.assertEqual([item.label for item in file_items], ["E&xit"])

    def test_menu_open_refreshes_state_and_skips_event(self):
        self.installer.install(self.definition)
        self.states.values["file.open"] = CommandState(enabled=False)
        event = FakeEvent()
        self.frame.fire(fake_wx.EVT_MENU_OPEN, event=event)
        self.assertFalse(self.frame.menu_bar.GetMenu(0).GetMenuItems()[0].enabled)
        self.assertTrue(event.skipped)

    def test_context_provider_and_current_form_resolver(self):
        forms = ["first"]
        installer = MenuInstaller(
            self.frame, self.registry,
            context_provider=lambda: CommandContext(
                frame=self.frame, current_form=forms[0], services={"test": True}
            ),
        )
        installer.install(self.definition, current_form=lambda: "ignored")
        item = self.frame.menu_bar.GetMenu(0).GetMenuItems()[0]
        self.frame.fire(fake_wx.EVT_MENU, item.GetId())
        self.assertEqual(self.calls[0][0], "file.open")

    def test_replacement_unbinds_and_destroys_old_owned_bar(self):
        first = self.installer.install(self.definition)
        binding_count = len(self.frame.bindings)
        second = self.installer.install(self.definition)
        self.assertIsNot(first, second)
        self.assertTrue(first.destroyed)
        self.assertEqual(len(self.frame.bindings), binding_count)
        item = second.GetMenu(0).GetMenuItems()[0]
        self.frame.fire(fake_wx.EVT_MENU, item.GetId())
        self.assertEqual(len(self.calls), 1)

    def test_dispose_restores_prior_bar_and_is_idempotent(self):
        previous = FakeMenuBar()
        self.frame.SetMenuBar(previous)
        owned = self.installer.install(self.definition)
        self.assertTrue(self.installer.dispose())
        self.assertIs(self.frame.GetMenuBar(), previous)
        self.assertTrue(owned.destroyed)
        self.assertEqual(self.frame.bindings, [])
        self.assertFalse(self.installer.dispose())


class FakeEditControl:
    def __init__(self):
        self.calls = []
        self.can_paste = False

    def Cut(self): self.calls.append("cut")
    def Copy(self): self.calls.append("copy")
    def Paste(self): self.calls.append("paste")
    def SetSelection(self, start, end): self.calls.append(("selection", start, end))
    def CanCut(self): return True
    def CanCopy(self): return True
    def CanPaste(self): return self.can_paste


class FakeSecurity:
    def __init__(self, denied=()):
        self.denied = set(denied)

    def allows(self, operation):
        return operation not in self.denied


class FakeRecords:
    def __init__(self, current=None):
        self.record = current

    def current(self):
        return self.record


class FakeForm:
    def __init__(self):
        self.calls = []
        self.SECURITY = FakeSecurity()
        self.RECORDS = FakeRecords({"ID": 1})
        self.FORMDESCRIPTON = {"table": {"name": "records"}}

    def new_record(self): self.calls.append("new")
    def save_record(self): self.calls.append("save")
    def delete_record(self): self.calls.append("delete")
    def refresh_records(self): self.calls.append("refresh")


class TestStandardCommandIntegration(unittest.TestCase):
    def test_action_adapter_preserves_command_presentation(self):
        command = ApplicationCommand(
            "record.delete", "&Delete", lambda _context: None,
            wx_id=5009, help_text="Delete record", destructive=True,
        )
        action = action_from_command(command, trailing=True)
        self.assertEqual(action.name, "record.delete")
        self.assertEqual(action.command_name, "record.delete")
        self.assertEqual(action.window_id, 5009)
        self.assertTrue(action.trailing)
        self.assertTrue(action.destructive)

    def test_action_bar_supports_legacy_and_registered_handlers(self):
        calls = []
        current_state = [CommandState()]
        registry = CommandRegistry(error_reporter=lambda *_args, **_kwargs: None)
        registered = ApplicationCommand(
            "tools.run", "&Run", lambda context: calls.append(context.source),
            state_provider=lambda _context: current_state[0],
        )
        registry.register(registered)
        legacy = Action("legacy", "Legacy", lambda _event: calls.append("legacy"))
        bar = StandardActionBar(
            FakePanel(), (legacy, action_from_command(registered)),
            registry=registry,
        )
        bar.buttons["legacy"].click()
        bar.buttons["tools.run"].click()
        self.assertEqual(calls, ["legacy", "action_bar"])
        current_state[0] = CommandState(enabled=False, visible=False)
        states = bar.refresh()
        self.assertFalse(bar.buttons["tools.run"].enabled)
        self.assertFalse(bar.buttons["tools.run"].shown)
        self.assertIn("tools.run", states)

    def test_command_backed_action_requires_registry(self):
        command = ApplicationCommand("tools.run", "Run", lambda _context: None)
        with self.assertRaisesRegex(TypeError, "CommandRegistry"):
            StandardActionBar(FakePanel(), (action_from_command(command),))
        with self.assertRaisesRegex(ValueError, "both"):
            Action(
                "ambiguous", "Ambiguous", lambda _event: None,
                command_name="tools.run",
            )

    def test_standard_application_commands_close_and_about(self):
        calls = []
        commands = standard_application_commands(
            "Sample", application_version="1.0",
            about_handler=lambda context: calls.append(("about", context.frame)),
        )
        registry = CommandRegistry(error_reporter=lambda *_args, **_kwargs: None)
        registry.register_many(commands)
        frame = FakeFrame()
        context = CommandContext(frame=frame)
        registry.dispatch("app.about", context)
        registry.dispatch("app.exit", context)
        self.assertEqual(calls, [("about", frame)])
        self.assertTrue(frame.closed)

    def test_edit_commands_follow_focus_and_capabilities(self):
        control = FakeEditControl()
        FakeWindow.focused = control
        registry = CommandRegistry(error_reporter=lambda *_args, **_kwargs: None)
        registry.register_many(standard_edit_commands())
        self.assertTrue(registry.state("edit.cut").enabled)
        self.assertFalse(registry.state("edit.paste").enabled)
        registry.dispatch("edit.copy")
        registry.dispatch("edit.select_all")
        self.assertEqual(control.calls, ["copy", ("selection", -1, -1)])
        FakeWindow.focused = None
        self.assertFalse(registry.state("edit.copy").enabled)

    def test_record_commands_target_current_form_and_apply_state(self):
        form = FakeForm()
        registry = CommandRegistry(error_reporter=lambda *_args, **_kwargs: None)
        registry.register_many(standard_record_commands())
        context = CommandContext(current_form=form)
        for name in ("record.new", "record.save", "record.delete", "record.refresh"):
            self.assertTrue(registry.state(name, context).enabled)
            registry.dispatch(name, context)
        self.assertEqual(form.calls, ["new", "save", "delete", "refresh"])
        form.SECURITY.denied.add("delete")
        self.assertFalse(registry.state("record.delete", context).enabled)
        form.RECORDS.record = None
        self.assertFalse(registry.state("record.save", context).enabled)

    def test_record_commands_disable_without_current_form(self):
        registry = CommandRegistry(error_reporter=lambda *_args, **_kwargs: None)
        registry.register_many(standard_record_commands())
        for name in registry.names:
            self.assertFalse(registry.state(name).enabled)


if __name__ == "__main__":
    unittest.main()
