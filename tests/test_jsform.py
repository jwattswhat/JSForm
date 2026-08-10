"""Safe tests for JSForm-owned modules and assets."""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
import types
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATIONAL_MODULES = sorted(
    path
    for path in ROOT.glob("*.py")
    if path.name != "run_jsform_tests.py"
)
EXPECTED_PUBLIC_NAMES = {
    "CONST", "CONFIG", "OPTION", "FONT", "LG", "PMON", "clsForm",
    "clsDB", "clsRecord", "clsChoice", "clsErrorHandler", "clsSMTP",
    "clsSQL", "clsField", "getcontrolparameters", "convertNavButtons",
    "charactertopoint", "date_to_datetime", "next_weekday",
    "sql_table_exists", "check_internetconnection", "RunReport",
    "ChildFormRegistry",
    "DatabaseConnections", "DatabaseSettings",
    "OriginalRecord", "RecordState",
    "WriteStatements", "quote_identifier",
    "ControlFactory", "FormDefinitionError", "FormDefinitionLoader", "required_fields",
    "resolve_form_schema",
    "LimeReportProcess", "ReportProcessError",
    "LayoutItem", "build_layout_plan", "apply_responsive_layout",
    "supports_responsive_layout",
    "grouped_controls",
    "layout_spacing",
    "frame_position",
}


class TestResponsiveLayout(unittest.TestCase):
    def test_frame_position_accounts_for_header_and_usable_screen_bounds(self):
        from layout_engine import frame_position

        self.assertEqual(frame_position((0, 0, 1920, 1080), (1000, 900)), (460, 90))
        self.assertEqual(
            frame_position((0, 0, 1920, 1080), (1000, 900), (-50, -40)),
            (8, 8),
        )

    def test_datetime_composite_is_a_real_panel_for_sizer_placement(self):
        tree = ast.parse((ROOT / "clsField.py").read_text(encoding="utf-8-sig"))
        datetime_class = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "clsDateTime"
        )
        bases = [ast.unparse(base) for base in datetime_class.bases]
        calls = [ast.unparse(node.func) for node in ast.walk(datetime_class) if isinstance(node, ast.Call)]
        self.assertIn("wx.Panel", bases)
        self.assertIn("wx.Panel.__init__", calls)

    def test_default_spacing_is_compact_and_overridable(self):
        from layout_engine import layout_spacing

        self.assertEqual(layout_spacing(), (2, 2, 1))
        self.assertEqual(
            layout_spacing({"gap": 4, "border": 6, "item_padding": 2}),
            (4, 6, 2),
        )

    def test_safe_forms_use_responsive_layout_automatically(self):
        from layout_engine import supports_responsive_layout

        form = {"type": "Panel"}
        controls = {
            "label": {"type": "StaticText", "posch": [1, 1]},
            "field": {"type": "TextCtrl", "posch": [10, 1]},
        }
        self.assertTrue(supports_responsive_layout(form, controls))

    def test_overlaps_static_groups_and_opt_out_stay_legacy(self):
        from layout_engine import supports_responsive_layout

        self.assertTrue(supports_responsive_layout(
            {"type": "Panel"},
            {
                "group": {"type": "StaticBox", "posch": [1, 1], "sizech": [20, 10]},
                "field": {"type": "TextCtrl", "posch": [2, 2]},
            },
        ))

    def test_static_box_members_are_identified_by_logical_bounds(self):
        from layout_engine import grouped_controls, supports_responsive_layout

        groups = grouped_controls({
            "group": {"type": "StaticBox", "posch": [1, 1], "sizech": [20, 10]},
            "inside": {"type": "TextCtrl", "posch": [2, 2]},
            "outside": {"type": "TextCtrl", "posch": [30, 2]},
        })
        self.assertEqual(groups, {"group": ["inside"]})
        self.assertFalse(supports_responsive_layout(
            {"type": "Panel"},
            {
                "one": {"type": "TextCtrl", "posch": [1, 1]},
                "two": {"type": "TextCtrl", "posch": [1, 1]},
            },
        ))
        self.assertFalse(supports_responsive_layout(
            {"type": "Panel", "layout": {"type": "legacy"}},
            {"field": {"type": "TextCtrl", "posch": [1, 1]}},
        ))

    def test_character_positions_become_dense_grid_and_navigation_row(self):
        from layout_engine import build_layout_plan

        plan = build_layout_plan({
            "label": {"type": "StaticText", "posch": [1, 1]},
            "field": {"type": "TextCtrl", "posch": [12, 1]},
            "notes": {"type": "MultiLine", "posch": [1, 8]},
            "btnClose": {"type": "Button", "pos": [500, 500]},
        })
        items = {item.name: item for item in plan}
        self.assertEqual((items["label"].row, items["label"].column), (0, 0))
        self.assertEqual((items["field"].row, items["field"].column), (0, 1))
        self.assertTrue(items["field"].expand)
        self.assertEqual(items["btnClose"].row, 2)

    def test_navigation_can_be_excluded_from_the_content_grid(self):
        from layout_engine import build_layout_plan

        plan = build_layout_plan({
            "field": {"type": "TextCtrl", "posch": [1, 1]},
            "btnUpdate": {"type": "Button", "pos": [10, 100]},
            "btnClose": {"type": "Button", "pos": [100, 100]},
        }, include_navigation=False)
        self.assertEqual([item.name for item in plan], ["field"])

    def test_explicit_layout_overrides_character_position(self):
        from layout_engine import build_layout_plan

        item = build_layout_plan({
            "field": {
                "type": "TextCtrl", "posch": [50, 50],
                "layout": {"row": 2, "column": 3, "column_span": 2},
            }
        })[0]
        self.assertEqual((item.row, item.column, item.column_span), (0, 0, 2))


class TestMonitorMetrics(unittest.TestCase):
    def test_missing_physical_size_uses_standard_dpi(self):
        from clsMonitor import monitor_metrics

        monitor = types.SimpleNamespace(
            name="display", is_primary=True, width=1920, height=1080,
            width_mm=None, height_mm=None,
        )
        metrics = monitor_metrics(monitor)
        self.assertEqual(metrics["pixelsperinch"], [96, 96])


class TestReportRuntime(unittest.TestCase):
    def test_report_process_builds_argument_list_and_opens_output(self):
        from report_runtime import LimeReportProcess

        calls = []
        opened = []

        class Process:
            def wait(self):
                return 0

        def popen(command):
            calls.append(command)
            return Process()

        runner = LimeReportProcess(r"C:\Program Files\LimeReport", popen, opened.append)
        runner.generate("template.lrxml", "output.pdf", {"StartDate": "2026/08/10"})
        runner.open_output("output.pdf")

        self.assertIsInstance(calls[0], list)
        self.assertIn("-stemplate.lrxml", calls[0])
        self.assertIn("-pStartDate=2026/08/10", calls[0])
        self.assertEqual(opened, ["output.pdf"])

    def test_report_process_surfaces_nonzero_exit(self):
        from report_runtime import LimeReportProcess, ReportProcessError

        process = types.SimpleNamespace(wait=lambda: 7)
        runner = LimeReportProcess(".", lambda command: process, lambda output: None)
        with self.assertRaisesRegex(ReportProcessError, "status 7"):
            runner.generate("template.lrxml", "output.pdf")


class TestFormServices(unittest.TestCase):
    def test_bundled_unified_schema_wins_over_legacy_configured_copy(self):
        import tempfile
        from form_services import resolve_form_schema

        with tempfile.TemporaryDirectory() as package, tempfile.TemporaryDirectory() as configured:
            package_root = Path(package)
            (package_root / "schema").mkdir()
            canonical = package_root / "schema" / "unified_schema.json"
            canonical.write_text("{}", encoding="utf-8")
            (Path(configured) / "jsformschema.json").write_text("{}", encoding="utf-8")
            self.assertEqual(
                resolve_form_schema(package_root / "__init__.py", configured), canonical
            )

    def test_definition_loader_uses_primary_then_fallback(self):
        import tempfile
        from form_services import FormDefinitionLoader

        with tempfile.TemporaryDirectory() as primary, tempfile.TemporaryDirectory() as fallback:
            path = Path(fallback) / "frmExample.json"
            path.write_text(
                json.dumps({"frmExampleFORM": {"FORM": {"name": "frmExample"}, "CONTROLS": {}}}),
                encoding="utf-8",
            )
            form, controls = FormDefinitionLoader(primary, fallback).load("frmExample")
            self.assertEqual(form["name"], "frmExample")
            self.assertEqual(controls, {})

    def test_required_fields_combines_database_and_control_rules(self):
        from form_services import required_fields

        class Control:
            def __init__(self, value, required=False):
                self.value = value
                self.CONTROLDESCRIPTION = {"required": required}

            def GetValue(self):
                return self.value

        description = {
            "ID": {"null_ok": False},
            "Name": {"null_ok": False},
            "Note": {"null_ok": True},
        }
        controls = {"Name": Control(None), "Note": Control(None, required=True)}
        self.assertEqual(required_fields(description, controls), ["Name", "Note"])


class TestWriteStatements(unittest.TestCase):
    def test_statements_parameterize_values_and_validate_identifiers(self):
        from sql_statements import WriteStatements, quote_identifier

        statements = WriteStatements("tblPerson")
        insert_sql, insert_values = statements.insert(
            {"ID": None, "Name": "O'Brien", "Notes": None}
        )
        self.assertEqual(
            insert_sql, "INSERT INTO `tblPerson` (`Name`) VALUES (%s);"
        )
        self.assertEqual(insert_values, ("O'Brien",))

        update_sql, update_values = statements.update(
            {"ID": 7, "Name": "O'Brien", "Notes": None}
        )
        self.assertIn("`Name`=%s", update_sql)
        self.assertNotIn("O'Brien", update_sql)
        self.assertEqual(update_values, ("O'Brien", None, 7))

        with self.assertRaisesRegex(ValueError, "Unsafe SQL identifier"):
            quote_identifier("tblPerson; DROP TABLE tblPerson")


class TestDatabaseConnections(unittest.TestCase):
    def test_pair_opens_expected_databases_and_closes_both(self):
        from db_connections import DatabaseConnections, DatabaseSettings

        opened = []

        class Connection:
            def __init__(self, arguments):
                self.arguments = arguments
                self.closed = False

            def close(self):
                self.closed = True

        def connect(**arguments):
            connection = Connection(arguments)
            opened.append(connection)
            return connection

        pair = DatabaseConnections(
            DatabaseSettings("server", "ChurchDBTest", "user", "secret"),
            DatabaseSettings("server", "JSFormTest", "user", "secret"),
            connect,
        )
        self.assertEqual([item.arguments["database"] for item in opened], ["ChurchDBTest", "JSFormTest"])
        pair.close()
        self.assertTrue(all(item.closed for item in opened))

    def test_framework_failure_closes_application_connection(self):
        from db_connections import DatabaseConnections, DatabaseSettings

        opened = []

        class Connection:
            closed = False

            def close(self):
                self.closed = True

        def connect(**arguments):
            if arguments["database"] == "JSFormTest":
                raise RuntimeError("framework unavailable")
            connection = Connection()
            opened.append(connection)
            return connection

        with self.assertRaisesRegex(RuntimeError, "framework unavailable"):
            DatabaseConnections(
                DatabaseSettings("server", "ChurchDBTest", "user", "secret"),
                DatabaseSettings("server", "JSFormTest", "user", "secret"),
                connect,
            )
        self.assertTrue(opened[0].closed)


class TestChildFormRegistry(unittest.TestCase):
    def test_registry_is_mapping_compatible_and_close_is_idempotent(self):
        from form_lifecycle import ChildFormRegistry

        class Panel:
            def __init__(self):
                self.closed = 0

            def IsBeingDeleted(self):
                return False

            def Close(self):
                self.closed += 1

        child = types.SimpleNamespace(FORM=Panel())
        registry = ChildFormRegistry()
        registry.update({"frmChild": child})
        self.assertIs(registry["frmChild"], child)

        registry.close_all()
        registry.close_all()

        self.assertEqual(len(registry), 0)
        self.assertEqual(child.FORM.closed, 1)

    def test_registry_discards_deleted_native_window(self):
        from form_lifecycle import ChildFormRegistry

        class DeletedPanel:
            def IsBeingDeleted(self):
                raise RuntimeError("wrapped C/C++ object has been deleted")

        registry = ChildFormRegistry()
        registry["deleted"] = types.SimpleNamespace(FORM=DeletedPanel())
        registry.close_all()
        self.assertEqual(len(registry), 0)


def load_clsdb_with_stubs():
    """Load clsDB without requiring wxPython or a database connection."""
    wx = types.ModuleType("wx")
    wx.Dialog = type("Dialog", (), {})
    wx.ID_OK = 5100
    wx.ID_CANCEL = 5101
    sys.modules.setdefault("wx", wx)

    mysql = types.ModuleType("mysql")
    connector = types.ModuleType("mysql.connector")
    connector.FieldType = type("FieldType", (), {})
    mysql.connector = connector
    sys.modules.setdefault("mysql", mysql)
    sys.modules.setdefault("mysql.connector", connector)

    jsform_stub = types.ModuleType("JSForm")
    jsform_stub.CONST = types.SimpleNamespace(FORM_CANCEL=wx.ID_CANCEL)
    jsform_stub.__path__ = [str(ROOT)]
    sys.modules["JSForm"] = jsform_stub

    spec = importlib.util.spec_from_file_location("_jsform_test_clsdb", ROOT / "clsDB.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class TestJSFormPython(unittest.TestCase):
    def test_database_constraint_errors_have_useful_messages(self):
        module = load_clsdb_with_stubs()

        class DatabaseError(Exception):
            def __init__(self, errno):
                self.errno = errno

        expected = {
            1048: "A required database value is missing.",
            1062: "This record duplicates an existing value.",
            1451: "This record cannot be deleted because other records still use it.",
            1452: "The selected related record no longer exists.",
        }
        for errno, message in expected.items():
            with self.subTest(errno=errno):
                self.assertEqual(
                    module.database_operation_message(DatabaseError(errno), "update"),
                    message,
                )

    def test_unknown_database_error_keeps_operation_context(self):
        module = load_clsdb_with_stubs()
        error = types.SimpleNamespace(errno=9999)
        self.assertEqual(
            module.database_operation_message(error, "update"),
            "Unable to update the database record.",
        )

    def test_operational_modules_compile(self):
        self.assertGreater(len(OPERATIONAL_MODULES), 10)
        for path in OPERATIONAL_MODULES:
            with self.subTest(module=path.name):
                source = path.read_text(encoding="utf-8-sig")
                compile(source, str(path), "exec")

    def test_public_api_exports_expected_names(self):
        tree = ast.parse((ROOT / "__init__.py").read_text(encoding="utf-8"))
        exported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                exported.update(alias.asname or alias.name for alias in node.names)
        self.assertEqual(EXPECTED_PUBLIC_NAMES - exported, set())

    def test_record_navigation_and_dirty_tracking(self):
        module = load_clsdb_with_stubs()
        recordset = module.clsRecord(
            connection=None,
            table={"name": "tblExample", "fields": ["ID", "Name"]},
        )
        recordset._record = [{"ID": 1, "Name": "First"}, {"ID": 2, "Name": "Second"}]
        self.assertEqual(recordset.first()["ID"], 1)
        self.assertEqual(recordset.next()["ID"], 2)
        self.assertEqual(recordset.prev()["ID"], 1)
        recordset.setfieldvalue("Name", "Changed")
        self.assertEqual(recordset.recordisdirty(), ["Name"])
        self.assertEqual(recordset.last()["ID"], 2)


class TestJSFormDefinitions(unittest.TestCase):
    def test_framework_forms_match_canonical_schema(self):
        from jsonschema import validate

        schema = json.loads((ROOT / "schema" / "unified_schema.json").read_text(encoding="utf-8-sig"))
        for path in sorted((ROOT / "Forms").glob("*.json")):
            with self.subTest(form=path.name):
                validate(instance=json.loads(path.read_text(encoding="utf-8-sig")), schema=schema)

    def setUp(self):
        self.form_paths = sorted((ROOT / "Forms").glob("*.json"))

    @staticmethod
    def load_definition(path):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if len(data) != 1:
            raise AssertionError(f"{path.name} must contain exactly one form root")
        return data, next(iter(data.values()))

    def test_all_framework_forms_are_valid_json(self):
        self.assertGreater(len(self.form_paths), 0)
        for path in self.form_paths:
            with self.subTest(form=path.name):
                json.loads(path.read_text(encoding="utf-8-sig"))

    def test_form_roots_and_names_match_filenames(self):
        for path in self.form_paths:
            with self.subTest(form=path.name):
                data, definition = self.load_definition(path)
                root_name = f"{path.stem}FORM"
                self.assertEqual(set(data), {root_name})
                self.assertIn("FORM", definition)
                self.assertIn("CONTROLS", definition)
                self.assertEqual(definition["FORM"].get("name"), path.stem)

    def test_control_names_match_definition_keys(self):
        for path in self.form_paths:
            _, definition = self.load_definition(path)
            controls = definition["CONTROLS"]
            for key, control in controls.items():
                with self.subTest(form=path.name, control=key):
                    self.assertEqual(control.get("name"), key)
                    self.assertIsInstance(control.get("type"), str)

    def test_table_definitions_have_names_and_fields(self):
        for path in self.form_paths:
            _, definition = self.load_definition(path)
            form = definition["FORM"]
            if "table" not in form:
                continue
            with self.subTest(form=path.name):
                self.assertIsInstance(form["table"].get("name"), str)
                self.assertIsInstance(form["table"].get("fields"), list)
                self.assertGreater(len(form["table"]["fields"]), 0)

    def test_schema_files_are_valid_json(self):
        for name in ("jsformschema.json", "schema/unified_schema.json"):
            with self.subTest(schema=name):
                data = json.loads((ROOT / name).read_text(encoding="utf-8-sig"))
                self.assertIsInstance(data, dict)
                self.assertIn("$schema", data)

    def test_lime_report_patterns_are_well_formed_xml(self):
        patterns = sorted((ROOT / "LimeReportPattern").glob("*.lrxml"))
        self.assertGreater(len(patterns), 0)
        for path in patterns:
            with self.subTest(pattern=path.name):
                ET.parse(path)
