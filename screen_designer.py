"""Visual editor for native JSForm screen definitions."""

from copy import deepcopy
from pathlib import Path

import wx

from JSForm.form_services import FormDefinitionError
from JSForm.screen_definition import (
    ScreenDefinition,
    ScreenDefinitionLoader,
    save_screen_definition,
)


CELL_WIDTH = 10
CELL_HEIGHT = 18
HANDLE = 7
MINIMUM_SIZE = (1, 1)
CONTROL_TYPES = (
    "StaticBox", "StaticText", "TextCtrl", "MultiLine", "TextNumber",
    "Currency", "Float", "CheckBox", "ComboBox", "Button",
    "DatePickerCtrl", "TimePickerCtrl", "CalendarCtrl", "FilePickerCtrl",
    "ImagePickerCtrl", "ListCtrl", "ListCtrlID", "DataViewListCtrl",
    "CheckListBox", "CheckListEdit", "JSON", "HTMLCtrl", "DateTime",
)
DEFAULT_SIZES = {
    "StaticText": [10, 1], "StaticBox": [18, 6], "CheckBox": [12, 1],
    "Button": [8, 2], "MultiLine": [20, 6], "ListCtrl": [24, 8],
    "ListCtrlID": [24, 8], "DataViewListCtrl": [24, 8],
    "CheckListBox": [20, 6], "CheckListEdit": [20, 6],
    "CalendarCtrl": [22, 10], "HTMLCtrl": [24, 10], "JSON": [24, 8],
    "ImagePickerCtrl": [20, 4], "FilePickerCtrl": [20, 2],
}
LABEL_TYPES = {"StaticText", "StaticBox", "CheckBox", "Button"}
PROTECTED_PROPERTIES = {"lookupchoices", "action", "security", "table"}


class ScreenDesignerModel:
    def __init__(self, definition, loader=None):
        self.loader = loader or ScreenDefinitionLoader()
        self.data = definition.to_dict()
        self.root_name = definition.root_name
        self.selected = None
        self.dirty = False
        self.undo_stack = []
        self.redo_stack = []
        self.transaction_snapshot = None

    def _snapshot(self):
        return deepcopy(self.data), self.root_name, self.selected

    def _record_change(self):
        if self.transaction_snapshot is None:
            self.undo_stack.append(self._snapshot())
            self.undo_stack = self.undo_stack[-100:]
            self.redo_stack.clear()

    def begin_transaction(self):
        if self.transaction_snapshot is None:
            self.transaction_snapshot = self._snapshot()

    def end_transaction(self):
        if self.transaction_snapshot is None:
            return
        old = self.transaction_snapshot
        self.transaction_snapshot = None
        if old[0] != self.data:
            self.undo_stack.append(old)
            self.undo_stack = self.undo_stack[-100:]
            self.redo_stack.clear()

    @property
    def form(self):
        return self.data[self.root_name]["FORM"]

    @property
    def controls(self):
        return self.data[self.root_name]["CONTROLS"]

    @property
    def form_size(self):
        return list(self.form.get("sizech", [50, 35]))

    def select(self, name):
        if name is not None and name not in self.controls:
            raise KeyError(name)
        self.selected = name

    def undo(self):
        if not self.undo_stack:
            return False
        self.redo_stack.append(self._snapshot())
        self.data, self.root_name, self.selected = self.undo_stack.pop()
        self.dirty = True
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        self.undo_stack.append(self._snapshot())
        self.data, self.root_name, self.selected = self.redo_stack.pop()
        self.dirty = True
        return True

    def _bounded_geometry(self, position, size):
        form_width, form_height = self.form_size
        width = max(MINIMUM_SIZE[0], min(float(size[0]), form_width))
        height = max(MINIMUM_SIZE[1], min(float(size[1]), form_height))
        x = min(max(0, float(position[0])), max(0, form_width - width))
        y = min(max(0, float(position[1])), max(0, form_height - height))
        return [x, y], [width, height]

    def geometry(self, name):
        control = self.controls[name]
        position = list(control.get("posch", [0, 0]))
        size = list(control.get("sizech", DEFAULT_SIZES.get(control["type"], [16, 2])))
        return position, size

    def set_geometry(self, name, position=None, size=None):
        old_position, old_size = self.geometry(name)
        new_position, new_size = self._bounded_geometry(
            position if position is not None else old_position,
            size if size is not None else old_size,
        )
        if new_position == old_position and new_size == old_size:
            return
        self._record_change()
        control = self.controls[name]
        control["posch"] = new_position
        control["sizech"] = new_size
        self.dirty = True

    def move(self, name, dx, dy):
        position, size = self.geometry(name)
        self.set_geometry(name, [position[0] + dx, position[1] + dy], size)

    def resize(self, name, dw, dh):
        position, size = self.geometry(name)
        self.set_geometry(name, position, [size[0] + dw, size[1] + dh])

    def snap_to_grid(self, name, grid_size=1):
        if grid_size <= 0:
            raise ValueError("Grid size must be positive")
        position, size = self.geometry(name)
        self.set_geometry(
            name,
            [round(value / grid_size) * grid_size for value in position],
            [max(1, round(value / grid_size) * grid_size) for value in size],
        )

    def set_form_size(self, size):
        width, height = (float(value) for value in size)
        if width < 10 or height < 8:
            raise ValueError("A screen must be at least 10 by 8 character units")
        self._record_change()
        self.form["sizech"] = [width, height]
        for name in self.controls:
            position, control_size = self.geometry(name)
            bounded_position, bounded_size = self._bounded_geometry(position, control_size)
            self.controls[name]["posch"] = bounded_position
            self.controls[name]["sizech"] = bounded_size
        self.dirty = True

    def set_form_property(self, key, value):
        if key in PROTECTED_PROPERTIES:
            raise ValueError("{} is developer-controlled".format(key))
        candidate = deepcopy(self.data)
        if value is None:
            candidate[self.root_name]["FORM"].pop(key, None)
        else:
            candidate[self.root_name]["FORM"][key] = value
        validated = self.loader.from_dict(candidate)
        self._record_change()
        self.data = validated.to_dict()
        self.dirty = True

    def set_property(self, name, key, value):
        if key in PROTECTED_PROPERTIES or key == "name":
            raise ValueError("{} is developer-controlled".format(key))
        candidate = deepcopy(self.data)
        control = candidate[self.root_name]["CONTROLS"][name]
        if value is None or value == "":
            control.pop(key, None)
        else:
            control[key] = value
        validated = self.loader.from_dict(candidate)
        self._record_change()
        self.data = validated.to_dict()
        self.dirty = True

    def unique_control_name(self, prefix):
        if prefix not in self.controls:
            return prefix
        number = 2
        while "{}{}".format(prefix, number) in self.controls:
            number += 1
        return "{}{}".format(prefix, number)

    def add_control(self, control_type, name=None):
        if control_type not in CONTROL_TYPES:
            raise ValueError("Unsupported control type: {}".format(control_type))
        prefix = "lbl" if control_type == "StaticText" else control_type
        name = name or self.unique_control_name(prefix)
        if name in self.controls:
            raise ValueError("A control named {} already exists".format(name))
        size = list(DEFAULT_SIZES.get(control_type, [16, 2]))
        control = {"name": name, "type": control_type, "posch": [1, 1], "sizech": size}
        if control_type in LABEL_TYPES:
            control["label"] = "New {}".format(control_type.replace("Static", "").lower())
        candidate = deepcopy(self.data)
        candidate[self.root_name]["CONTROLS"][name] = control
        validated = self.loader.from_dict(candidate)
        self._record_change()
        self.data = validated.to_dict()
        self.selected = name
        self.dirty = True
        return name

    def delete_control(self, name):
        if name not in self.controls:
            raise KeyError(name)
        self._record_change()
        del self.controls[name]
        if self.selected == name:
            self.selected = None
        self.dirty = True

    def copy_controls(self, names):
        return [(name, deepcopy(self.controls[name])) for name in names]

    def paste_controls(self, copied_controls, offset=(2, 1)):
        self._record_change()
        created = []
        for original_name, source in copied_controls:
            name = self.unique_control_name(original_name)
            control = deepcopy(source)
            control["name"] = name
            position = control.get("posch", [0, 0])
            size = control.get("sizech", DEFAULT_SIZES.get(control["type"], [16, 2]))
            position, size = self._bounded_geometry(
                [position[0] + offset[0], position[1] + offset[1]], size
            )
            control["posch"] = position
            control["sizech"] = size
            self.controls[name] = control
            created.append(name)
        self.loader.from_dict(self.data)
        self.selected = created[-1] if created else self.selected
        self.dirty = bool(created) or self.dirty
        return created

    def align_controls(self, names, edge):
        names = list(dict.fromkeys(names))
        if len(names) < 2:
            raise ValueError("Select at least two controls to align")
        geometries = {name: self.geometry(name) for name in names}
        if edge in ("left", "top"):
            index = 0 if edge == "left" else 1
            target = min(value[0][index] for value in geometries.values())
        elif edge == "right":
            target = max(value[0][0] + value[1][0] for value in geometries.values())
        elif edge == "bottom":
            target = max(value[0][1] + value[1][1] for value in geometries.values())
        else:
            raise ValueError("Unknown alignment edge")
        self.begin_transaction()
        try:
            for name, (position, size) in geometries.items():
                if edge == "left": position[0] = target
                elif edge == "right": position[0] = target - size[0]
                elif edge == "top": position[1] = target
                else: position[1] = target - size[1]
                self.set_geometry(name, position, size)
        finally:
            self.end_transaction()

    def distribute_controls(self, names, axis):
        names = list(dict.fromkeys(names))
        if len(names) < 3:
            raise ValueError("Select at least three controls to distribute")
        horizontal = axis == "horizontal"
        if not horizontal and axis != "vertical":
            raise ValueError("Unknown distribution axis")
        index = 0 if horizontal else 1
        ordered = sorted(names, key=lambda name: self.geometry(name)[0][index])
        first_position, first_size = self.geometry(ordered[0])
        last_position, last_size = self.geometry(ordered[-1])
        start = first_position[index]
        end = last_position[index] + last_size[index]
        total_size = sum(self.geometry(name)[1][index] for name in ordered)
        gap = (end - start - total_size) / (len(ordered) - 1)
        cursor = start
        self.begin_transaction()
        try:
            for name in ordered:
                position, size = self.geometry(name)
                position[index] = cursor
                self.set_geometry(name, position, size)
                cursor += size[index] + gap
        finally:
            self.end_transaction()

    @staticmethod
    def _overlap(first, second):
        ax, ay, aw, ah = first
        bx, by, bw, bh = second
        return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah

    def layout_warnings(self):
        warnings = []
        width, height = self.form_size
        rectangles = []
        for name in self.controls:
            position, size = self.geometry(name)
            x, y = position
            control_width, control_height = size
            if x < 0 or y < 0 or x + control_width > width or y + control_height > height:
                warnings.append("{} extends outside the screen".format(name))
            rectangles.append((name, x, y, control_width, control_height))
        for index, first in enumerate(rectangles):
            if self.controls[first[0]]["type"] == "StaticBox":
                continue
            for second in rectangles[index + 1:]:
                if self.controls[second[0]]["type"] == "StaticBox":
                    continue
                if self._overlap(first[1:], second[1:]):
                    warnings.append("{} overlaps {}".format(first[0], second[0]))
        return warnings

    def validated_definition(self):
        return self.loader.from_dict(deepcopy(self.data))

    def replace_definition(self, definition):
        self._record_change()
        self.data = definition.to_dict()
        self.root_name = definition.root_name
        self.selected = next(iter(self.controls), None)
        self.dirty = True

    def rename_definition(self, form_name):
        if not form_name or not form_name.replace("_", "").isalnum():
            raise ValueError("Use letters, numbers, and underscores for the screen name")
        old_root = self.root_name
        new_root = form_name + "FORM"
        candidate = {new_root: deepcopy(self.data[old_root])}
        candidate[new_root]["FORM"]["name"] = form_name
        validated = self.loader.from_dict(candidate, form_name)
        self._record_change()
        self.data = validated.to_dict()
        self.root_name = new_root
        self.dirty = True

    def save(self, path):
        definition = self.validated_definition()
        save_screen_definition(definition, path)
        self.dirty = False
        return Path(path)


class ScreenCanvas(wx.ScrolledWindow):
    def __init__(self, parent, model, selection_handler=None):
        super().__init__(parent, style=wx.BORDER_SUNKEN | wx.WANTS_CHARS)
        self.model = model
        self.selection_handler = selection_handler
        self.selected_names = set()
        self.zoom = 1.0
        self.snap = False
        self.show_grid = True
        self.drag_start = None
        self.drag_geometry = None
        self.drag_mode = None
        self.SetBackgroundColour(wx.Colour(150, 150, 150))
        self.SetScrollRate(10, 10)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.Bind(wx.EVT_LEFT_DCLICK, self.on_left_double_click)
        self.Bind(wx.EVT_MOTION, self.on_motion)
        self.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key)
        self.refresh_extent()

    def scale_x(self): return CELL_WIDTH * self.zoom
    def scale_y(self): return CELL_HEIGHT * self.zoom

    def refresh_extent(self):
        width, height = self.model.form_size
        self.SetVirtualSize((int(width * self.scale_x() + 80), int(height * self.scale_y() + 80)))
        self.Refresh()

    def fit_form(self):
        width, height = self.model.form_size
        available = self.GetClientSize()
        if width and height and available.width > 80 and available.height > 80:
            self.zoom = max(.25, min(2.0, (available.width - 60) / (width * CELL_WIDTH), (available.height - 60) / (height * CELL_HEIGHT)))
            self.refresh_extent()

    def form_origin(self): return (30, 30)

    def control_rect(self, name):
        position, size = self.model.geometry(name)
        left, top = self.form_origin()
        return wx.Rect(
            int(left + position[0] * self.scale_x()),
            int(top + position[1] * self.scale_y()),
            max(3, int(size[0] * self.scale_x())),
            max(3, int(size[1] * self.scale_y())),
        )

    def hit_test(self, point):
        for name in reversed(list(self.model.controls)):
            rectangle = self.control_rect(name)
            handle = wx.Rect(rectangle.right - HANDLE, rectangle.bottom - HANDLE, HANDLE * 2, HANDLE * 2)
            if handle.Contains(point) and name in self.selected_names:
                return name, "resize"
            if rectangle.Contains(point):
                return name, "move"
        return None, None

    def select(self, name, extend=False):
        if name is None:
            self.selected_names.clear()
            self.model.select(None)
        else:
            if not extend:
                self.selected_names = {name}
            elif name in self.selected_names:
                self.selected_names.remove(name)
            else:
                self.selected_names.add(name)
            self.model.select(name if name in self.selected_names else next(iter(self.selected_names), None))
        if self.selection_handler:
            self.selection_handler(self.model.selected)
        self.Refresh()

    def on_left_down(self, event):
        point = self.CalcUnscrolledPosition(event.GetPosition())
        name, mode = self.hit_test(point)
        if not name:
            self.select(None)
            return
        self.select(name, event.ControlDown())
        if name not in self.selected_names:
            return
        self.drag_start = point
        self.drag_geometry = self.model.geometry(name)
        self.drag_mode = mode
        self.model.begin_transaction()
        self.CaptureMouse()

    def on_left_double_click(self, event):
        point = self.CalcUnscrolledPosition(event.GetPosition())
        name, _ = self.hit_test(point)
        if name:
            self.select(name)
            if self.selection_handler:
                self.selection_handler(name, activate=True)

    def on_motion(self, event):
        if not self.drag_start or not event.Dragging() or not event.LeftIsDown():
            return
        point = self.CalcUnscrolledPosition(event.GetPosition())
        dx = (point.x - self.drag_start.x) / self.scale_x()
        dy = (point.y - self.drag_start.y) / self.scale_y()
        position, size = deepcopy(self.drag_geometry)
        if self.drag_mode == "resize":
            size = [size[0] + dx, size[1] + dy]
        else:
            position = [position[0] + dx, position[1] + dy]
        self.model.set_geometry(self.model.selected, position, size)
        self.Refresh()

    def on_left_up(self, event):
        if self.HasCapture(): self.ReleaseMouse()
        if self.drag_start:
            if self.snap and self.model.selected:
                self.model.snap_to_grid(self.model.selected)
            self.model.end_transaction()
            self.drag_start = self.drag_geometry = self.drag_mode = None
            if self.selection_handler: self.selection_handler(self.model.selected)
            self.Refresh()

    def on_key(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_DELETE:
            wx.PostEvent(self.GetParent(), wx.CommandEvent(wx.EVT_MENU.typeId, wx.ID_DELETE))
            return
        directions = {wx.WXK_LEFT: (-1, 0), wx.WXK_RIGHT: (1, 0), wx.WXK_UP: (0, -1), wx.WXK_DOWN: (0, 1)}
        if key in directions and self.selected_names:
            dx, dy = directions[key]
            self.model.begin_transaction()
            try:
                for name in self.selected_names:
                    if event.ShiftDown(): self.model.resize(name, dx, dy)
                    else: self.model.move(name, dx, dy)
            finally:
                self.model.end_transaction()
            if self.selection_handler: self.selection_handler(self.model.selected)
            self.Refresh()
            return
        event.Skip()

    def on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        self.PrepareDC(dc)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        left, top = self.form_origin()
        width, height = self.model.form_size
        form_rect = wx.Rect(left, top, int(width * self.scale_x()), int(height * self.scale_y()))
        dc.SetBrush(wx.Brush(wx.WHITE))
        dc.SetPen(wx.Pen(wx.Colour(70, 70, 70), 1))
        dc.DrawRectangle(form_rect)
        if self.show_grid and self.zoom >= .5:
            dc.SetPen(wx.Pen(wx.Colour(230, 230, 230), 1))
            for column in range(1, int(width)):
                x = int(left + column * self.scale_x())
                dc.DrawLine(x, top, x, form_rect.bottom)
            for row in range(1, int(height)):
                y = int(top + row * self.scale_y())
                dc.DrawLine(left, y, form_rect.right, y)
        for name, control in self.model.controls.items():
            rectangle = self.control_rect(name)
            selected = name in self.selected_names
            control_type = control.get("type", "Control")
            if control_type == "StaticBox":
                dc.SetBrush(wx.TRANSPARENT_BRUSH)
            elif control_type in ("StaticText", "CheckBox"):
                dc.SetBrush(wx.Brush(wx.Colour(250, 250, 250)))
            else:
                dc.SetBrush(wx.Brush(wx.Colour(225, 238, 250)))
            dc.SetPen(wx.Pen(wx.Colour(0, 102, 204) if selected else wx.Colour(90, 120, 145), 2 if selected else 1))
            dc.DrawRectangle(rectangle)
            label = control.get("label") or "{}: {}".format(name, control_type)
            dc.SetTextForeground(wx.BLACK)
            dc.SetClippingRegion(rectangle)
            dc.DrawText(str(label), rectangle.x + 3, rectangle.y + 2)
            dc.DestroyClippingRegion()
            if selected:
                dc.SetBrush(wx.Brush(wx.Colour(0, 102, 204)))
                dc.DrawRectangle(rectangle.right - HANDLE, rectangle.bottom - HANDLE, HANDLE, HANDLE)


class FormSizeDialog(wx.Dialog):
    def __init__(self, parent, model):
        super().__init__(parent, title="Screen Size")
        width, height = model.form_size
        self.width = wx.SpinCtrlDouble(self, min=10, max=300, initial=width, inc=1)
        self.height = wx.SpinCtrlDouble(self, min=8, max=200, initial=height, inc=1)
        grid = wx.FlexGridSizer(2, 2, 8, 8)
        grid.AddMany([(wx.StaticText(self, label="Width"), 0, wx.ALIGN_CENTER_VERTICAL), (self.width, 1, wx.EXPAND), (wx.StaticText(self, label="Height"), 0, wx.ALIGN_CENTER_VERTICAL), (self.height, 1, wx.EXPAND)])
        grid.AddGrowableCol(1, 1)
        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(grid, 1, wx.EXPAND | wx.ALL, 12)
        root.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 12)
        self.SetSizerAndFit(root)

    def values(self): return [self.width.GetValue(), self.height.GetValue()]


class ScreenPreviewFrame(wx.Frame):
    """Read-only, data-free visual preview of a validated screen definition."""

    def __init__(self, definition):
        title = definition.form.get("title", definition.form_name)
        super().__init__(None, title="Screen Preview - {}".format(title), size=(1000, 700))
        self.canvas = ScreenCanvas(self, ScreenDesignerModel(definition))
        self.canvas.show_grid = False
        self.canvas.Enable(False)
        self.Bind(wx.EVT_SHOW, self.on_show)

    def on_show(self, event):
        if event.IsShown(): wx.CallAfter(self.canvas.fit_form)
        event.Skip()


def open_screen_preview(definition):
    preview = ScreenPreviewFrame(definition)
    preview.Show()
    return preview


class ScreenDesignerFrame(wx.Frame):
    def __init__(self, definition_path, preview_handler=None, starter_definition_path=None, allowed_directory=None, audit_hook=None):
        self.path = Path(definition_path)
        self.loader = ScreenDefinitionLoader()
        definition = self.loader.load(self.path)
        self.model = ScreenDesignerModel(definition, self.loader)
        super().__init__(None, title="JSForm Screen Designer - {}".format(definition.form.get("title", definition.form_name)), size=(1500, 900))
        self.preview_handler = preview_handler or open_screen_preview
        self.starter_definition_path = Path(starter_definition_path) if starter_definition_path else None
        self.allowed_directory = Path(allowed_directory).resolve() if allowed_directory else None
        self.audit_hook = audit_hook
        self.clipboard = []
        self.property_controls = {}
        self.CreateStatusBar()
        self.build_menu_bar()
        self.build_interface()
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_MENU, lambda event: self.delete_selected(), id=wx.ID_DELETE)
        self.refresh_control_list()
        self.canvas.fit_form()
        self.on_selection(next(iter(self.model.controls), None))
        self.Centre()

    def audit(self, action, detail=None):
        if self.audit_hook:
            self.audit_hook(action, self.path.name, detail)

    def add_menu_item(self, menu, label, handler, item_id=wx.ID_ANY, kind=wx.ITEM_NORMAL):
        item = menu.Append(item_id, label, kind=kind)
        self.Bind(wx.EVT_MENU, handler, item)
        return item

    def build_menu_bar(self):
        bar = wx.MenuBar()
        file_menu = wx.Menu()
        self.add_menu_item(file_menu, "&Open...\tCtrl+O", self.on_open, wx.ID_OPEN)
        self.add_menu_item(file_menu, "&Save\tCtrl+S", self.on_save, wx.ID_SAVE)
        self.add_menu_item(file_menu, "Save &As...", self.on_save_as, wx.ID_SAVEAS)
        file_menu.AppendSeparator()
        self.add_menu_item(file_menu, "Restore &Starter", self.on_restore_starter)
        self.add_menu_item(file_menu, "Restore &Previous", self.on_restore_previous)
        file_menu.AppendSeparator()
        self.add_menu_item(file_menu, "&Close", lambda event: self.Close(), wx.ID_CLOSE)
        bar.Append(file_menu, "&File")
        edit = wx.Menu()
        self.add_menu_item(edit, "&Undo\tCtrl+Z", self.on_undo, wx.ID_UNDO)
        self.add_menu_item(edit, "&Redo\tCtrl+Y", self.on_redo, wx.ID_REDO)
        edit.AppendSeparator()
        self.add_menu_item(edit, "&Copy\tCtrl+C", self.on_copy, wx.ID_COPY)
        self.add_menu_item(edit, "&Paste\tCtrl+V", self.on_paste, wx.ID_PASTE)
        self.add_menu_item(edit, "D&uplicate\tCtrl+D", self.on_duplicate)
        self.add_menu_item(edit, "&Delete\tDel", lambda event: self.delete_selected(), wx.ID_DELETE)
        bar.Append(edit, "&Edit")
        insert = wx.Menu()
        for control_type in CONTROL_TYPES:
            self.add_menu_item(insert, control_type, lambda event, value=control_type: self.add_control(value))
        bar.Append(insert, "&Insert")
        layout = wx.Menu()
        for label, edge in (("Align Left", "left"), ("Align Right", "right"), ("Align Top", "top"), ("Align Bottom", "bottom")):
            self.add_menu_item(layout, label, lambda event, value=edge: self.apply_alignment(value))
        layout.AppendSeparator()
        self.add_menu_item(layout, "Distribute Across", lambda event: self.apply_distribution("horizontal"))
        self.add_menu_item(layout, "Distribute Down", lambda event: self.apply_distribution("vertical"))
        layout.AppendSeparator()
        self.add_menu_item(layout, "Screen Size...", self.on_form_size)
        bar.Append(layout, "&Layout")
        tools = wx.Menu()
        self.add_menu_item(tools, "&Preview\tF5", self.on_preview)
        self.add_menu_item(tools, "&Validate", self.on_validate)
        bar.Append(tools, "&Tools")
        self.SetMenuBar(bar)

    def toolbar_button(self, parent, sizer, label, handler):
        button = wx.Button(parent, label=label)
        button.Bind(wx.EVT_BUTTON, handler)
        sizer.Add(button, 0, wx.RIGHT, 6)
        return button

    def build_interface(self):
        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)
        first = wx.BoxSizer(wx.HORIZONTAL)
        for label, handler in (("Open", self.on_open), ("Save", self.on_save), ("Undo", self.on_undo), ("Redo", self.on_redo), ("Preview", self.on_preview), ("Validate", self.on_validate)):
            self.toolbar_button(panel, first, label, handler)
        first.Add(wx.StaticText(panel, label="Zoom:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        self.zoom_choice = wx.Choice(panel, choices=["Fit Form", "50%", "75%", "100%", "125%", "150%", "200%"])
        self.zoom_choice.SetSelection(0)
        self.zoom_choice.Bind(wx.EVT_CHOICE, self.on_zoom)
        first.Add(self.zoom_choice, 0, wx.LEFT | wx.RIGHT, 5)
        self.snap_check = wx.CheckBox(panel, label="Snap to grid")
        self.snap_check.Bind(wx.EVT_CHECKBOX, self.on_snap)
        first.Add(self.snap_check, 0, wx.ALIGN_CENTER_VERTICAL)
        root.Add(first, 0, wx.EXPAND | wx.ALL, 6)
        second = wx.BoxSizer(wx.HORIZONTAL)
        for label, handler in (("Align Left", lambda e: self.apply_alignment("left")), ("Align Right", lambda e: self.apply_alignment("right")), ("Align Top", lambda e: self.apply_alignment("top")), ("Align Bottom", lambda e: self.apply_alignment("bottom")), ("Distribute Across", lambda e: self.apply_distribution("horizontal")), ("Distribute Down", lambda e: self.apply_distribution("vertical")), ("Screen Size", self.on_form_size), ("Delete", lambda e: self.delete_selected())):
            self.toolbar_button(panel, second, label, handler)
        self.position_text = wx.StaticText(panel, label="")
        second.Add(self.position_text, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
        root.Add(second, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        splitter = wx.SplitterWindow(panel, style=wx.SP_LIVE_UPDATE)
        left_center = wx.SplitterWindow(splitter, style=wx.SP_LIVE_UPDATE)
        left = wx.Panel(left_center)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        left_sizer.Add(wx.StaticText(left, label="Screen Controls"), 0, wx.BOTTOM, 4)
        self.control_list = wx.ListBox(left, style=wx.LB_EXTENDED)
        self.control_list.Bind(wx.EVT_LISTBOX, self.on_list_selection)
        self.control_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_list_double_click)
        left_sizer.Add(self.control_list, 1, wx.EXPAND | wx.BOTTOM, 8)
        left_sizer.Add(wx.StaticText(left, label="Add Control"), 0, wx.BOTTOM, 4)
        self.type_choice = wx.Choice(left, choices=list(CONTROL_TYPES))
        self.type_choice.SetStringSelection("StaticText")
        left_sizer.Add(self.type_choice, 0, wx.EXPAND | wx.BOTTOM, 5)
        add = wx.Button(left, label="Add Selected Control")
        add.Bind(wx.EVT_BUTTON, lambda event: self.add_control(self.type_choice.GetStringSelection()))
        left_sizer.Add(add, 0, wx.EXPAND)
        left.SetSizer(left_sizer)
        self.canvas = ScreenCanvas(left_center, self.model, self.on_selection)
        left_center.SplitVertically(left, self.canvas, 260)
        left_center.SetMinimumPaneSize(190)
        properties = wx.ScrolledWindow(splitter)
        properties.SetScrollRate(5, 5)
        property_sizer = wx.BoxSizer(wx.VERTICAL)
        property_sizer.Add(wx.StaticText(properties, label="Properties"), 0, wx.ALL, 6)
        grid = wx.FlexGridSizer(0, 2, 6, 6)
        grid.AddGrowableCol(1, 1)
        for key, label in (("x", "X"), ("y", "Y"), ("width", "Width"), ("height", "Height")):
            control = wx.SpinCtrlDouble(properties, min=0, max=1000, inc=1)
            control.Bind(wx.EVT_SPINCTRLDOUBLE, self.on_geometry_change)
            control.Bind(wx.EVT_KILL_FOCUS, self.on_geometry_change)
            self.property_controls[key] = control
            grid.Add(wx.StaticText(properties, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(control, 1, wx.EXPAND)
        for key, label in (("label", "Label"), ("tooltip", "Tooltip")):
            control = wx.TextCtrl(properties)
            control.Bind(wx.EVT_KILL_FOCUS, lambda event, value=key: self.on_text_property(event, value))
            self.property_controls[key] = control
            grid.Add(wx.StaticText(properties, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(control, 1, wx.EXPAND)
        self.property_controls["fontface"] = wx.Choice(
            properties, choices=sorted(wx.FontEnumerator.GetFacenames())
        )
        self.property_controls["fontface"].Bind(
            wx.EVT_CHOICE, lambda event: self.on_text_property(event, "fontface")
        )
        grid.Add(wx.StaticText(properties, label="Font"), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.property_controls["fontface"], 1, wx.EXPAND)
        self.property_controls["fontsize"] = wx.SpinCtrl(properties, min=6, max=72, initial=10)
        self.property_controls["fontsize"].Bind(
            wx.EVT_SPINCTRL, lambda event: self.on_number_property(event, "fontsize")
        )
        grid.Add(wx.StaticText(properties, label="Font size"), 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(self.property_controls["fontsize"], 1, wx.EXPAND)
        for key, label in (("foreground", "Text color"), ("background", "Background")):
            control = wx.ColourPickerCtrl(properties)
            control.Bind(wx.EVT_COLOURPICKER_CHANGED, lambda event, value=key: self.on_color_property(event, value))
            self.property_controls[key] = control
            grid.Add(wx.StaticText(properties, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(control, 1, wx.EXPAND)
        for key, label in (("bold", "Bold"), ("italic", "Italic"), ("readonly", "Read only"), ("required", "Required"), ("hidden", "Hidden")):
            control = wx.CheckBox(properties)
            control.Bind(wx.EVT_CHECKBOX, lambda event, value=key: self.on_boolean_property(event, value))
            self.property_controls[key] = control
            grid.Add(wx.StaticText(properties, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(control, 0)
        property_sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 8)
        self.security_text = wx.StaticText(properties, label="Security: developer controlled")
        self.security_text.Wrap(220)
        property_sizer.Add(self.security_text, 0, wx.EXPAND | wx.ALL, 8)
        properties.SetSizer(property_sizer)
        splitter.SplitVertically(left_center, properties, -280)
        splitter.SetMinimumPaneSize(220)
        root.Add(splitter, 1, wx.EXPAND)
        panel.SetSizer(root)

    def refresh_control_list(self):
        names = list(self.model.controls)
        self.control_list.Set(names)
        for index, name in enumerate(names):
            if name in self.canvas.selected_names: self.control_list.SetSelection(index)

    def on_selection(self, name, activate=False):
        self.model.select(name)
        enabled = name is not None
        for control in self.property_controls.values(): control.Enable(enabled)
        if not name:
            self.position_text.SetLabel("No control selected")
            return
        position, size = self.model.geometry(name)
        values = {"x": position[0], "y": position[1], "width": size[0], "height": size[1]}
        control = self.model.controls[name]
        for key in ("x", "y", "width", "height"): self.property_controls[key].SetValue(values[key])
        self.property_controls["label"].SetValue(str(control.get("label", "")))
        self.property_controls["tooltip"].SetValue(str(control.get("tooltip", "")))
        fontface = str(control.get("fontface", ""))
        self.property_controls["fontface"].SetStringSelection(fontface)
        self.property_controls["fontsize"].SetValue(int(control.get("fontsize", 10)))
        self.property_controls["foreground"].SetColour(control.get("foreground", "#000000"))
        self.property_controls["background"].SetColour(control.get("background", "#FFFFFF"))
        self.property_controls["bold"].SetValue(bool(control.get("bold", False)))
        self.property_controls["italic"].SetValue(bool(control.get("italic", False)))
        self.property_controls["readonly"].SetValue(bool(control.get("readonly", False)))
        self.property_controls["required"].SetValue(bool(control.get("required", False)))
        self.property_controls["hidden"].SetValue(bool(control.get("layout", {}).get("hidden", False)))
        security = control.get("security", {})
        self.security_text.SetLabel("Security: {}".format(", ".join("{}={}".format(k, v) for k, v in security.items()) if security else "none (developer controlled)"))
        self.position_text.SetLabel("{}  Position [{:g}, {:g}]  Size [{:g}, {:g}]".format(name, *position, *size))
        if activate: self.property_controls["label"].SetFocus()

    def on_geometry_change(self, event):
        name = self.model.selected
        if name:
            position = [self.property_controls["x"].GetValue(), self.property_controls["y"].GetValue()]
            size = [self.property_controls["width"].GetValue(), self.property_controls["height"].GetValue()]
            self.model.set_geometry(name, position, size)
            self.canvas.Refresh()
            self.on_selection(name)
        event.Skip()

    def on_text_property(self, event, key):
        if self.model.selected:
            source = event.GetEventObject()
            value = source.GetStringSelection() if isinstance(source, wx.Choice) else source.GetValue()
            try: self.model.set_property(self.model.selected, key, value)
            except (FormDefinitionError, ValueError) as error: wx.MessageBox(str(error), "Invalid property", wx.OK | wx.ICON_ERROR, self)
            self.canvas.Refresh()
        event.Skip()

    def on_number_property(self, event, key):
        if self.model.selected:
            try: self.model.set_property(self.model.selected, key, int(event.GetEventObject().GetValue()))
            except (FormDefinitionError, ValueError) as error: wx.MessageBox(str(error), "Invalid property", wx.OK | wx.ICON_ERROR, self)
            self.canvas.Refresh()

    def on_color_property(self, event, key):
        if self.model.selected:
            color = event.GetColour().GetAsString(wx.C2S_HTML_SYNTAX)
            try: self.model.set_property(self.model.selected, key, color)
            except (FormDefinitionError, ValueError) as error: wx.MessageBox(str(error), "Invalid property", wx.OK | wx.ICON_ERROR, self)
            self.canvas.Refresh()

    def on_boolean_property(self, event, key):
        name = self.model.selected
        if not name: return
        if key == "hidden":
            layout = deepcopy(self.model.controls[name].get("layout", {}))
            if event.IsChecked(): layout["hidden"] = True
            else: layout.pop("hidden", None)
            self.model.set_property(name, "layout", layout or None)
        else: self.model.set_property(name, key, event.IsChecked())
        self.canvas.Refresh()

    def on_list_selection(self, event):
        names = {self.control_list.GetString(index) for index in self.control_list.GetSelections()}
        self.canvas.selected_names = names
        self.on_selection(event.GetString())
        self.canvas.Refresh()

    def on_list_double_click(self, event): self.on_selection(event.GetString(), activate=True)

    def add_control(self, control_type):
        try: name = self.model.add_control(control_type)
        except (FormDefinitionError, ValueError) as error:
            wx.MessageBox(str(error), "Cannot add control", wx.OK | wx.ICON_ERROR, self); return
        self.canvas.selected_names = {name}
        self.refresh_control_list(); self.on_selection(name); self.canvas.Refresh(); self.canvas.SetFocus()

    def selected_names(self): return list(self.canvas.selected_names)

    def apply_alignment(self, edge):
        try: self.model.align_controls(self.selected_names(), edge)
        except ValueError as error: self.SetStatusText(str(error)); return
        self.canvas.Refresh(); self.on_selection(self.model.selected)

    def apply_distribution(self, axis):
        try: self.model.distribute_controls(self.selected_names(), axis)
        except ValueError as error: self.SetStatusText(str(error)); return
        self.canvas.Refresh(); self.on_selection(self.model.selected)

    def on_copy(self, event): self.clipboard = self.model.copy_controls(self.selected_names())
    def on_paste(self, event):
        created = self.model.paste_controls(self.clipboard)
        self.canvas.selected_names = set(created); self.refresh_control_list(); self.on_selection(self.model.selected); self.canvas.Refresh()
    def on_duplicate(self, event): self.clipboard = self.model.copy_controls(self.selected_names()); self.on_paste(event)
    def on_undo(self, event):
        if self.model.undo(): self.canvas.selected_names = {self.model.selected} if self.model.selected else set(); self.refresh_control_list(); self.canvas.refresh_extent(); self.on_selection(self.model.selected)
    def on_redo(self, event):
        if self.model.redo(): self.canvas.selected_names = {self.model.selected} if self.model.selected else set(); self.refresh_control_list(); self.canvas.refresh_extent(); self.on_selection(self.model.selected)

    def delete_selected(self):
        names = self.selected_names()
        if not names: self.SetStatusText("Select a control to delete"); return
        dialog = wx.MessageDialog(self, "Delete {} selected control(s)?".format(len(names)), "Delete screen controls", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        try:
            if dialog.ShowModal() != wx.ID_YES: return
        finally: dialog.Destroy()
        self.model.begin_transaction()
        try:
            for name in names: self.model.delete_control(name)
        finally: self.model.end_transaction()
        self.canvas.selected_names.clear(); self.refresh_control_list(); self.on_selection(None); self.canvas.Refresh()

    def on_zoom(self, event):
        value = self.zoom_choice.GetStringSelection()
        if value == "Fit Form": self.canvas.fit_form()
        else: self.canvas.zoom = int(value.rstrip("%")) / 100; self.canvas.refresh_extent()
    def on_snap(self, event): self.canvas.snap = event.IsChecked()

    def on_form_size(self, event):
        dialog = FormSizeDialog(self, self.model)
        try:
            if dialog.ShowModal() != wx.ID_OK: return
            self.model.set_form_size(dialog.values())
        except ValueError as error: wx.MessageBox(str(error), "Invalid screen size", wx.OK | wx.ICON_ERROR, self)
        finally: dialog.Destroy()
        self.canvas.refresh_extent()

    def on_save(self, event):
        try: self.model.save(self.path); self.audit("SCREEN_DESIGN_SAVED"); self.SetStatusText("Screen definition saved")
        except (FormDefinitionError, OSError) as error: wx.MessageBox(str(error), "Cannot save screen", wx.OK | wx.ICON_ERROR, self)

    def _path_allowed(self, path):
        if not self.allowed_directory: return True
        try: Path(path).resolve().relative_to(self.allowed_directory); return True
        except ValueError: return False

    def on_save_as(self, event):
        dialog = wx.FileDialog(self, "Save screen definition as", defaultDir=str(self.path.parent), defaultFile=self.path.name, wildcard="JSForm screens (*.json)|*.json", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        try:
            if dialog.ShowModal() != wx.ID_OK: return
            target = Path(dialog.GetPath())
        finally: dialog.Destroy()
        if target.suffix.casefold() != ".json": target = target.with_suffix(".json")
        if not self._path_allowed(target): wx.MessageBox("Choose a file inside the approved screen-definition folder.", "Location not allowed", wx.OK | wx.ICON_ERROR, self); return
        old = self.model._snapshot()
        try:
            if target.stem != self.model.form["name"]: self.model.rename_definition(target.stem)
            self.model.save(target)
        except Exception as error:
            self.model.data, self.model.root_name, self.model.selected = old
            wx.MessageBox(str(error), "Cannot save screen", wx.OK | wx.ICON_ERROR, self); return
        self.path = target; self.audit("SCREEN_DESIGN_SAVED_AS"); self.SetTitle("JSForm Screen Designer - {}".format(target.stem))

    def confirm_discard_or_save(self):
        if not self.model.dirty: return True
        dialog = wx.MessageDialog(self, "Save changes to this screen definition?", "Unsaved screen changes", wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
        try: result = dialog.ShowModal()
        finally: dialog.Destroy()
        if result == wx.ID_CANCEL: return False
        if result == wx.ID_YES:
            self.model.save(self.path); self.audit("SCREEN_DESIGN_SAVED")
        return True

    def on_open(self, event):
        if not self.confirm_discard_or_save(): return
        dialog = wx.FileDialog(self, "Open screen definition", defaultDir=str(self.path.parent), wildcard="JSForm screens (*.json)|*.json", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        try:
            if dialog.ShowModal() != wx.ID_OK: return
            target = Path(dialog.GetPath())
        finally: dialog.Destroy()
        if not self._path_allowed(target): wx.MessageBox("That screen is outside the approved folder.", "Location not allowed", wx.OK | wx.ICON_ERROR, self); return
        try: self.loader.load(target)
        except FormDefinitionError as error: wx.MessageBox(str(error), "Cannot open screen", wx.OK | wx.ICON_ERROR, self); return
        replacement = ScreenDesignerFrame(target, self.preview_handler, self.starter_definition_path, self.allowed_directory, self.audit_hook)
        replacement.Show(); self.Destroy()

    def on_preview(self, event):
        try: self.preview_handler(self.model.validated_definition()); self.audit("SCREEN_DESIGN_PREVIEWED")
        except Exception as error: wx.MessageBox(str(error), "Cannot preview screen", wx.OK | wx.ICON_ERROR, self)

    def on_validate(self, event):
        try: self.model.validated_definition(); warnings = self.model.layout_warnings(); self.audit("SCREEN_DESIGN_VALIDATED", str(len(warnings)))
        except (FormDefinitionError, ValueError) as error: wx.MessageBox(str(error), "Screen validation failed", wx.OK | wx.ICON_ERROR, self); return
        if warnings: wx.MessageBox("The screen is valid, but review:\n\n" + "\n".join("- " + item for item in warnings), "Screen validation", wx.OK | wx.ICON_WARNING, self)
        else: wx.MessageBox("The screen definition and layout are valid.", "Screen validation", wx.OK | wx.ICON_INFORMATION, self)

    def on_restore_starter(self, event):
        if not self.starter_definition_path or not self.starter_definition_path.is_file(): self.SetStatusText("No starter definition is available"); return
        dialog = wx.MessageDialog(self, "Replace the current layout with the starter? The file will not change until Save.", "Restore starter", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        try:
            if dialog.ShowModal() != wx.ID_YES: return
        finally: dialog.Destroy()
        try: self.model.replace_definition(self.loader.load(self.starter_definition_path))
        except FormDefinitionError as error: wx.MessageBox(str(error), "Cannot restore starter", wx.OK | wx.ICON_ERROR, self); return
        self.canvas.model = self.model; self.canvas.selected_names = {self.model.selected} if self.model.selected else set(); self.refresh_control_list(); self.canvas.refresh_extent(); self.on_selection(self.model.selected); self.audit("SCREEN_DESIGN_STARTER_LOADED")

    def on_restore_previous(self, event):
        previous = self.path.with_suffix(self.path.suffix + ".bak")
        if not previous.is_file(): self.SetStatusText("No previous saved version exists"); return
        try: self.model.replace_definition(self.loader.load(previous))
        except FormDefinitionError as error: wx.MessageBox(str(error), "Cannot restore previous", wx.OK | wx.ICON_ERROR, self); return
        self.canvas.model = self.model; self.canvas.selected_names = {self.model.selected} if self.model.selected else set(); self.refresh_control_list(); self.canvas.refresh_extent(); self.on_selection(self.model.selected); self.audit("SCREEN_DESIGN_PREVIOUS_LOADED")

    def on_close(self, event):
        if not self.confirm_discard_or_save(): event.Veto(); return
        event.Skip()


def open_screen_designer(definition_path, preview_handler=None, starter_definition_path=None, allowed_directory=None, audit_hook=None):
    application = wx.App.Get() or wx.App(False)
    frame = ScreenDesignerFrame(definition_path, preview_handler, starter_definition_path, allowed_directory, audit_hook)
    frame.Show()
    if not wx.App.Get().IsMainLoopRunning(): application.MainLoop()
    return frame
