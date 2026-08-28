import unittest
from datetime import date
from decimal import Decimal

from dynamic_fields import (
    DynamicFieldDescriptor, DynamicFieldError, DynamicFieldOption,
    normalize_dynamic_value, validate_dynamic_descriptors,
)


class DynamicFieldContractTests(unittest.TestCase):
    def test_supported_types_round_trip_as_native_values(self):
        cases = (
            ("short_text", "  hello ", "hello"),
            ("integer", "42", 42),
            ("decimal", "12.345", Decimal("12.35")),
            ("date", "2026-08-24", date(2026, 8, 24)),
            ("boolean", "yes", True),
        )
        for kind, value, expected in cases:
            with self.subTest(kind=kind):
                descriptor = DynamicFieldDescriptor("sample", "Sample", kind)
                self.assertEqual(expected, normalize_dynamic_value(descriptor, value))

    def test_choice_fields_use_stable_keys_not_labels(self):
        options = (DynamicFieldOption("north", "North Campus"),
                   DynamicFieldOption("south", "South Campus"))
        single = DynamicFieldDescriptor("campus", "Campus", "single_choice", options=options)
        multiple = DynamicFieldDescriptor("campuses", "Campuses", "multiple_choice", options=options)
        self.assertEqual("north", normalize_dynamic_value(single, "north"))
        self.assertEqual(("north", "south"), normalize_dynamic_value(multiple, ["north", "south"]))
        with self.assertRaisesRegex(DynamicFieldError, "valid value"):
            normalize_dynamic_value(single, "North Campus")

    def test_required_length_range_and_duplicate_options_are_rejected(self):
        with self.assertRaisesRegex(DynamicFieldError, "required"):
            normalize_dynamic_value(DynamicFieldDescriptor("code", "Code", "short_text", required=True), "")
        with self.assertRaisesRegex(DynamicFieldError, "cannot exceed"):
            normalize_dynamic_value(DynamicFieldDescriptor("code", "Code", "short_text", max_length=3), "long")
        with self.assertRaisesRegex(DynamicFieldError, "cannot be less"):
            normalize_dynamic_value(DynamicFieldDescriptor("count", "Count", "integer", minimum=1), 0)
        with self.assertRaisesRegex(DynamicFieldError, "unique"):
            DynamicFieldDescriptor("choice", "Choice", "single_choice", options=(
                DynamicFieldOption("same", "One"), DynamicFieldOption("same", "Two")))
        with self.assertRaisesRegex(DynamicFieldError, "between 1 and 255"):
            DynamicFieldDescriptor("code", "Code", "short_text", max_length=256)
        with self.assertRaisesRegex(DynamicFieldError, "Integer length"):
            DynamicFieldDescriptor("count", "Count", "integer", max_length=10)

    def test_contract_is_bounded_sorted_and_application_neutral(self):
        fields = validate_dynamic_descriptors((
            DynamicFieldDescriptor("second", "Second", "boolean", section="B", order=2),
            DynamicFieldDescriptor("first", "First", "boolean", section="A", order=1),
        ))
        self.assertEqual(["first", "second"], [item.key for item in fields])
        with self.assertRaisesRegex(DynamicFieldError, "No more than 1"):
            validate_dynamic_descriptors(fields, maximum_fields=1)


if __name__ == "__main__":
    unittest.main()
