from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from report_dataset import (
    ReportCollection, ReportDataset, ReportDatasetContract, ReportDatasetError,
    ReportField,
)
from report_definition import ReportDefinitionLoader
from test_report_definition import valid_definition


class TestReportDataset(unittest.TestCase):
    def contract(self):
        return ReportDatasetContract(
            "membership.directory", 1, "reports.membership.contact",
            (ReportCollection("families", "Families", (
                ReportField("FamilyName", "Family Name"),
            )),),
        )

    def test_definition_bindings_must_exist_in_contract(self):
        definition_data = valid_definition()
        definition = ReportDefinitionLoader().from_dict(definition_data)
        self.contract().validate_definition(definition)
        definition_data["CMMD01REPORT"]["CONTROLS"]["FamilyName"]["field"] = "SecretNote"
        definition = ReportDefinitionLoader().from_dict(definition_data)
        with self.assertRaisesRegex(ReportDatasetError, "Unknown report field"):
            self.contract().validate_definition(definition)

    def test_dataset_rejects_extra_collections_and_fields(self):
        contract = self.contract()
        with self.assertRaises(ReportDatasetError):
            ReportDataset.create(contract, {"families": [], "users": []})
        with self.assertRaises(ReportDatasetError):
            ReportDataset.create(contract, {"families": [{"FamilyName": "Smith", "Password": "x"}]})

    def test_dataset_rows_are_immutable(self):
        dataset = ReportDataset.create(
            self.contract(), {"families": [{"FamilyName": "Smith"}]}
        )
        with self.assertRaises(TypeError):
            dataset.collections["families"][0]["FamilyName"] = "Changed"

    def test_sort_and_group_fields_must_be_approved(self):
        source = valid_definition()
        source["CMMD01REPORT"]["REPORT"]["sort"] = [{
            "collection": "families", "field": "PrivateNote", "direction": "ascending",
        }]
        definition = ReportDefinitionLoader().from_dict(source)
        with self.assertRaisesRegex(ReportDatasetError, "Unknown report field"):
            self.contract().validate_definition(definition)


if __name__ == "__main__":
    unittest.main()
