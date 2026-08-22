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
    def test_table_row_can_bind_its_text_color(self):
        class RecordingPDF:
            def __init__(self): self.fills = []
            def setStrokeColorRGB(self, *_args): pass
            def setLineWidth(self, *_args): pass
            def line(self, *_args): pass
            def setFont(self, *_args): pass
            def setFillColorRGB(self, *value): self.fills.append(value)
            def drawString(self, *_args): pass

        renderer = PDFReportRenderer()
        pdf = RecordingPDF()
        renderer._draw_table_row(pdf, {
            "position": [0, 0], "colorfield": "FlagColor",
            "columns": [{"field": "Name", "width": 100}],
        }, {"Name": "Flagged member", "FlagColor": "#C00000"}, 40, 0, 20)
        self.assertIn((192 / 255, 0, 0), pdf.fills)

    def test_data_bound_rectangle_uses_value_and_omits_blank_value(self):
        class RecordingPDF:
            def __init__(self):
                self.fills = []
                self.rectangles = []

            def setStrokeColorRGB(self, *_args):
                pass

            def setLineWidth(self, *_args):
                pass

            def setFillColorRGB(self, *value):
                self.fills.append(value)

            def rect(self, *args, **kwargs):
                self.rectangles.append((args, kwargs))

        contract = ReportDatasetContract(
            "test.colors", 1, "reports.test",
            (ReportCollection("service", "Service", (ReportField("ColorHex", "Color"),)),),
        )
        renderer = PDFReportRenderer()
        control = {
            "type": "rectangle", "position": [0, 0], "size": [12, 12],
            "collection": "service", "field": "ColorHex",
        }
        pdf = RecordingPDF()
        renderer._draw_control(
            pdf, control, ReportDataset.create(contract, {"service": [{"ColorHex": "#2E7D32"}]}),
            0, 20,
        )
        self.assertEqual(pdf.fills[-1], (46 / 255, 125 / 255, 50 / 255))
        self.assertEqual(len(pdf.rectangles), 1)

        blank_pdf = RecordingPDF()
        renderer._draw_control(
            blank_pdf, control, ReportDataset.create(contract, {"service": [{"ColorHex": ""}]}),
            0, 20,
        )
        self.assertEqual(blank_pdf.rectangles, [])

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

    def test_empty_table_prints_clear_empty_result_message(self):
        source = valid_definition()
        source["CMMD01REPORT"]["REPORT"]["emptytext"] = "Nothing to report."
        source["CMMD01REPORT"]["CONTROLS"]["FamilyName"] = {
            "type": "table", "band": "Detail", "position": [0, 0], "size": [500, 36],
            "repeatcollection": "families",
            "columns": [{
                "name": "FamilyName", "label": "Family", "collection": "families",
                "field": "FamilyName", "width": 500,
            }],
        }
        definition = ReportDefinitionLoader().from_dict(source)
        contract = ReportDatasetContract(
            "membership.directory", 1, "reports.membership.contact",
            (ReportCollection("families", "Families", (ReportField("FamilyName", "Family Name"),)),),
        )
        dataset = ReportDataset.create(contract, {"families": []})
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "empty.pdf"
            PDFReportRenderer().render(definition, dataset, output)
            text = PdfReader(output).pages[0].extract_text() or ""
            self.assertIn("Nothing to report.", text)

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

    def test_system_values_supply_report_metadata(self):
        renderer = PDFReportRenderer()
        renderer._rendered_at = datetime(2026, 8, 12, 14, 5)
        renderer._page_number = 3
        renderer._context = {"run_user": "Jonathan Watt"}
        definition = ReportDefinitionLoader().from_dict(valid_definition())
        self.assertEqual(renderer._system_value(
            {"systemvalue": "run_date", "prefix": "Run: "}, definition
        ), "Run: 8/12/2026")
        self.assertEqual(renderer._system_value(
            {"systemvalue": "page_number", "prefix": "Page "}, definition
        ), "Page 3")
        self.assertEqual(renderer._system_value(
            {"systemvalue": "run_user", "prefix": "Run by: "}, definition
        ), "Run by: Jonathan Watt")

    def test_default_page_number_can_be_suppressed(self):
        class RecordingPDF:
            def __init__(self):
                self.text = []

            def setFont(self, *_args): pass
            def setFillColorRGB(self, *_args): pass
            def drawRightString(self, *_args): self.text.append(_args[-1])

        source = valid_definition()
        source["CMMD01REPORT"]["REPORT"]["showdefaultpagenumber"] = False
        definition = ReportDefinitionLoader().from_dict(source)
        pdf = RecordingPDF()
        PDFReportRenderer()._draw_footer(
            pdf, definition, None, 20, 612,
            {"left": 36, "right": 36, "top": 36, "bottom": 36}, 1,
        )
        self.assertEqual(pdf.text, [])

    def test_approved_condition_operators_are_deterministic(self):
        contract = ReportDatasetContract(
            "membership.directory", 1, "reports.membership.contact",
            (ReportCollection("status", "Status", (ReportField("Ready", "Ready", "boolean"),)),),
        )
        dataset = ReportDataset.create(contract, {"status": [{"Ready": True}]})
        renderer = PDFReportRenderer()
        self.assertTrue(renderer._condition_matches(
            {"collection": "status", "field": "Ready", "operator": "equals", "value": True},
            dataset,
        ))
        self.assertFalse(renderer._condition_matches(
            {"collection": "status", "field": "Ready", "operator": "not_equals", "value": True},
            dataset,
        ))

    def test_matrix_pivots_dynamic_columns_and_renders_totals(self):
        source = valid_definition()
        source["CMMD01REPORT"]["REPORT"]["orientation"] = "landscape"
        source["CMMD01REPORT"]["CONTROLS"]["FamilyName"] = {
            "type": "matrix", "band": "Detail", "position": [0, 0], "size": [700, 60],
            "repeatcollection": "expenses", "rowfield": "Account", "columnfield": "Function",
            "valuefield": "Amount", "rowlabel": "Expense account", "rowwidth": 220,
            "format": "currency", "showrowtotals": True, "showcolumntotals": True,
            "showgrandtotal": True,
        }
        definition = ReportDefinitionLoader().from_dict(source)
        contract = ReportDatasetContract(
            "membership.directory", 1, "reports.membership.contact",
            (ReportCollection("expenses", "Expenses", (
                ReportField("Account", "Account"), ReportField("Function", "Function"),
                ReportField("Amount", "Amount", "currency"),
            )),),
        )
        dataset = ReportDataset.create(contract, {"expenses": [
            {"Account": "Supplies", "Function": "Worship", "Amount": Decimal("100")},
            {"Account": "Supplies", "Function": "Education", "Amount": Decimal("25")},
            {"Account": "Utilities", "Function": "Worship", "Amount": Decimal("50")},
        ]})
        contract.validate_definition(definition)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "matrix.pdf"
            PDFReportRenderer().render(definition, dataset, output)
            text = PdfReader(output).pages[0].extract_text() or ""
            for expected in ("Expense account", "Education", "Worship", "Supplies", "Utilities", "$175.00"):
                self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
