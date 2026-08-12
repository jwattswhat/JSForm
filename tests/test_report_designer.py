from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from report_definition import ReportDefinitionLoader
from report_designer import ReportDesignerModel, export_preview_file
from test_report_definition import valid_definition


class TestReportDesignerModel(unittest.TestCase):
    def test_system_report_value_can_be_added_and_edited(self):
        model = self.model()
        name = model.add_control("systemtext", band=next(iter(model.report["bands"])))
        model.set_property(name, "systemvalue", "page_number")
        model.set_property(name, "prefix", "Page ")
        self.assertEqual(model.controls[name]["systemvalue"], "page_number")
        self.assertEqual(model.controls[name]["prefix"], "Page ")

    def test_table_column_heading_width_format_and_alignment_are_editable(self):
        source = valid_definition()
        source["CMMD01REPORT"]["CONTROLS"]["FamilyName"] = {
            "type": "table", "band": "Detail", "position": [0, 0], "size": [500, 36],
            "repeatcollection": "families",
            "columns": [{
                "name": "FamilyName", "label": "Family", "collection": "families",
                "field": "FamilyName", "width": 200,
            }],
        }
        model = ReportDesignerModel(ReportDefinitionLoader().from_dict(source))
        model.set_table_column(
            "FamilyName", "FamilyName", label="Household", width=240,
            format_name="text", align="right",
        )
        column = model.controls["FamilyName"]["columns"][0]
        self.assertEqual(column["label"], "Household")
        self.assertEqual(column["width"], 240)
        self.assertEqual(column["align"], "right")

    def model(self):
        return ReportDesignerModel(ReportDefinitionLoader().from_dict(valid_definition()))

    def test_move_and_resize_change_familiar_jsform_properties(self):
        model = self.model()
        model.move("FamilyName", 12, 5)
        model.resize("FamilyName", -20, 4)
        self.assertEqual(model.controls["FamilyName"]["position"], [12, 5])
        self.assertEqual(model.controls["FamilyName"]["size"], [180, 22])
        self.assertTrue(model.dirty)

    def test_controls_are_kept_within_page_and_band(self):
        model = self.model()
        model.move("FamilyName", -1000, -1000)
        self.assertEqual(model.controls["FamilyName"]["position"], [0, 0])
        model.move("FamilyName", 10000, 10000)
        x, y = model.controls["FamilyName"]["position"]
        self.assertLessEqual(x + model.controls["FamilyName"]["size"][0], model.content_width)
        self.assertLessEqual(y + model.controls["FamilyName"]["size"][1], 72)

    def test_save_revalidates_and_reopens(self):
        model = self.model()
        model.move("FamilyName", 5, 3)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "report.json"
            saved = model.save(path)
            reopened = ReportDefinitionLoader().load(path)
            self.assertEqual(saved.to_dict(), reopened.to_dict())
            self.assertFalse(model.dirty)

    def test_properties_are_validated_before_the_model_changes(self):
        model = self.model()
        model.set_property("FamilyName", "label", "Household name")
        self.assertEqual(model.controls["FamilyName"]["label"], "Household name")
        with self.assertRaises(ValueError):
            model.set_property("FamilyName", "color", "blue")
        self.assertNotIn("color", model.controls["FamilyName"])

    def test_direct_geometry_edits_remain_inside_the_band(self):
        model = self.model()
        model.set_geometry("FamilyName", position=[10000, 10000], size=[10000, 10000])
        control = model.controls["FamilyName"]
        self.assertLessEqual(control["position"][0] + control["size"][0], model.content_width)
        self.assertLessEqual(control["position"][1] + control["size"][1], 72)

    def test_add_control_uses_unique_names_and_valid_definition(self):
        model = self.model()
        first = model.add_control("label", band="Detail")
        second = model.add_control("label", band="Detail")
        self.assertEqual((first, second), ("Label", "Label2"))
        self.assertEqual(model.controls[first]["label"], "New label")
        model.validated_definition()

    def test_delete_control_removes_selection(self):
        model = self.model()
        name = model.add_control("rectangle", band="Detail")
        model.delete_control(name)
        self.assertNotIn(name, model.controls)
        self.assertIsNone(model.selected)

    def test_add_bound_field_uses_contract_compatible_properties(self):
        model = self.model()
        name = model.add_bound_field("families", "FamilyName", "Family Name", band="Detail")
        control = model.controls[name]
        self.assertEqual(control["type"], "text")
        self.assertEqual((control["collection"], control["field"]), ("families", "FamilyName"))
        model.validated_definition()

    def test_add_bound_image_creates_image_control(self):
        model = self.model()
        name = model.add_bound_field("families", "Image", "Family Image", "image", "Detail")
        self.assertEqual(model.controls[name]["type"], "image")

    def test_replace_definition_restores_content_and_marks_dirty(self):
        model = self.model()
        model.add_control("label", band="Detail")
        starter = ReportDefinitionLoader().from_dict(valid_definition())
        model.replace_definition(starter)
        self.assertNotIn("Label", model.controls)
        self.assertEqual(model.selected, "FamilyName")
        self.assertTrue(model.dirty)

    def test_undo_and_redo_restore_geometry(self):
        model = self.model()
        original = list(model.controls["FamilyName"]["position"])
        model.move("FamilyName", 12, 5)
        changed = list(model.controls["FamilyName"]["position"])
        self.assertTrue(model.undo())
        self.assertEqual(model.controls["FamilyName"]["position"], original)
        self.assertTrue(model.redo())
        self.assertEqual(model.controls["FamilyName"]["position"], changed)

    def test_drag_transaction_is_one_undoable_change(self):
        model = self.model()
        original = list(model.controls["FamilyName"]["position"])
        model.begin_transaction()
        model.move("FamilyName", 2, 1)
        model.move("FamilyName", 3, 2)
        model.end_transaction()
        self.assertEqual(len(model.undo_stack), 1)
        model.undo()
        self.assertEqual(model.controls["FamilyName"]["position"], original)

    def test_snap_to_grid_rounds_position_and_is_undoable(self):
        model = self.model()
        model.set_geometry("FamilyName", position=[13, 10])
        model.snap_to_grid("FamilyName", 6)
        self.assertEqual(model.controls["FamilyName"]["position"], [12, 12])
        model.undo()
        self.assertEqual(model.controls["FamilyName"]["position"], [13, 10])

    def test_layout_validation_reports_overlaps(self):
        model = self.model()
        model.add_control("label", band="Detail", name="FirstLabel")
        model.add_control("label", band="Detail", name="SecondLabel")
        warnings = model.layout_warnings()
        self.assertIn("FirstLabel overlaps SecondLabel", warnings)

    def test_layout_validation_accepts_separated_controls(self):
        model = self.model()
        model.delete_control("FamilyName")
        model.add_control("label", band="Detail", name="FirstLabel")
        model.add_control("label", band="Detail", name="SecondLabel")
        model.set_geometry("SecondLabel", position=[200, 40])
        self.assertEqual(model.layout_warnings(), [])

    def test_align_controls_left_is_undoable(self):
        model = self.model()
        model.delete_control("FamilyName")
        first = model.add_control("label", band="Detail", name="FirstLabel")
        second = model.add_control("label", band="Detail", name="SecondLabel")
        model.set_geometry(first, position=[20, 4])
        model.set_geometry(second, position=[80, 40])
        model.align_controls([first, second], "left")
        self.assertEqual(model.controls[second]["position"][0], 20)
        model.undo()
        self.assertEqual(model.controls[second]["position"][0], 80)

    def test_align_controls_requires_same_band(self):
        model = self.model()
        model.add_control("label", band="Detail", name="DetailLabel")
        model.report["bands"]["Header"] = {"type": "reportheader", "height": 40}
        model.add_control("label", band="Header", name="HeaderLabel")
        with self.assertRaisesRegex(ValueError, "same report section"):
            model.align_controls(["DetailLabel", "HeaderLabel"], "top")

    def test_distribute_controls_evenly_across(self):
        model = self.model()
        model.delete_control("FamilyName")
        names = [model.add_control("label", band="Detail", name=f"Label{number}") for number in range(3)]
        for name, x in zip(names, (0, 100, 300)):
            model.set_geometry(name, position=[x, 4], size=[20, 10])
        model.distribute_controls(names, "horizontal")
        self.assertEqual([model.controls[name]["position"][0] for name in names], [0, 150, 300])

    def test_distribute_controls_requires_three(self):
        model = self.model()
        with self.assertRaisesRegex(ValueError, "at least three"):
            model.distribute_controls(["FamilyName"], "vertical")

    def test_band_height_can_expand_and_undo(self):
        model = self.model()
        original = model.report["bands"]["Detail"]["height"]
        model.set_band_height("Detail", 200)
        self.assertEqual(model.report["bands"]["Detail"]["height"], 200)
        model.undo()
        self.assertEqual(model.report["bands"]["Detail"]["height"], original)

    def test_band_cannot_shrink_over_a_control(self):
        model = self.model()
        with self.assertRaisesRegex(ValueError, "must be at least"):
            model.set_band_height("Detail", 5)

    def test_repeater_item_width_can_be_changed_and_undone(self):
        source = valid_definition()
        source["CMMD01REPORT"]["CONTROLS"]["FamilyName"] = {
            "type": "repeater", "band": "Detail", "position": [0, 0], "size": [500, 60],
            "repeatcollection": "families", "itemheight": 60,
            "items": [{"name": "Name", "field": "FamilyName", "position": [0, 0], "size": [200, 20]}],
        }
        model = ReportDesignerModel(ReportDefinitionLoader().from_dict(source))
        model.set_repeater_item_geometry("FamilyName", "Name", size=[250, 20])
        self.assertEqual(model.controls["FamilyName"]["items"][0]["size"][0], 250)
        model.undo()
        self.assertEqual(model.controls["FamilyName"]["items"][0]["size"][0], 200)

    def test_repeater_item_cannot_extend_past_row(self):
        source = valid_definition()
        source["CMMD01REPORT"]["CONTROLS"]["FamilyName"] = {
            "type": "repeater", "band": "Detail", "position": [0, 0], "size": [500, 60],
            "repeatcollection": "families", "itemheight": 60,
            "items": [{"name": "Name", "field": "FamilyName", "position": [0, 0], "size": [200, 20]}],
        }
        model = ReportDesignerModel(ReportDefinitionLoader().from_dict(source))
        with self.assertRaisesRegex(ValueError, "beyond the detail row width"):
            model.set_repeater_item_geometry("FamilyName", "Name", position=[400, 0], size=[200, 20])

    def test_page_setup_changes_orientation_and_is_undoable(self):
        model = self.model()
        model.set_page_setup(
            "letter", "landscape", {"top": 36, "right": 36, "bottom": 36, "left": 36},
        )
        self.assertEqual(model.report["orientation"], "landscape")
        self.assertEqual(model.page_size, (792, 612))
        model.undo()
        self.assertEqual(model.report["orientation"], "portrait")

    def test_page_setup_rejects_too_narrow_printable_area(self):
        model = self.model()
        with self.assertRaisesRegex(ValueError, "printable width"):
            model.set_page_setup(
                "letter", "portrait", {"top": 36, "right": 210, "bottom": 36, "left": 210},
            )

    def test_report_sort_is_undoable_and_can_be_cleared(self):
        model = self.model()
        sort_items = [{
            "collection": "families", "field": "FamilyName", "direction": "descending",
        }]
        model.set_sort(sort_items)
        self.assertEqual(model.report["sort"], sort_items)
        self.assertTrue(model.undo())
        self.assertNotIn("sort", model.report)
        self.assertTrue(model.redo())
        model.set_sort([])
        self.assertNotIn("sort", model.report)

    def test_grouping_creates_editable_bands_and_default_heading(self):
        model = self.model()
        groups = [{
            "name": "CityGroup", "collection": "families", "field": "FamilyName",
            "headerband": "CityGroupHeader", "footerband": "CityGroupFooter",
            "keeptogether": True,
        }]
        model.set_groups(groups)
        self.assertEqual(model.report["bands"]["CityGroupHeader"]["type"], "groupheader")
        self.assertEqual(model.report["bands"]["CityGroupFooter"]["type"], "groupfooter")
        heading = next(
            control for control in model.controls.values()
            if control["band"] == "CityGroupHeader"
        )
        self.assertEqual(heading["field"], "FamilyName")
        self.assertEqual(model.report["sort"][0]["field"], "FamilyName")
        model.set_groups([])
        self.assertNotIn("CityGroupHeader", model.report["bands"])
        self.assertNotIn("groups", model.report)

    def test_report_total_creates_footer_and_is_undoable(self):
        model = self.model()
        name = model.add_aggregate(
            "families", "FamilyName", "count", format_name="integer",
        )
        self.assertEqual(model.controls[name]["type"], "aggregate")
        self.assertEqual(model.report["bands"]["ReportFooter"]["type"], "reportfooter")
        self.assertTrue(model.undo())
        self.assertNotIn(name, model.controls)
        self.assertNotIn("ReportFooter", model.report["bands"])

    def test_group_total_is_placed_in_matching_footer(self):
        model = self.model()
        groups = [{
            "name": "FamilyGroup", "collection": "families", "field": "FamilyName",
            "headerband": "FamilyGroupHeader", "footerband": "FamilyGroupFooter",
        }]
        model.set_groups(groups)
        name = model.add_aggregate(
            "families", "FamilyName", "count", scope="group", group="FamilyGroup",
            format_name="integer",
        )
        self.assertEqual(model.controls[name]["band"], "FamilyGroupFooter")
        self.assertGreaterEqual(model.report["bands"]["FamilyGroupFooter"]["height"], 28)

    def test_copy_and_paste_preserve_properties_with_unique_name(self):
        model = self.model()
        copied = model.copy_controls(["FamilyName"])
        created = model.paste_controls(copied)
        self.assertEqual(created, ["FamilyNameCopy"])
        original = model.controls["FamilyName"]
        duplicate = model.controls["FamilyNameCopy"]
        self.assertEqual(duplicate["field"], original["field"])
        self.assertNotEqual(duplicate["position"], original["position"])

    def test_pasting_multiple_controls_is_one_undoable_change(self):
        model = self.model()
        model.add_control("label", band="Detail", name="FirstLabel")
        copied = model.copy_controls(["FamilyName", "FirstLabel"])
        created = model.paste_controls(copied)
        self.assertTrue(all(name in model.controls for name in created))
        model.undo()
        self.assertTrue(all(name not in model.controls for name in created))

    def test_export_preview_file_creates_permanent_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "preview.pdf"
            target = Path(folder) / "exports" / "directory.pdf"
            source.write_bytes(b"%PDF-test")
            result = export_preview_file(source, target)
            self.assertEqual(result, target)
            self.assertEqual(target.read_bytes(), b"%PDF-test")


if __name__ == "__main__":
    unittest.main()
