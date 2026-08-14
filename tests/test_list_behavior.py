import unittest

from list_behavior import ListSortState, ListCtrlBehavior


class ListBehaviorTests(unittest.TestCase):
    def test_sort_state_starts_ascending_and_toggles_same_column(self):
        state = ListSortState()
        self.assertEqual(state.select(1), (1, True))
        self.assertEqual(state.select(1), (1, False))
        self.assertEqual(state.select(0), (0, True))

    def test_sorting_is_case_insensitive_and_does_not_mutate_input(self):
        behavior = object.__new__(ListCtrlBehavior)
        behavior.sort_state = ListSortState(0, True)
        rows = [{"name": "Zulu"}, {"name": "alpha"}]
        result = behavior.sorted(rows, (lambda row: row["name"],))
        self.assertEqual([row["name"] for row in result], ["alpha", "Zulu"])
        self.assertEqual([row["name"] for row in rows], ["Zulu", "alpha"])

    def test_selection_is_restored_by_stable_record_key(self):
        class Control:
            def __init__(self): self.selected = -1
            def GetFirstSelected(self): return self.selected
            def Select(self, index): self.selected = index
            def Focus(self, _index): pass
            def EnsureVisible(self, _index): pass

        rows = [{"id": 1}, {"id": 2}]
        behavior = object.__new__(ListCtrlBehavior)
        behavior.control = Control()
        behavior.item_provider = lambda: rows
        behavior.key = lambda row: row["id"]
        behavior.action_rules = ()
        behavior.restore_selection(2)
        self.assertEqual(behavior.control.selected, 1)

    def test_delete_key_respects_record_permission(self):
        class Event:
            def __init__(self): self.skipped = False
            def GetKeyCode(self):
                import wx
                return wx.WXK_DELETE
            def Skip(self): self.skipped = True

        deleted = []
        behavior = object.__new__(ListCtrlBehavior)
        behavior.delete = lambda _event: deleted.append(True)
        behavior.selected_item = lambda: {"protected": True}
        behavior.delete_allowed = lambda item: not item["protected"]
        event = Event()
        behavior._on_key(event)
        self.assertEqual(deleted, [])
        self.assertTrue(event.skipped)


if __name__ == "__main__":
    unittest.main()
