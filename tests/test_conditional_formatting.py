import unittest

from conditional_formatting import ConditionalFormatter, condition_matches, status_style


class ConditionalFormattingTests(unittest.TestCase):
    def test_semantic_styles_are_stable(self):
        self.assertEqual(status_style("customized").foreground, "#0066CC")
        self.assertTrue(status_style("incomplete").bold)
        self.assertEqual(status_style("omitted"), status_style("inactive"))

    def test_common_condition_operators(self):
        self.assertTrue(condition_matches(None, "empty"))
        self.assertTrue(condition_matches("Ready", "contains", "ead"))
        self.assertTrue(condition_matches(4, "greater_than", 3))
        self.assertFalse(condition_matches(False, "truthy"))

    def test_first_matching_rule_supplies_named_status(self):
        formatter = ConditionalFormatter((
            {"field": "active", "operator": "falsy", "style": "inactive"},
            {"field": "complete", "operator": "falsy", "style": "incomplete"},
        ))
        self.assertEqual(formatter.status({"active": False, "complete": False}), "inactive")
        self.assertEqual(formatter.status({"active": True, "complete": False}), "incomplete")
        self.assertEqual(formatter.status({"active": True, "complete": True}), "normal")

    def test_unknown_operator_and_style_fail_clearly(self):
        with self.assertRaisesRegex(ValueError, "operator"):
            condition_matches(1, "approximately", 1)
        with self.assertRaisesRegex(ValueError, "status style"):
            status_style("mystery")


if __name__ == "__main__":
    unittest.main()
