"""Safe tests for JSForm-owned modules and assets."""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
import types
import unittest
import xml.etree.ElementTree as ET
from decimal import Decimal
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
    "AllowAllAuthorizationPolicy", "AuthorizationDenied",
    "DenyAllAuthorizationPolicy", "FormSecurity",
    "LimeReportProcess", "ReportProcessError",
    "ReportDefinition", "ReportDefinitionError", "ReportDefinitionLoader",
    "save_report_definition",
    "ReportCollection", "ReportDataset", "ReportDatasetContract",
    "ReportDatasetError", "ReportField",
    "PDFReportRenderer", "ReportRenderError",
    "ReportCanvas", "ReportDesignerFrame", "ReportDesignerModel",
    "open_report_designer",
    "LayoutItem", "build_layout_plan", "apply_responsive_layout",
    "supports_responsive_layout",
    "grouped_controls",
    "layout_spacing",
    "frame_position",
    "master_detail_orientation", "master_detail_panes",
}


class TestChoiceRefresh(unittest.TestCase):
    def test_choice_parser_supports_json_and_preserves_punctuation(self):
        from clsChoice import parse_choice_values

        self.assertEqual(parse_choice_values('["White, Scarlet or Violet","Blue"]'), ["White, Scarlet or Violet", "Blue"])
        self.assertEqual(parse_choice_values("[First\rSecond\rFirst]"), ["First", "Second"])

    def test_choice_editor_normalizes_blanks_and_duplicates(self):
        from choice_manager import normalized_choices

        self.assertEqual(normalized_choices([" General ", "", "general", "Special"]), ["General", "Special"])
        with self.assertRaises(ValueError):
            normalized_choices(["", "  "])

    def test_typed_value_outside_suggestion_list_is_preserved(self):
        from clsChoice import clsChoice

        choices = object.__new__(clsChoice)
        choices.id = []
        choices.display = ["55604", "55612", "55616"]
        self.assertEqual(choices.getchoiceid("99999"), "99999")

    def test_lookup_refresh_replaces_stale_mappings(self):
        from clsChoice import clsChoice

        choices = object.__new__(clsChoice)
        choices.controldescription = {
            "name": "HymnID",
            "lookupchoices": {"name": "tblHymn", "fields": ["ID", "Title"]},
        }
        choices.id = [1]
        choices.display = ["Old hymn"]
        choices.fielddata = [["Old hymn"]]
        choices._loadfromchoicestable = lambda: None

        def load_current():
            choices._addchoiceanddata(2, "Current hymn", ["Current hymn"])
            return choices.display

        choices._loadchoicesfromtable = load_current

        self.assertEqual(choices.load_choices(choices.controldescription), ["Current hymn"])
        self.assertEqual(choices.id, [2])
        self.assertEqual(choices.fielddata, [["Current hymn"]])

    def test_lookup_can_offer_an_explicit_sql_null_choice(self):
        import JSForm
        from clsChoice import clsChoice

        class Cursor:
            def execute(self, _sql, _values=()): pass
            def fetchone(self): return None
            def fetchall(self): return [(3, "LSB")]
            def close(self): pass

        class Connection:
            def cursor(self): return Cursor()

        original_sql = JSForm.clsSQL
        JSForm.clsSQL = lambda *_args: type("SQL", (), {"select": lambda self: "SELECT"})()
        try:
            choices = clsChoice(
                Connection(),
                {
                    "name": "HymnalID",
                    "lookupchoices": {
                        "name": "tblHymnal", "fields": ["ID", "Hymnal"],
                        "allowblank": True, "blanklabel": "No primary hymnal",
                    },
                },
            )
            self.assertEqual(
                choices.load_choices(choices.controldescription),
                ["No primary hymnal", "LSB"],
            )
            self.assertEqual(choices.getchoiceid("No primary hymnal"), None)
        finally:
            JSForm.clsSQL = original_sql

    def test_literal_filter_can_offer_all_without_storing_the_label(self):
        from clsChoice import clsChoice

        choices = clsChoice(
            None,
            {
                "name": "TripType", "choices": ["Morning", "Afternoon"],
                "allowall": True, "alllabel": "All trips",
            },
        )
        self.assertEqual(
            choices.load_choices(choices.controldescription),
            ["All trips", "Morning", "Afternoon"],
        )
        self.assertIsNone(choices.getchoiceid("All trips"))
        self.assertEqual(choices.getchoiceid("Morning"), "Morning")

    def test_lookup_filter_can_offer_all_without_storing_the_label(self):
        import JSForm
        from clsChoice import clsChoice

        class Cursor:
            def execute(self, _sql, _values=()): pass
            def fetchone(self): return None
            def fetchall(self): return [(3, "LSB")]
            def close(self): pass

        class Connection:
            def cursor(self): return Cursor()

        original_sql = JSForm.clsSQL
        JSForm.clsSQL = lambda *_args: type("SQL", (), {"select": lambda self: "SELECT"})()
        try:
            choices = clsChoice(
                Connection(),
                {
                    "name": "HymnalID",
                    "lookupchoices": {
                        "name": "tblHymnal", "fields": ["ID", "Hymnal"],
                        "allowall": True,
                    },
                },
            )
            self.assertEqual(choices.load_choices(choices.controldescription), ["All", "LSB"])
            self.assertIsNone(choices.getchoiceid("All"))
            self.assertEqual(choices.getchoiceid("LSB"), 3)
        finally:
            JSForm.clsSQL = original_sql

    def test_lookup_works_without_optional_choices_table(self):
        import JSForm
        from clsChoice import clsChoice

        class MissingTableError(Exception):
            errno = 1146

        class Cursor:
            def execute(self, sql, _values=()):
                if "tblChoices" in sql:
                    raise MissingTableError()
            def fetchall(self): return [(7, "Pine Valley Elementary")]
            def close(self): pass

        class Connection:
            def cursor(self): return Cursor()

        original_sql = JSForm.clsSQL
        JSForm.clsSQL = lambda *_args: type("SQL", (), {"select": lambda self: "SELECT"})()
        try:
            choices = clsChoice(
                Connection(),
                {
                    "name": "SchoolID",
                    "lookupchoices": {
                        "name": "sb_school", "fields": ["ID", "Name"],
                    },
                },
            )
            self.assertEqual(
                choices.load_choices(choices.controldescription),
                ["Pine Valley Elementary"],
            )
            self.assertEqual(choices.getchoiceid("Pine Valley Elementary"), 7)
        finally:
            JSForm.clsSQL = original_sql


class TestControlValues(unittest.TestCase):
    def test_multiline_preserves_strings_and_joins_sequences(self):
        from control_values import multiline_text

        self.assertEqual(multiline_text("one\ntwo"), "one\ntwo")
        self.assertEqual(multiline_text(["one", 2]), "one\r\n2")
        self.assertEqual(multiline_text(None), "")

    def test_phone_values_have_separate_display_and_storage_forms(self):
        from control_values import phone_display, phone_storage

        self.assertEqual(phone_display("9999999999"), "(999) 999-9999")
        self.assertEqual(phone_display("(999) 999-9999"), "(999) 999-9999")
        self.assertEqual(phone_storage("(999) 999-9999"), "9999999999")
        self.assertIsNone(phone_storage(""))
        self.assertEqual(phone_display("+44 20 7946 0958"), "+44 20 7946 0958")
        self.assertEqual(phone_storage("+44 20 7946 0958"), "+44 20 7946 0958")

    def test_configured_font_uses_portable_positional_constructor(self):
        from unittest.mock import patch
        from clsFont import clsFont

        configured = type("Config", (), {"get_Config_Family": lambda _self, _name: (
            ("PointSize", "10"), ("Family", "70"), ("Style", "90"),
            ("Weight", "90"), ("Face", "Segoe UI"), ("Underline", "1"),
        )})()
        with patch("clsFont.JSForm.CONFIG", configured), patch("clsFont.wx.Font") as font:
            instance = object.__new__(clsFont)
            instance.fontdict = {}
            instance._currentfont = None
            instance.Get_Config_Font()
        font.assert_called_once_with(10, 70, 90, 90, True, "Segoe UI")

    def test_numeric_types_preserve_null_and_return_python_numbers(self):
        from control_values import number_value

        self.assertIsNone(number_value(""))
        self.assertEqual(number_value("1,234"), 1234)
        self.assertEqual(number_value('"1"'), 1)
        self.assertEqual(number_value("'2'"), 2)
        self.assertEqual(number_value("12.50"), Decimal("12.50"))
        self.assertEqual(number_value("$1,234.50", "currency"), Decimal("1234.50"))
        self.assertEqual(number_value("1.25", "float"), 1.25)

    def test_sql_record_formatter_preserves_standard_numeric_types(self):
        from clsSQL import clsSQL

        formatter = object.__new__(clsSQL)
        for field_type, value in (
            ("SHORT", 1), ("LONG", 2), ("LONGLONG", 3),
            ("INT24", 4), ("YEAR", 2027), ("FLOAT", 1.5), ("DOUBLE", 2.5),
        ):
            with self.subTest(field_type=field_type):
                formatter.sqldescription = {"Value": {"type": field_type}}
                self.assertEqual(formatter._format_for_record("Value", value), value)

    def test_json_is_validated_and_normalized(self):
        from control_values import normalized_json

        self.assertIsNone(normalized_json(None))
        self.assertEqual(normalized_json({"enabled": True}), '{"enabled":true}')
        self.assertEqual(normalized_json('{ "items": [1, 2] }'), '{"items":[1,2]}')
        with self.assertRaises(json.JSONDecodeError):
            normalized_json("not JSON")

    def test_boolean_and_scalar_list_normalization(self):
        from control_values import checked_value, checklist_state, value_sequence

        for value in (True, 1, "1", "true", "YES", "on"):
            self.assertTrue(checked_value(value))
        for value in (False, 0, None, "false", "no"):
            self.assertFalse(checked_value(value))
        self.assertEqual(value_sequence("single"), ["single"])
        self.assertEqual(value_sequence(None), [])
        self.assertEqual(value_sequence("[1\r3\r2\r4]"), ["1", "3", "2", "4"])
        self.assertEqual(value_sequence("[Sunday]"), ["Sunday"])
        self.assertEqual(value_sequence("1;3"), ["1", "3"])
        self.assertEqual(value_sequence('["A", "B"]'), ["A", "B"])
        self.assertEqual(
            checklist_state(None, ["Bulletin", "Hymns"]),
            {"Bulletin": False, "Hymns": False},
        )
        self.assertEqual(
            checklist_state('{"Bulletin":"True","One-time task":true}', ["Bulletin", "Hymns"]),
            {"Bulletin": True, "Hymns": False, "One-time task": True},
        )

    def test_date_time_inputs_accept_native_database_values(self):
        import datetime
        from control_values import (
            datetime_value,
            native_date,
            native_datetime,
            native_time,
        )

        date = datetime.date(2026, 8, 10)
        time = datetime.time(13, 45)
        delta = datetime.timedelta(hours=9, minutes=30)
        self.assertEqual(datetime_value(date, "%Y-%m-%d", "date").date(), date)
        self.assertEqual(datetime_value(time, "%H:%M", "time").time(), time)
        self.assertEqual(datetime_value(delta, "%H:%M", "time").time(), datetime.time(9, 30))
        self.assertEqual(
            datetime_value("2026-08-10", "%Y-%m-%d", "date").date(), date
        )
        self.assertEqual(native_date(date), date)
        self.assertEqual(native_date("08/10/2026", "%m/%d/%Y"), date)
        self.assertEqual(native_time(time), datetime.timedelta(hours=13, minutes=45))
        self.assertEqual(native_time(delta), delta)
        self.assertEqual(native_time(datetime.time()), datetime.timedelta(0))
        stamp = datetime.datetime(2026, 8, 10, 13, 45)
        self.assertEqual(native_datetime(stamp), stamp)
        self.assertEqual(
            native_datetime("08/10/2026 01:45 PM", "%m/%d/%Y %I:%M %p"), stamp
        )
        for converter in (native_date, native_time, native_datetime):
            self.assertIsNone(converter(None))
            self.assertIsNone(converter(""))

    def test_sql_record_formatter_preserves_native_temporal_types(self):
        import datetime
        from clsSQL import clsSQL

        formatter = object.__new__(clsSQL)
        values = {
            "DATE": datetime.date(2027, 1, 1),
            "TIME": datetime.timedelta(hours=9, minutes=30),
            "DATETIME": datetime.datetime(2027, 1, 1, 9, 30),
        }
        for field_type, value in values.items():
            with self.subTest(field_type=field_type):
                formatter.sqldescription = {"Value": {"type": field_type}}
                self.assertIs(formatter._format_for_record("Value", value), value)

    def test_sql_record_formatter_preserves_binary_blobs(self):
        from clsSQL import clsSQL

        formatter = object.__new__(clsSQL)
        formatter.sqldescription = {"Value": {"type": "BLOB"}}
        value = b"\x89PNG\r\n\x1a\n"
        self.assertIs(formatter._format_for_record("Value", value), value)
        self.assertEqual(formatter._format_for_record("Value", "plain text"), "plain text")


class TestControlCatalog(unittest.TestCase):
    def test_data_view_constructor_does_not_receive_json_field_name(self):
        import clsConstant

        self.assertNotIn(
            "name", clsConstant.CONST.wxpythoncallparmameters["DataViewListCtrl"]
        )

    def test_both_schemas_accept_security_declarations(self):
        from jsonschema import validate

        definition = {
            "frmSecureFORM": {
                "FORM": {
                    "name": "frmSecure", "type": "Panel", "title": "Secure",
                    "posch": [1, 1], "sizech": [20, 10],
                    "security": {"open": "people.records.view"},
                },
                "CONTROLS": {
                    "Name": {
                        "type": "TextCtrl", "name": "Name", "posch": [1, 1],
                        "security": {
                            "view": "people.records.view",
                            "edit": "people.records.edit",
                        },
                    }
                },
            }
        }
        for schema_path in (
            ROOT / "schema" / "unified_schema.json", ROOT / "jsformschema.json"
        ):
            validate(definition, json.loads(schema_path.read_text()))

    def test_schema_rejects_malformed_permission_name(self):
        from jsonschema import ValidationError, validate

        definition = {
            "frmSecureFORM": {
                "FORM": {
                    "name": "frmSecure", "type": "Panel", "title": "Secure",
                    "posch": [1, 1], "sizech": [20, 10],
                    "security": {"open": "Not A Permission"},
                },
                "CONTROLS": {},
            }
        }
        with self.assertRaises(ValidationError):
            validate(
                definition,
                json.loads((ROOT / "schema" / "unified_schema.json").read_text()),
            )

    def test_factory_metadata_and_schemas_advertise_the_same_controls(self):
        tree = ast.parse((ROOT / "clsField.py").read_text(encoding="utf-8-sig"))
        field_class = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "clsField"
        )
        constructor = next(
            node for node in field_class.body
            if isinstance(node, ast.FunctionDef) and node.name == "__init__"
        )
        factory_types = {
            case.pattern.value.value
            for node in ast.walk(constructor)
            if isinstance(node, ast.Match)
            for case in node.cases
            if isinstance(case.pattern, ast.MatchValue)
            and isinstance(case.pattern.value, ast.Constant)
        }

        constants_tree = ast.parse((ROOT / "clsConstant.py").read_text(encoding="utf-8-sig"))
        constants_class = next(
            node for node in constants_tree.body
            if isinstance(node, ast.ClassDef) and node.name == "clsConstantsNameSpace"
        )
        parameter_assignment = next(
            node for node in constants_class.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "wxpythoncallparmameters" for target in node.targets)
        )
        metadata_types = set(ast.literal_eval(parameter_assignment.value))
        metadata_types -= {"Dialog", "Frame", "Panel", "navButton"}

        canonical = json.loads((ROOT / "schema" / "unified_schema.json").read_text())
        canonical_form = next(iter(canonical["patternProperties"].values()))
        schema_types = set(
            canonical_form["properties"]["CONTROLS"]
            ["patternProperties"][".*"]["properties"]["type"]["enum"]
        )
        legacy = json.loads((ROOT / "jsformschema.json").read_text())
        legacy_form = next(iter(legacy["patternProperties"].values()))
        legacy_types = set(
            legacy_form["properties"]["CONTROLS"]
            ["patternProperties"][".*"]["properties"]["type"]["enum"]
        )

        self.assertEqual(factory_types, metadata_types)
        self.assertEqual(factory_types, schema_types)
        self.assertEqual(factory_types, legacy_types)
        self.assertIn("CalendarCtrl", factory_types)
        self.assertIn("JSON", factory_types)
        self.assertIn("ImagePickerCtrl", factory_types)

    def test_image_picker_uses_binary_values_and_database_safe_metadata(self):
        source = (ROOT / "clsField.py").read_text(encoding="utf-8-sig")
        self.assertIn("class clsImagePickerCtrl(wx.Panel, clsFieldExtra)", source)
        self.assertIn("return bytes(value)", source)
        self.assertIn("path.read_bytes()", source)
        self.assertNotIn("path.read_text()", source)
        self.assertIn('self._show_placeholder("Image unavailable")', source)
        self.assertNotIn("self._value = None\n                self._show_placeholder()", source)
        self.assertIn('get("allowupscale", False)', source)
        self.assertIn('get("maxpixels", 20_000_000)', source)
        for path in (ROOT / "schema" / "unified_schema.json", ROOT / "jsformschema.json"):
            schema = json.loads(path.read_text(encoding="utf-8-sig"))
            text = json.dumps(schema)
            self.assertIn('"ImagePickerCtrl"', text)
            self.assertIn('"maxbytes"', text)
            self.assertIn('"maxpixels"', text)
            self.assertIn('"allowupscale"', text)

    def test_id_list_catalog_support_is_kept_in_code_and_both_schemas(self):
        source = (ROOT / "clsField.py").read_text(encoding="utf-8-sig")
        form_source = (ROOT / "clsForm.py").read_text(encoding="utf-8-sig")
        self.assertIn("def SetCatalogRows(self, rows):", source)
        self.assertIn("wx.LC_SINGLE_SEL", source)
        self.assertIn("wx.EVT_LIST_ITEM_SELECTED", form_source)
        for path in (ROOT / "schema" / "unified_schema.json", ROOT / "jsformschema.json"):
            schema = json.loads(path.read_text(encoding="utf-8-sig"))
            text = json.dumps(schema)
            self.assertIn('"singleselect"', text)

    def test_data_grid_accepts_legacy_pixel_and_character_column_widths(self):
        source = (ROOT / "clsField.py").read_text(encoding="utf-8-sig")
        self.assertIn('if "widthch" in column', source)
        self.assertIn('column.get("width", 100)', source)

    def test_both_schemas_allow_nonempty_tooltips(self):
        for schema_path in (
            ROOT / "schema" / "unified_schema.json",
            ROOT / "jsformschema.json",
        ):
            schema = json.loads(schema_path.read_text())
            form_schema = next(iter(schema["patternProperties"].values()))
            tooltip = (
                form_schema["properties"]["CONTROLS"]["patternProperties"][".*"]
                ["properties"]["tooltip"]
            )
            self.assertEqual(tooltip["type"], "string")
            self.assertEqual(tooltip["minLength"], 1)

    def test_control_factory_applies_tooltip_after_construction(self):
        tree = ast.parse((ROOT / "clsField.py").read_text(encoding="utf-8-sig"))
        source = ast.unparse(tree)
        self.assertIn("tooltip = controldescription.get('tooltip')", source)
        self.assertIn("self.FIELD.SetToolTip(str(tooltip))", source)

    def test_text_controls_support_field_specific_maximum_length(self):
        source = (ROOT / "clsField.py").read_text(encoding="utf-8-sig")
        self.assertIn('self.CONTROLDESCRIPTION.get("maxlength")', source)
        self.assertIn("self.SetMaxLength(int(maximum))", source)
        self.assertIn("wx.EVT_TEXT_MAXLEN", source)
        for path in (ROOT / "schema" / "unified_schema.json", ROOT / "jsformschema.json"):
            schema = json.loads(path.read_text(encoding="utf-8-sig"))
            text = json.dumps(schema)
            self.assertIn('"maxlength"', text)
            self.assertIn('"maxlengthmessage"', text)


class TestResponsiveLayout(unittest.TestCase):
    def test_master_detail_reflows_at_configured_breakpoint(self):
        from layout_engine import master_detail_orientation

        settings = {"breakpoint": 800}
        self.assertEqual(master_detail_orientation(1200, settings), "horizontal")
        self.assertEqual(master_detail_orientation(799, settings), "vertical")

    def test_master_detail_partitions_controls_and_inherits_group_pane(self):
        from layout_engine import master_detail_panes

        descriptions = {
            "masterBox": {
                "type": "StaticBox", "posch": [1, 1], "sizech": [20, 10],
                "layout": {"pane": "master"},
            },
            "memberList": {"type": "ListCtrlID", "posch": [2, 2]},
            "Name": {
                "type": "TextCtrl", "posch": [30, 2],
                "layout": {"pane": "detail"},
            },
            "btnClose": {"type": "Button", "posch": [1, 20]},
        }
        panes = master_detail_panes(descriptions)
        self.assertEqual(set(panes["master"]), {"masterBox", "memberList"})
        self.assertEqual(set(panes["detail"]), {"Name"})

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

    def test_nullable_time_picker_does_not_call_unsupported_null_text_api(self):
        tree = ast.parse((ROOT / "clsField.py").read_text(encoding="utf-8-sig"))
        time_class = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "clsTimePickerCtrl"
        )
        calls = [
            ast.unparse(node.func) for node in ast.walk(time_class)
            if isinstance(node, ast.Call)
        ]
        self.assertNotIn("super().SetNullText", calls)

    def test_datetime_composite_uses_child_specific_formats(self):
        source = (ROOT / "clsField.py").read_text(encoding="utf-8-sig")
        self.assertIn('get_Config_Value("Format", "Date")', source)
        self.assertIn('get_Config_Value("Format", "Time")', source)
        self.assertNotIn("self.datefield.SetValue(value, dtfmt)", source)

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

    def test_partial_explicit_layout_does_not_mix_positioning_systems(self):
        from layout_engine import build_layout_plan

        plan = build_layout_plan({
            "first": {
                "type": "StaticBox", "posch": [1, 10],
                "layout": {"row": 0, "column": 0},
            },
            "second": {"type": "StaticBox", "posch": [20, 1]},
        }, include_navigation=False)
        items = {item.name: item for item in plan}
        self.assertEqual((items["first"].row, items["first"].column), (1, 0))
        self.assertEqual((items["second"].row, items["second"].column), (0, 1))

    def test_forms_reset_initial_scroll_after_show(self):
        source = (ROOT / "clsForm.py").read_text(encoding="utf-8")
        self.assertIn("wx.CallAfter(self._reset_initial_scroll)", source)
        self.assertIn("self.FORM.Scroll(0, 0)", source)


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
        import datetime
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

        temporal = {
            "ID": 8,
            "Date": datetime.date(2027, 1, 1),
            "Time": datetime.timedelta(hours=9, minutes=30),
            "DateTime": datetime.datetime(2027, 1, 1, 9, 30),
        }
        _, temporal_values = statements.update(temporal)
        self.assertEqual(temporal_values, tuple(temporal.values())[1:] + (8,))

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

    def test_temporal_dirty_tracking_compares_native_values_semantically(self):
        import datetime
        from record_state import RecordState

        recordset = RecordState()
        recordset.add(
            {
                "Date": datetime.date(2027, 1, 1),
                "Time": datetime.timedelta(hours=9, minutes=30),
                "DateTime": datetime.datetime(2027, 1, 1, 9, 30),
            }
        )
        recordset.first()
        recordset.setfieldvalue("Time", datetime.time(9, 30))
        self.assertEqual(recordset.recordisdirty(), [])
        recordset.setfieldvalue("Time", datetime.time(9, 31))
        self.assertEqual(recordset.recordisdirty(), ["Time"])

    def test_dirty_tracking_normalizes_supported_scalar_and_collection_values(self):
        import datetime
        from decimal import Decimal
        from record_state import RecordState

        recordset = RecordState()
        recordset.add({
            "Blank": None,
            "Amount": Decimal("25.00"),
            "Checked": 1,
            "Choices": ["A", "B"],
            "Settings": {"enabled": True, "count": 2},
            "Time": datetime.timedelta(hours=10),
        })
        recordset.first()
        recordset.setfieldvalue("Blank", "")
        recordset.setfieldvalue("Amount", 25)
        recordset.setfieldvalue("Checked", True)
        recordset.setfieldvalue("Choices", ("A", "B"))
        recordset.setfieldvalue("Settings", {"count": Decimal("2.0"), "enabled": 1})
        recordset.setfieldvalue("Time", datetime.time(10, 0))
        self.assertEqual(recordset.recordisdirty(), [])

        recordset.setfieldvalue("Amount", Decimal("25.01"))
        self.assertEqual(recordset.recordisdirty(), ["Amount"])

    def test_form_baseline_uses_loaded_control_values_not_raw_database_values(self):
        import types
        from record_state import RecordState
        from JSForm.clsForm import clsForm

        recordset = RecordState()
        recordset.add({"ID": 1, "Choice": "[1\r2]", "Date": "2027-01-01"})
        recordset.first()
        form = types.SimpleNamespace(
            RECORDS=recordset,
            CONTROLID={
                "Choice": types.SimpleNamespace(GetValue=lambda: ["1", "2"]),
                "Date": types.SimpleNamespace(GetValue=lambda: "01/01/2027"),
            },
        )
        clsForm._save_control_value_baseline(form, recordset.current())
        recordset.setfieldvalue("Choice", ["1", "2"])
        recordset.setfieldvalue("Date", "01/01/2027")
        self.assertEqual(recordset.recordisdirty(), [])
        recordset.setfieldvalue("Choice", ["1", "3"])
        self.assertEqual(recordset.recordisdirty(), ["Choice"])


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

    def test_any_legacy_lime_report_patterns_are_well_formed_xml(self):
        patterns = sorted((ROOT / "LimeReportPattern").glob("*.lrxml"))
        for path in patterns:
            with self.subTest(pattern=path.name):
                ET.parse(path)
