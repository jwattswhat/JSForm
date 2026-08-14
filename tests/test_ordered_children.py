import unittest
from pathlib import Path

from ordered_children import OrderedChildModel


class OrderedChildModelTests(unittest.TestCase):
    def test_editor_owns_and_sizes_its_panel(self):
        source = Path(__file__).resolve().parents[1].joinpath("ordered_children.py").read_text(encoding="utf-8")
        self.assertIn("self.SetSizer(frame_sizer)", source)
        self.assertIn("self.SetMinSize((700, 420))", source)

    def test_add_move_delete_always_resequences(self):
        model = OrderedChildModel([
            {"id": 1, "sequence": 10, "name": "First"},
            {"id": 2, "sequence": 20, "name": "Second"},
        ])
        self.assertFalse(model.dirty)
        added = model.add({"id": 3, "name": "Third"})
        self.assertEqual(added, 2)
        selected = model.move(2, -1)
        self.assertEqual(selected, 1)
        self.assertEqual([row["id"] for row in model.rows], [1, 3, 2])
        model.remove(0)
        self.assertEqual([row["sequence"] for row in model.rows], [1, 2])

    def test_protected_row_cannot_be_removed(self):
        model = OrderedChildModel(
            [{"id": 1, "protected": True}],
            protected=lambda row: row["protected"],
        )
        with self.assertRaisesRegex(ValueError, "protected"):
            model.remove(0)

    def test_application_fields_and_stable_id_survive_update(self):
        model = OrderedChildModel([{"id": 7, "sequence": 4, "name": "Old"}])
        model.update(0, {"name": "New"})
        self.assertEqual(model.rows[0], {"id": 7, "sequence": 1, "name": "New"})

    def test_dirty_state_can_be_marked_saved(self):
        model = OrderedChildModel([{"id": 1, "sequence": 1}])
        self.assertFalse(model.dirty)
        model.add({"id": 2})
        self.assertTrue(model.dirty)
        model.mark_saved()
        self.assertFalse(model.dirty)


if __name__ == "__main__":
    unittest.main()
