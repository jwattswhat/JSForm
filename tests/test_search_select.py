import unittest

from search_select import SearchSelectModel


class SearchSelectModelTests(unittest.TestCase):
    def setUp(self):
        self.model = SearchSelectModel([
            {"id": 1, "first": "Avery", "last": "Bennett", "grade": "3"},
            {"id": 2, "first": "Jordan", "last": "Kim", "grade": "4"},
            {"id": 3, "first": "Riley", "last": "Patel", "grade": "3"},
        ], search_fields=("first", "last"))

    def test_search_uses_all_case_insensitive_terms(self):
        self.assertEqual([row["id"] for row in self.model.matching("avery BEN")], [1])

    def test_filter_and_search_can_be_combined(self):
        self.assertEqual(
            [row["id"] for row in self.model.matching("i", {"grade": "3"})],
            [3],
        )

    def test_blank_filter_means_all(self):
        self.assertEqual(len(self.model.matching(filters={"grade": None})), 3)

    def test_sort_is_case_insensitive_and_preserves_source(self):
        rows = self.model.matching()
        result = self.model.sorted(rows, "last", ascending=False)
        self.assertEqual([row["id"] for row in result], [3, 2, 1])
        self.assertEqual([row["id"] for row in rows], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
