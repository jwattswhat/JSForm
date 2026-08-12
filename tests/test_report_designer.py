from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from report_definition import ReportDefinitionLoader
from report_designer import ReportDesignerModel
from test_report_definition import valid_definition


class TestReportDesignerModel(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
