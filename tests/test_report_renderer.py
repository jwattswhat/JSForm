from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pypdf import PdfReader
from report_dataset import ReportCollection, ReportDataset, ReportDatasetContract, ReportField
from report_definition import ReportDefinitionLoader
from report_renderer import PDFReportRenderer
from test_report_definition import valid_definition


class TestPDFReportRenderer(unittest.TestCase):
    def test_native_values_use_consistent_report_formats(self):
        renderer = PDFReportRenderer()
        self.assertEqual(renderer._format_value(Decimal("11700"), "currency"), "$11,700.00")
        self.assertEqual(renderer._format_value(datetime(2026, 8, 12, 14, 5), "date"), "8/12/2026")
        self.assertEqual(renderer._format_value(datetime(2026, 8, 12, 14, 5), "time"), "2:05 PM")
        self.assertEqual(renderer._format_value("2183871200", "phone"), "(218) 387-1200")

    def test_multiline_text_preserves_explicit_line_breaks(self):
        self.assertEqual(
            PDFReportRenderer._wrapped_lines("100 Main St\nDuluth, MN 55802", 200, 10),
            ["100 Main St", "Duluth, MN 55802"],
        )
    def test_table_paginates_and_pdf_contains_bound_data(self):
        source = valid_definition()
        source["CMMD01REPORT"]["CONTROLS"]["FamilyName"] = {
            "type": "table", "band": "Detail", "position": [0, 0], "size": [500, 36],
            "repeatcollection": "families",
            "columns": [{
                "name": "FamilyName", "label": "Family", "collection": "families",
                "field": "FamilyName", "width": 500
            }]
        }
        definition = ReportDefinitionLoader().from_dict(source)
        contract = ReportDatasetContract(
            "membership.directory", 1, "reports.membership.contact",
            (ReportCollection("families", "Families", (ReportField("FamilyName", "Family Name"),)),),
        )
        rows = [{"FamilyName": f"Test Family {number:03d}"} for number in range(100)]
        dataset = ReportDataset.create(contract, {"families": rows})
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.pdf"
            PDFReportRenderer().render(definition, dataset, output)
            reader = PdfReader(output)
            self.assertGreater(len(reader.pages), 1)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            self.assertIn("Test Family 000", text)
            self.assertIn("Test Family 099", text)

    def test_rows_follow_multiple_sort_levels_without_mutating_dataset(self):
        source = valid_definition()
        source["CMMD01REPORT"]["REPORT"]["sort"] = [
            {"collection": "families", "field": "City", "direction": "ascending"},
            {"collection": "families", "field": "FamilyName", "direction": "descending"},
        ]
        definition = ReportDefinitionLoader().from_dict(source)
        contract = ReportDatasetContract(
            "membership.directory", 1, "reports.membership.contact",
            (ReportCollection("families", "Families", (
                ReportField("FamilyName", "Family Name"), ReportField("City", "City"),
            )),),
        )
        dataset = ReportDataset.create(contract, {"families": [
            {"FamilyName": "Able", "City": "Duluth"},
            {"FamilyName": "Young", "City": "Duluth"},
            {"FamilyName": "Baker", "City": "Bemidji"},
        ]})
        result = PDFReportRenderer._sorted_rows(
            dataset.collections["families"], definition, dataset, "families",
        )
        self.assertEqual([row["FamilyName"] for row in result], ["Baker", "Young", "Able"])
        self.assertEqual(dataset.collections["families"][0]["FamilyName"], "Able")

    def test_report_aggregate_counts_and_sums_rows(self):
        renderer = PDFReportRenderer()
        contract = ReportDatasetContract(
            "membership.directory", 1, "reports.membership.contact",
            (ReportCollection("families", "Families", (
                ReportField("Amount", "Amount", "currency"),
            )),),
        )
        dataset = ReportDataset.create(contract, {"families": [
            {"Amount": Decimal("10.50")}, {"Amount": Decimal("4.50")}, {"Amount": None},
        ]})
        count = {
            "collection": "families", "field": "Amount", "operation": "count", "scope": "report",
        }
        total = dict(count, operation="sum")
        self.assertEqual(renderer._aggregate_value(count, dataset), 2)
        self.assertEqual(renderer._aggregate_value(total, dataset), Decimal("15.00"))


if __name__ == "__main__":
    unittest.main()
