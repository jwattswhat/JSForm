import unittest

from grid_behavior import GridBehavior, grid_checked


class Control:
    def __init__(self):
        self.row = 0
        self.column = 0
        self.values = {(0, 0): ""}
        self.view = (2, 3)

    def GetGridCursorRow(self): return self.row
    def GetGridCursorCol(self): return self.column
    def SetGridCursor(self, row, column): self.row, self.column = row, column
    def GetCellValue(self, row, column): return self.values.get((row, column), "")
    def SetCellValue(self, row, column, value): self.values[(row, column)] = value
    def GetViewStart(self): return self.view
    def Scroll(self, x, y): self.view = (x, y)
    def MakeCellVisible(self, _row, _column): pass


class GridBehaviorTests(unittest.TestCase):
    def behavior(self, rows=None, **keywords):
        behavior = object.__new__(GridBehavior)
        behavior.control = Control()
        behavior.item_provider = lambda: rows if rows is not None else [{"id": 1}]
        behavior.checkbox_columns = frozenset(keywords.get("checkbox_columns", (0,)))
        behavior.changed = keywords.get("changed")
        behavior.key = lambda row: row["id"]
        behavior.action_rules = ()
        return behavior

    def test_checkbox_values_are_semantic(self):
        self.assertTrue(grid_checked("1"))
        self.assertTrue(grid_checked("TRUE"))
        self.assertFalse(grid_checked(""))
        self.assertFalse(grid_checked("0"))

    def test_toggle_changes_a_boolean_cell_with_one_action(self):
        changes = []
        behavior = self.behavior(changed=lambda row, column, checked: changes.append((row, column, checked)))
        self.assertTrue(behavior.toggle(0, 0))
        self.assertEqual(behavior.control.GetCellValue(0, 0), "1")
        self.assertFalse(behavior.toggle(0, 0))
        self.assertEqual(changes, [(0, 0, True), (0, 0, False)])

    def test_selection_and_scroll_restore_by_stable_key(self):
        rows = [{"id": 1}, {"id": 2}]
        behavior = self.behavior(rows)
        behavior.control.row = 1
        state = behavior.remembered_state()
        rows.reverse()
        behavior.restore_state(state)
        self.assertEqual(behavior.control.row, 0)
        self.assertEqual(behavior.control.view, (2, 3))


if __name__ == "__main__":
    unittest.main()
