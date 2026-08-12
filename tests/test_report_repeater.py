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


if __name__ == "__main__":
    unittest.main()
