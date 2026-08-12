from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
