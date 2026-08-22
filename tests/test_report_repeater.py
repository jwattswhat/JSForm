from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pypdf import PdfReader
from report_dataset import ReportCollection, ReportDataset, ReportDatasetContract, ReportField
from report_definition import ReportDefinitionLoader
from report_renderer import PDFReportRenderer
from test_report_definition import valid_definition


class TestReportRepeater(unittest.TestCase):
    def test_schema_accepts_multi_column_repeater_settings(self):
        schema = json.loads(
            (Path(__file__).parents[1] / "schema" / "report_definition_schema.json").read_text()
        )
        properties = schema["$defs"]["control"]["properties"]
        self.assertEqual(properties["repeatcolumns"]["minimum"], 1)
        self.assertIn("columngap", properties)

    def test_repeater_can_suppress_record_separator(self):
        class FakePDF:
            def __init__(self):
                self.lines = []

            def setStrokeColorRGB(self, *_args):
                pass

            def setLineWidth(self, *_args):
                pass

            def line(self, *args):
                self.lines.append(args)

        pdf = FakePDF()
        repeater = {
            "position": [0, 0], "size": [200, 30], "itemheight": 30,
            "separator": False, "items": [],
        }
        PDFReportRenderer()._draw_repeater(pdf, repeater, {}, 100, 20, 30)
        self.assertEqual(pdf.lines, [])

    def test_repeater_wraps_and_paginates_records(self):
        source = valid_definition()
        source["CMMD01REPORT"]["CONTROLS"]["FamilyName"] = {
            "type": "repeater", "band": "Detail", "position": [0, 0], "size": [500, 50],
            "repeatcollection": "entries", "itemheight": 50,
            "items": [
                {"name": "Name", "field": "Name", "position": [0, 0], "size": [180, 14], "bold": True},
                {"name": "Details", "field": "Details", "position": [190, 0], "size": [300, 14], "fontsize": 8}
            ]
        }
        definition = ReportDefinitionLoader().from_dict(source)
        contract = ReportDatasetContract(
            "membership.directory", 1, "reports.membership.contact",
            (ReportCollection("entries", "Entries", (
                ReportField("Name", "Name"), ReportField("Details", "Details")
            )),),
        )
        rows = [{"Name": f"Family {number}", "Details": "Long listed detail " * 8} for number in range(40)]
        dataset = ReportDataset.create(contract, {"entries": rows})
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "repeat.pdf"
            PDFReportRenderer().render(definition, dataset, output)
            reader = PdfReader(output)
            text = " ".join(page.extract_text() or "" for page in reader.pages)
            self.assertGreater(len(reader.pages), 1)
            self.assertIn("Family 0", text)
            self.assertIn("Family 39", text)

    def test_multi_column_repeater_fills_across_then_down(self):
        source = valid_definition()
        report = source["CMMD01REPORT"]["REPORT"]
        report["margins"] = {"top": 36, "right": 13.5, "bottom": 28, "left": 13.5}
        report["bands"] = {"Detail": {"type": "detail", "height": 72}}
        source["CMMD01REPORT"]["CONTROLS"] = {
            "Labels": {
                "type": "repeater", "band": "Detail", "position": [0, 0],
                "size": [189, 72], "repeatcollection": "entries", "itemheight": 72,
                "repeatcolumns": 3, "columngap": 9, "separator": False,
                "items": [{
                    "name": "Name", "field": "Name", "position": [8, 7],
                    "size": [173, 14], "fontsize": 9,
                }],
            }
        }
        definition = ReportDefinitionLoader().from_dict(source)
        contract = ReportDatasetContract(
            "membership.directory", 1, "reports.membership.contact",
            (ReportCollection("entries", "Entries", (ReportField("Name", "Name"),)),),
        )
        dataset = ReportDataset.create(
            contract, {"entries": [{"Name": f"Label {number:02d}"} for number in range(1, 32)]},
        )
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "labels.pdf"
            PDFReportRenderer().render(definition, dataset, output)
            reader = PdfReader(output)
            self.assertEqual(len(reader.pages), 2)
            self.assertIn("Label 30", reader.pages[0].extract_text())
            self.assertNotIn("Label 31", reader.pages[0].extract_text())
            self.assertIn("Label 31", reader.pages[1].extract_text())

    def test_long_unbroken_values_are_split_to_the_available_width(self):
        lines = PDFReportRenderer._wrapped_lines(
            "extraordinarily.long.directory.address@example.invalid", 80, 8
        )
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(len(line) <= 19 for line in lines))

    def test_wrapped_item_pushes_later_item_down_in_same_column(self):
        renderer = PDFReportRenderer()
        repeater = {
            "itemheight": 50,
            "items": [
                {"name": "Name", "field": "Name", "position": [0, 0], "size": [80, 14], "fontsize": 10},
                {"name": "Members", "field": "Members", "position": [0, 18], "size": [80, 14], "fontsize": 8},
            ],
        }
        layout = renderer._repeater_layout(
            repeater, {"Name": "A very long household name that wraps", "Members": "Two Members"}
        )
        self.assertGreater(layout[1][2], 18)

    def test_repeater_image_uses_fixed_geometry_without_text_wrapping(self):
        repeater = {
            "itemheight": 72,
            "items": [{
                "name": "Photo", "type": "image", "field": "Photo",
                "position": [0, 0], "size": [64, 64],
            }],
        }
        renderer = PDFReportRenderer()
        layout = renderer._repeater_layout(repeater, {"Photo": b"image"})
        self.assertEqual(layout[0][1], [])
        self.assertEqual(renderer._repeater_height(repeater, {"Photo": b"image"}), 72)

    def test_autofit_content_detection_ignores_empty_bound_images_and_text(self):
        renderer = PDFReportRenderer()
        dataset = type("Dataset", (), {"collections": {"rows": ()}})()
        image = {
            "type": "image", "collection": "rows", "field": "Photo",
            "position": [0, 0], "size": [80, 72],
        }
        name = dict(image, type="text", field="Name")
        self.assertFalse(renderer._control_has_content(image, dataset, {"Photo": None}, "rows"))
        self.assertTrue(renderer._control_has_content(name, dataset, {"Name": "Household"}, "rows"))

    def test_group_headers_render_when_field_value_changes(self):
        source = valid_definition()
        report = source["CMMD01REPORT"]["REPORT"]
        report["bands"] = {
            "GroupHeader": {"type": "groupheader", "height": 20},
            "Detail": {"type": "detail", "height": 24},
            "GroupFooter": {"type": "groupfooter", "height": 4},
        }
        report["groups"] = [{
            "name": "CityGroup", "collection": "entries", "field": "City",
            "headerband": "GroupHeader", "footerband": "GroupFooter",
            "keeptogether": True,
        }]
        report["sort"] = [{
            "collection": "entries", "field": "City", "direction": "ascending",
        }]
        source["CMMD01REPORT"]["CONTROLS"] = {
            "GroupCity": {
                "type": "text", "band": "GroupHeader", "position": [0, 0],
                "size": [200, 18], "collection": "entries", "field": "City", "bold": True,
            },
            "Entries": {
                "type": "repeater", "band": "Detail", "position": [0, 0], "size": [500, 24],
                "repeatcollection": "entries", "itemheight": 24,
                "items": [{"name": "Name", "field": "Name", "position": [0, 0], "size": [200, 14]}],
            },
        }
        definition = ReportDefinitionLoader().from_dict(source)
        contract = ReportDatasetContract(
            "membership.directory", 1, "reports.membership.contact",
            (ReportCollection("entries", "Entries", (
                ReportField("Name", "Name"), ReportField("City", "City"),
            )),),
        )
        dataset = ReportDataset.create(contract, {"entries": [
            {"Name": "Zed", "City": "Duluth"}, {"Name": "Amy", "City": "Bemidji"},
            {"Name": "Bob", "City": "Duluth"},
        ]})
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "groups.pdf"
            PDFReportRenderer().render(definition, dataset, output)
            text = "\n".join(page.extract_text() or "" for page in PdfReader(output).pages)
            self.assertEqual(text.count("Bemidji"), 1)
            self.assertEqual(text.count("Duluth"), 1)
            self.assertLess(text.index("Amy"), text.index("Bob"))


if __name__ == "__main__":
    unittest.main()
