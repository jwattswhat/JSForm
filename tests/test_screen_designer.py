from pathlib import Path
import tempfile
import unittest

from JSForm.screen_definition import ScreenDefinitionLoader
from JSForm.screen_designer import ScreenDesignerModel


def definition():
    return ScreenDefinitionLoader().from_dict({
        "frmTestFORM": {
            "FORM": {"name": "frmTest", "type": "Panel", "title": "Test", "sizech": [50, 30]},
            "CONTROLS": {
                "lblName": {"name": "lblName", "type": "StaticText", "label": "Name", "posch": [1, 1], "sizech": [8, 1]},
                "Name": {"name": "Name", "type": "TextCtrl", "posch": [10, 1], "sizech": [20, 2], "security": {"edit": "membership.manage"}},
            },
        }
    })


class TestScreenDesignerModel(unittest.TestCase):
    def test_buffered_canvas_declares_paint_background_style(self):
        source = Path(__file__).resolve().parents[1].joinpath("screen_designer.py").read_text(encoding="utf-8")
        constructor = source.split("class ScreenCanvas", 1)[1].split("def scale_x", 1)[0]
        self.assertIn("SetBackgroundStyle(wx.BG_STYLE_PAINT)", constructor)
        paint = source.split("def on_paint", 1)[1].split("class Repeater", 1)[0]
        self.assertIn("wx.PaintDC(self)", paint)
        self.assertNotIn("AutoBufferedPaintDC", paint)

    def model(self): return ScreenDesignerModel(definition())

    def test_move_resize_and_round_trip_preserve_security(self):
        model = self.model()
        model.move("Name", 3, 2)
        model.resize("Name", 5, 1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "frmTest.json"
            model.save(path)
            reopened = ScreenDefinitionLoader().load(path)
        self.assertEqual(reopened.controls["Name"]["posch"], [13, 3])
        self.assertEqual(reopened.controls["Name"]["security"], {"edit": "membership.manage"})

    def test_add_copy_paste_delete_and_undo(self):
        model = self.model()
        added = model.add_control("Button")
        copies = model.paste_controls(model.copy_controls([added]))
        self.assertNotEqual(copies[0], added)
        model.delete_control(added)
        self.assertNotIn(added, model.controls)
        self.assertTrue(model.undo())
        self.assertIn(added, model.controls)

    def test_align_and_distribute(self):
        model = self.model()
        names = [model.add_control("Button", "Button{}".format(number)) for number in range(3)]
        for name, x in zip(names, (0, 15, 40)):
            model.set_geometry(name, [x, 10], [5, 2])
        model.distribute_controls(names, "horizontal")
        self.assertEqual([model.geometry(name)[0][0] for name in names], [0, 20, 40])
        model.align_controls(names, "top")
        self.assertEqual({model.geometry(name)[0][1] for name in names}, {10})

    def test_form_resize_keeps_controls_inside(self):
        model = self.model()
        model.set_geometry("Name", [40, 20], [10, 8])
        model.set_form_size([30, 15])
        position, size = model.geometry("Name")
        self.assertLessEqual(position[0] + size[0], 30)
        self.assertLessEqual(position[1] + size[1], 15)

    def test_protected_security_cannot_be_changed_in_visual_model(self):
        model = self.model()
        with self.assertRaisesRegex(ValueError, "developer-controlled"):
            model.set_property("Name", "security", {})

    def test_visual_style_properties_validate_and_round_trip(self):
        model = self.model()
        for key, value in (
            ("fontface", "Arial"), ("fontsize", 12), ("bold", True),
            ("italic", True), ("foreground", "#112233"),
            ("background", "#F0F0F0"),
        ):
            model.set_property("Name", key, value)
        control = model.validated_definition().controls["Name"]
        self.assertEqual(control["fontface"], "Arial")
        self.assertEqual(control["foreground"], "#112233")

    def test_validation_warns_about_overlap(self):
        model = self.model()
        model.set_geometry("Name", [1, 1], [8, 1])
        self.assertIn("lblName overlaps Name", model.layout_warnings())


if __name__ == "__main__":
    unittest.main()
