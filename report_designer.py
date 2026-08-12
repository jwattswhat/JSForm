"""Initial visual canvas and editing model for JSForm report definitions."""

from copy import deepcopy
from pathlib import Path

import wx

from JSForm.report_definition import (
    ReportDefinitionError,
    ReportDefinitionLoader,
    save_report_definition,
)


PAGE_POINTS = {"letter": (612, 792), "legal": (612, 1008), "a4": (595, 842)}
HANDLE = 7
MINIMUM_SIZE = 4
CONTROL_DEFAULTS = {
    "label": {"size": [140, 20], "label": "New label", "fontsize": 10},
    "line": {"size": [140, 1], "bordercolor": "#808080", "borderwidth": 1},
    "rectangle": {"size": [140, 50], "bordercolor": "#808080", "borderwidth": 1},
}


class ReportDesignerModel:
    def __init__(self, definition, loader=None):
        self.loader = loader or ReportDefinitionLoader()
        self.data = definition.to_dict()
        self.root_name = definition.root_name
        self.selected = None
        self.dirty = False
        self.undo_stack = []
        self.redo_stack = []
        self.transaction_snapshot = None

    def _snapshot(self):
        return deepcopy(self.data), self.selected

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
        old_data, old_selected = self.transaction_snapshot
        self.transaction_snapshot = None
        if old_data != self.data:
            self.undo_stack.append((old_data, old_selected))
            self.undo_stack = self.undo_stack[-100:]
            self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            return False
        self.redo_stack.append(self._snapshot())
        self.data, self.selected = self.undo_stack.pop()
        self.dirty = True
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        self.undo_stack.append(self._snapshot())
        self.data, self.selected = self.redo_stack.pop()
        self.dirty = True
        return True

    @property
    def report(self):
        return self.data[self.root_name]["REPORT"]

    @property
    def controls(self):
        return self.data[self.root_name]["CONTROLS"]

    def select(self, name):
        if name is not None and name not in self.controls:
            raise KeyError(name)
        self.selected = name

    def move(self, name, dx, dy):
        self._record_change()
        control = self.controls[name]
        x, y = control["position"]
        width, height = control["size"]
        band_height = self.report["bands"][control["band"]]["height"]
        control["position"] = [
            min(max(0, x + dx), max(0, self.content_width - width)),
            min(max(0, y + dy), max(0, band_height - height)),
        ]
        self.dirty = True

    def resize(self, name, dw, dh):
        self._record_change()
        control = self.controls[name]
        x, y = control["position"]
        width, height = control["size"]
        band_height = self.report["bands"][control["band"]]["height"]
        control["size"] = [
            max(MINIMUM_SIZE, min(width + dw, self.content_width - x)),
            max(MINIMUM_SIZE, min(height + dh, band_height - y)),
        ]
        self.dirty = True

    def set_geometry(self, name, position=None, size=None):
        self._record_change()
        control = self.controls[name]
        if position is not None:
            x, y = position
            width, height = control["size"]
            band_height = self.report["bands"][control["band"]]["height"]
            control["position"] = [
                min(max(0, x), max(0, self.content_width - width)),
                min(max(0, y), max(0, band_height - height)),
            ]
        if size is not None:
            width, height = size
            x, y = control["position"]
            band_height = self.report["bands"][control["band"]]["height"]
            control["size"] = [
                max(MINIMUM_SIZE, min(width, self.content_width - x)),
                max(MINIMUM_SIZE, min(height, band_height - y)),
            ]
        self.dirty = True

    def snap_to_grid(self, name, grid_size=6):
        if grid_size <= 0:
            raise ValueError("Grid size must be positive")
        control = self.controls[name]
        x, y = control["position"]
        snapped = [round(x / grid_size) * grid_size, round(y / grid_size) * grid_size]
        self.set_geometry(name, position=snapped)

    def set_property(self, name, key, value):
        candidate = deepcopy(self.data)
        candidate_control = candidate[self.root_name]["CONTROLS"][name]
        if value is None:
            candidate_control.pop(key, None)
        else:
            candidate_control[key] = value
        validated = self.loader.from_dict(candidate)
        self._record_change()
        self.data = validated.to_dict()
        self.dirty = True

    def unique_control_name(self, prefix):
        if prefix not in self.controls:
            return prefix
        number = 2
        while f"{prefix}{number}" in self.controls:
            number += 1
        return f"{prefix}{number}"

    def add_control(self, control_type, band=None, name=None):
        if control_type not in CONTROL_DEFAULTS:
            raise ValueError(f"Unsupported designer control type: {control_type}")
        band = band or next(iter(self.report["bands"]))
        if band not in self.report["bands"]:
            raise ValueError(f"Unknown report band: {band}")
        prefix = {"label": "Label", "line": "Line", "rectangle": "Rectangle"}[control_type]
        name = name or self.unique_control_name(prefix)
        if name in self.controls:
            raise ValueError(f"A control named {name} already exists")
        control = deepcopy(CONTROL_DEFAULTS[control_type])
        band_height = self.report["bands"][band]["height"]
        control["size"][1] = min(control["size"][1], max(MINIMUM_SIZE, band_height - 4))
        control.update({"type": control_type, "band": band, "position": [4, 4]})
        candidate = deepcopy(self.data)
        candidate[self.root_name]["CONTROLS"][name] = control
        validated = self.loader.from_dict(candidate)
        self._record_change()
        self.data = validated.to_dict()
        self.selected = name
        self.dirty = True
        return name

    def add_bound_field(self, collection, field, label, data_type="text", band=None):
        band = band or next(iter(self.report["bands"]))
        if band not in self.report["bands"]:
            raise ValueError(f"Unknown report band: {band}")
        control_type = "image" if data_type == "image" else "text"
        name = self.unique_control_name(field)
        band_height = self.report["bands"][band]["height"]
        height = min(64 if control_type == "image" else 20, max(MINIMUM_SIZE, band_height - 4))
        control = {
            "type": control_type,
            "band": band,
            "position": [4, 4],
            "size": [64 if control_type == "image" else 160, height],
            "collection": collection,
            "field": field,
        }
        if control_type == "text":
            control["fontsize"] = 10
            if data_type in ("integer", "decimal", "currency", "date", "time", "datetime", "boolean", "phone", "address"):
                control["format"] = data_type
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

    def replace_definition(self, definition):
        self._record_change()
        self.data = definition.to_dict()
        self.root_name = definition.root_name
        self.selected = next(iter(self.controls), None)
        self.dirty = True

    @property
    def page_size(self):
        width, height = PAGE_POINTS[self.report["pagesize"]]
        return (height, width) if self.report["orientation"] == "landscape" else (width, height)

    @property
    def content_width(self):
        width, _ = self.page_size
        margins = self.report["margins"]
        return width - margins["left"] - margins["right"]

    def validated_definition(self):
        return self.loader.from_dict(deepcopy(self.data))

    def layout_warnings(self):
        warnings = []
        by_band = {}
        for name, control in self.controls.items():
            x, y = control["position"]
            width, height = control["size"]
            band_height = self.report["bands"][control["band"]]["height"]
            if x + width > self.content_width or y + height > band_height:
                warnings.append(f"{name} extends outside its report section")
            if control["type"] in ("text", "image"):
                if not control.get("collection") or not control.get("field"):
                    warnings.append(f"{name} is missing its data binding")
            by_band.setdefault(control["band"], []).append((name, x, y, width, height))
        for controls in by_band.values():
            for index, first in enumerate(controls):
                for second in controls[index + 1:]:
                    if self._rectangles_overlap(first[1:], second[1:]):
                        warnings.append(f"{first[0]} overlaps {second[0]}")
        return warnings

    def align_controls(self, names, edge):
        names = list(dict.fromkeys(names))
        if len(names) < 2:
            raise ValueError("Select at least two controls to align")
        controls = [self.controls[name] for name in names]
        if len({control["band"] for control in controls}) != 1:
            raise ValueError("Controls must be in the same report section to align")
        self._record_change()
        if edge == "left":
            target = min(control["position"][0] for control in controls)
            for control in controls:
                control["position"][0] = target
        elif edge == "right":
            target = max(control["position"][0] + control["size"][0] for control in controls)
            for control in controls:
                control["position"][0] = target - control["size"][0]
        elif edge == "top":
            target = min(control["position"][1] for control in controls)
            for control in controls:
                control["position"][1] = target
        elif edge == "bottom":
            target = max(control["position"][1] + control["size"][1] for control in controls)
            for control in controls:
                control["position"][1] = target - control["size"][1]
        else:
            raise ValueError(f"Unknown alignment edge: {edge}")
        self.dirty = True

    def distribute_controls(self, names, axis):
        names = list(dict.fromkeys(names))
        if len(names) < 3:
            raise ValueError("Select at least three controls to distribute")
        controls = [(name, self.controls[name]) for name in names]
        if len({control["band"] for _, control in controls}) != 1:
            raise ValueError("Controls must be in the same report section to distribute")
        coordinate = 0 if axis == "horizontal" else 1
        dimension = coordinate
        controls.sort(key=lambda item: item[1]["position"][coordinate])
        first = controls[0][1]["position"][coordinate]
        last_control = controls[-1][1]
        last_edge = last_control["position"][coordinate] + last_control["size"][dimension]
        occupied = sum(control["size"][dimension] for _, control in controls)
        gap = (last_edge - first - occupied) / (len(controls) - 1)
        self._record_change()
        cursor = first
        for _, control in controls:
            control["position"][coordinate] = round(cursor)
            cursor += control["size"][dimension] + gap
        self.dirty = True

    def set_band_height(self, band_name, height):
        if band_name not in self.report["bands"]:
            raise ValueError(f"Unknown report section: {band_name}")
        height = max(MINIMUM_SIZE, min(float(height), 2000))
        required = max(
            (
                control["position"][1] + control["size"][1]
                for control in self.controls.values()
                if control["band"] == band_name
            ),
            default=MINIMUM_SIZE,
        )
        if height < required:
            raise ValueError(
                f"{band_name} must be at least {required:g} points high to contain its controls"
            )
        self._record_change()
        self.report["bands"][band_name]["height"] = height
        self.dirty = True

    def set_repeater_item_geometry(self, control_name, item_name, position=None, size=None):
        control = self.controls[control_name]
        if control["type"] != "repeater":
            raise ValueError(f"{control_name} is not a repeating detail control")
        item = next((item for item in control["items"] if item["name"] == item_name), None)
        if item is None:
            raise ValueError(f"Unknown detail column: {item_name}")
        candidate = deepcopy(self.data)
        candidate_control = candidate[self.root_name]["CONTROLS"][control_name]
        candidate_item = next(
            value for value in candidate_control["items"] if value["name"] == item_name
        )
        if position is not None:
            candidate_item["position"] = [max(0, position[0]), max(0, position[1])]
        if size is not None:
            candidate_item["size"] = [max(MINIMUM_SIZE, size[0]), max(MINIMUM_SIZE, size[1])]
        if candidate_item["position"][0] + candidate_item["size"][0] > control["size"][0]:
            raise ValueError(f"{item_name} extends beyond the detail row width")
        if candidate_item["position"][1] + candidate_item["size"][1] > control["itemheight"]:
            raise ValueError(f"{item_name} extends beyond the detail row height")
        validated = self.loader.from_dict(candidate)
        self._record_change()
        self.data = validated.to_dict()
        self.dirty = True

    def set_page_setup(self, pagesize, orientation, margins):
        candidate = deepcopy(self.data)
        settings = candidate[self.root_name]["REPORT"]
        settings["pagesize"] = pagesize
        settings["orientation"] = orientation
        settings["margins"] = dict(margins)
        validated = self.loader.from_dict(candidate)
        candidate_model = ReportDesignerModel(validated, loader=self.loader)
        widest = max(
            (control["position"][0] + control["size"][0] for control in candidate_model.controls.values()),
            default=0,
        )
        if widest > candidate_model.content_width:
            raise ValueError(
                f"Existing controls require {widest:g} points, but the printable width would be "
                f"{candidate_model.content_width:g} points"
            )
        self._record_change()
        self.data = validated.to_dict()
        self.dirty = True

    @staticmethod
    def _rectangles_overlap(first, second):
        ax, ay, aw, ah = first
        bx, by, bw, bh = second
        return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah

    def save(self, path):
        definition = self.validated_definition()
        save_report_definition(definition, path)
        self.dirty = False
        return definition


class ReportCanvas(wx.ScrolledWindow):
    def __init__(self, parent, model, on_selection=None, on_delete=None, scale=1.0):
        super().__init__(parent, style=wx.BORDER_SIMPLE | wx.WANTS_CHARS)
        self.model = model
        self.on_selection = on_selection
        self.on_delete = on_delete
        self.scale = scale
        self.drag_origin = None
        self.drag_mode = None
        self.snap_enabled = False
        self.grid_size = 6
        self.selected_names = set()
        self.selected_band = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(wx.Colour(170, 170, 170))
        self.SetScrollRate(10, 10)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.Bind(wx.EVT_MOTION, self.on_motion)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key)
        self.refresh_extent()

    def refresh_extent(self):
        width, height = self.model.page_size
        self.SetVirtualSize((int(width * self.scale + 48), int(height * self.scale + 48)))
        self.Refresh()

    def fit_page(self):
        client_width, client_height = self.GetClientSize()
        page_width, page_height = self.model.page_size
        if client_width <= 60 or client_height <= 60:
            return
        self.scale = max(
            0.25,
            min((client_width - 48) / page_width, (client_height - 48) / page_height),
        )
        self.refresh_extent()
        self.Scroll(0, 0)

    def reveal_control(self, name):
        """Scroll the selected control into view and repaint it."""
        if not name:
            return
        rect = self.control_rect(self.model.controls[name])
        view_start_x, view_start_y = self.GetViewStart()
        pixels_x, pixels_y = self.GetScrollPixelsPerUnit()
        client_width, client_height = self.GetClientSize()
        current_x = view_start_x * pixels_x
        current_y = view_start_y * pixels_y
        target_x = current_x
        target_y = current_y
        if rect.x < current_x:
            target_x = max(0, rect.x - 20)
        elif rect.right > current_x + client_width:
            target_x = max(0, rect.right - client_width + 20)
        if rect.y < current_y:
            target_y = max(0, rect.y - 20)
        elif rect.bottom > current_y + client_height:
            target_y = max(0, rect.bottom - client_height + 20)
        self.Scroll(target_x // pixels_x, target_y // pixels_y)
        self.Refresh()

    def page_origin(self):
        return 24, 24

    def band_positions(self):
        result = {}
        y = self.model.report["margins"]["top"]
        for name, band in self.model.report["bands"].items():
            result[name] = y
            y += band["height"]
        return result

    def control_rect(self, control):
        page_x, page_y = self.page_origin()
        margins = self.model.report["margins"]
        band_y = self.band_positions()[control["band"]]
        x, y = control["position"]
        width, height = control["size"]
        return wx.Rect(
            int(page_x + (margins["left"] + x) * self.scale),
            int(page_y + (band_y + y) * self.scale),
            max(1, int(width * self.scale)), max(1, int(height * self.scale)),
        )

    def hit_test(self, point):
        for name, control in reversed(tuple(self.model.controls.items())):
            rect = self.control_rect(control)
            handle = wx.Rect(rect.right - HANDLE, rect.bottom - HANDLE, HANDLE * 2, HANDLE * 2)
            if handle.Contains(point):
                return name, "resize"
            if rect.Contains(point):
                return name, "move"
        return None, None

    def on_left_down(self, event):
        position = self.CalcUnscrolledPosition(event.GetPosition())
        name, mode = self.hit_test(position)
        if name and event.ControlDown():
            if name in self.selected_names:
                self.selected_names.remove(name)
            else:
                self.selected_names.add(name)
            name = name if name in self.selected_names else next(iter(self.selected_names), None)
        else:
            self.selected_names = {name} if name else set()
        self.model.select(name)
        self.drag_origin = position if name else None
        self.drag_mode = mode
        if name:
            self.model.begin_transaction()
            self.CaptureMouse()
        if self.on_selection:
            self.on_selection(name)
        self.SetFocus()
        self.Refresh()

    def on_motion(self, event):
        if not self.drag_origin or not event.Dragging() or not event.LeftIsDown():
            return
        position = self.CalcUnscrolledPosition(event.GetPosition())
        dx = round((position.x - self.drag_origin.x) / self.scale)
        dy = round((position.y - self.drag_origin.y) / self.scale)
        if dx or dy:
            if self.drag_mode == "resize":
                self.model.resize(self.model.selected, dx, dy)
            else:
                self.model.move(self.model.selected, dx, dy)
            self.drag_origin = position
            self.Refresh()

    def on_left_up(self, event):
        if self.HasCapture():
            self.ReleaseMouse()
        self.drag_origin = None
        self.drag_mode = None
        if self.snap_enabled and self.model.selected:
            self.model.snap_to_grid(self.model.selected, self.grid_size)
        self.model.end_transaction()
        if self.on_selection:
            self.on_selection(self.model.selected)
        self.Refresh()

    def on_key(self, event):
        if not self.model.selected:
            event.Skip()
            return
        key = event.GetKeyCode()
        if key in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            if self.on_delete:
                self.on_delete()
            return
        movement = {
            wx.WXK_LEFT: (-1, 0), wx.WXK_RIGHT: (1, 0),
            wx.WXK_UP: (0, -1), wx.WXK_DOWN: (0, 1),
        }.get(key)
        if not movement:
            event.Skip()
            return
        amount = 10 if event.ShiftDown() else 1
        dx, dy = movement[0] * amount, movement[1] * amount
        if event.ControlDown():
            self.model.resize(self.model.selected, dx, dy)
        else:
            self.model.move(self.model.selected, dx, dy)
        self.Refresh()

    def on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        self.PrepareDC(dc)
        dc.Clear()
        page_x, page_y = self.page_origin()
        width, height = self.model.page_size
        page = wx.Rect(page_x, page_y, int(width * self.scale), int(height * self.scale))
        dc.SetPen(wx.Pen(wx.Colour(100, 100, 100), 1))
        dc.SetBrush(wx.Brush(wx.WHITE))
        dc.DrawRectangle(page)
        margins = self.model.report["margins"]
        content_x = page_x + int(margins["left"] * self.scale)
        content_width = int(self.model.content_width * self.scale)
        positions = self.band_positions()
        for band_name, band in self.model.report["bands"].items():
            top = page_y + int(positions[band_name] * self.scale)
            band_height = int(band["height"] * self.scale)
            band_selected = band_name == self.selected_band
            dc.SetPen(wx.Pen(
                wx.Colour(230, 145, 30) if band_selected else wx.Colour(185, 195, 205),
                3 if band_selected else 1,
                wx.PENSTYLE_SOLID if band_selected else wx.PENSTYLE_DOT,
            ))
            dc.SetBrush(
                wx.Brush(wx.Colour(255, 246, 220)) if band_selected else wx.TRANSPARENT_BRUSH
            )
            dc.DrawRectangle(content_x, top, content_width, band_height)
            dc.SetTextForeground(
                wx.Colour(150, 80, 0) if band_selected else wx.Colour(90, 105, 120)
            )
            dc.SetFont(wx.Font(7, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            dc.DrawText(band_name, content_x + 2, top + 1)
            if self.snap_enabled:
                dc.SetPen(wx.Pen(wx.Colour(225, 230, 235), 1))
                grid = max(2, int(self.grid_size * self.scale))
                for x in range(content_x, content_x + content_width + 1, grid):
                    dc.DrawPoint(x, top + band_height // 2)
        for name, control in self.model.controls.items():
            rect = self.control_rect(control)
            selected = name in self.selected_names
            dc.SetPen(wx.Pen(wx.Colour(0, 92, 190) if selected else wx.Colour(55, 105, 145), 3 if selected else 2))
            dc.SetBrush(wx.Brush(wx.Colour(214, 234, 255) if selected else wx.Colour(235, 246, 255)))
            dc.DrawRectangle(rect)
            dc.SetTextForeground(wx.BLACK)
            dc.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            label = control.get("label") or f"{name}: {control.get('field', control['type'])}"
            dc.SetClippingRegion(rect)
            dc.DrawText(label, rect.x + 3, rect.y + 3)
            dc.DestroyClippingRegion()
            if control["type"] == "repeater":
                self.draw_repeater_items(dc, rect, control, selected)
            if selected:
                dc.SetBrush(wx.Brush(wx.Colour(0, 100, 220)))
                dc.DrawRectangle(rect.right - HANDLE // 2, rect.bottom - HANDLE // 2, HANDLE, HANDLE)

    def draw_repeater_items(self, dc, repeater_rect, control, selected):
        origin_x = repeater_rect.x
        origin_y = repeater_rect.y
        for item in control["items"]:
            x, y = item["position"]
            width, height = item["size"]
            rect = wx.Rect(
                int(origin_x + x * self.scale), int(origin_y + y * self.scale),
                max(1, int(width * self.scale)), max(1, int(height * self.scale)),
            )
            dc.SetPen(wx.Pen(wx.Colour(90, 145, 180), 1, wx.PENSTYLE_DOT))
            dc.SetBrush(wx.Brush(wx.Colour(250, 253, 255)))
            dc.DrawRectangle(rect)
            dc.SetTextForeground(wx.Colour(35, 70, 95))
            dc.SetFont(wx.Font(7, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            dc.SetClippingRegion(rect)
            dc.DrawText(item["name"], rect.x + 2, rect.y + 1)
            dc.DestroyClippingRegion()


class RepeaterItemsDialog(wx.Dialog):
    def __init__(self, parent, model, control_name):
        super().__init__(parent, title="Edit Detail Columns", size=(470, 330))
        self.model = model
        self.control_name = control_name
        self.items = model.controls[control_name]["items"]
        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(
            wx.StaticText(panel, label="Choose a detail item, then adjust its position and size."),
            0, wx.ALL, 10,
        )
        body = wx.BoxSizer(wx.HORIZONTAL)
        self.item_list = wx.ListBox(panel, choices=[item["name"] for item in self.items])
        self.item_list.Bind(wx.EVT_LISTBOX, self.on_item_selection)
        body.Add(self.item_list, 1, wx.EXPAND | wx.RIGHT, 10)
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=8)
        self.editors = {}
        for key, label in (("x", "X"), ("y", "Y"), ("width", "Width"), ("height", "Height")):
            grid.Add(wx.StaticText(panel, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            editor = wx.SpinCtrlDouble(panel, min=0, max=2000, initial=0, inc=1)
            editor.SetDigits(0)
            self.editors[key] = editor
            grid.Add(editor, 0)
        body.Add(grid, 0, wx.EXPAND)
        layout.Add(body, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.AddStretchSpacer()
        apply_button = wx.Button(panel, label="Apply")
        apply_button.Bind(wx.EVT_BUTTON, self.on_apply)
        buttons.Add(apply_button, 0, wx.RIGHT, 8)
        close_button = wx.Button(panel, wx.ID_CLOSE, "Close")
        close_button.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_CLOSE))
        buttons.Add(close_button, 0)
        layout.Add(buttons, 0, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(layout)
        if self.items:
            self.item_list.SetSelection(0)
            self.load_item(0)

    def on_item_selection(self, event):
        self.load_item(event.GetSelection())

    def load_item(self, index):
        item = self.model.controls[self.control_name]["items"][index]
        x, y = item["position"]
        width, height = item["size"]
        for key, value in (("x", x), ("y", y), ("width", width), ("height", height)):
            self.editors[key].SetValue(value)

    def on_apply(self, event):
        index = self.item_list.GetSelection()
        if index == wx.NOT_FOUND:
            return
        item = self.model.controls[self.control_name]["items"][index]
        try:
            self.model.set_repeater_item_geometry(
                self.control_name, item["name"],
                position=[self.editors["x"].GetValue(), self.editors["y"].GetValue()],
                size=[self.editors["width"].GetValue(), self.editors["height"].GetValue()],
            )
        except ValueError as error:
            wx.MessageBox(str(error), "Cannot resize detail column", wx.OK | wx.ICON_WARNING, self)
            return
        self.GetParent().canvas.Refresh()
        self.GetParent().SetStatusText(f"Updated detail column {item['name']}")


class PageSetupDialog(wx.Dialog):
    def __init__(self, parent, model):
        super().__init__(parent, title="Page Setup", size=(370, 350))
        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, vgap=10, hgap=10)
        grid.AddGrowableCol(1, 1)
        grid.Add(wx.StaticText(panel, label="Paper size"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.pagesize = wx.Choice(panel, choices=["Letter", "Legal", "A4"])
        self.pagesize.SetStringSelection(model.report["pagesize"].upper() if model.report["pagesize"] == "a4" else model.report["pagesize"].title())
        grid.Add(self.pagesize, 1, wx.EXPAND)
        grid.Add(wx.StaticText(panel, label="Orientation"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.orientation = wx.Choice(panel, choices=["Portrait", "Landscape"])
        self.orientation.SetStringSelection(model.report["orientation"].title())
        grid.Add(self.orientation, 1, wx.EXPAND)
        self.margin_editors = {}
        for key in ("top", "right", "bottom", "left"):
            grid.Add(wx.StaticText(panel, label=f"{key.title()} margin"), 0, wx.ALIGN_CENTER_VERTICAL)
            editor = wx.SpinCtrlDouble(
                panel, min=0, max=2000, initial=model.report["margins"][key], inc=1,
            )
            editor.SetDigits(0)
            self.margin_editors[key] = editor
            grid.Add(editor, 1, wx.EXPAND)
        layout.Add(grid, 1, wx.EXPAND | wx.ALL, 15)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.AddStretchSpacer()
        ok_button = wx.Button(panel, wx.ID_OK, "OK")
        ok_button.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_OK))
        buttons.Add(ok_button, 0, wx.RIGHT, 8)
        cancel_button = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        cancel_button.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_CANCEL))
        buttons.Add(cancel_button, 0)
        layout.Add(buttons, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        panel.SetSizer(layout)

    def values(self):
        return (
            self.pagesize.GetStringSelection().casefold(),
            self.orientation.GetStringSelection().casefold(),
            {key: editor.GetValue() for key, editor in self.margin_editors.items()},
        )


class ReportDesignerFrame(wx.Frame):
    def __init__(
        self, definition_path, dataset_contract=None, preview_handler=None,
        starter_definition_path=None,
    ):
        self.path = Path(definition_path)
        definition = ReportDefinitionLoader().load(self.path)
        self.model = ReportDesignerModel(definition)
        self.dataset_contract = dataset_contract
        self.preview_handler = preview_handler
        self.starter_definition_path = (
            Path(starter_definition_path) if starter_definition_path else None
        )
        if dataset_contract is not None:
            dataset_contract.validate_definition(definition)
        super().__init__(None, title=f"JSForm Report Designer - {definition.title}", size=(1100, 850))
        self.build_menu_bar()
        panel = wx.Panel(self)
        toolbar = wx.BoxSizer(wx.HORIZONTAL)
        primary_toolbar = wx.BoxSizer(wx.HORIZONTAL)
        save_button = wx.Button(panel, label="Save")
        save_button.Bind(wx.EVT_BUTTON, self.on_save)
        primary_toolbar.Add(save_button, 0, wx.ALL, 5)
        undo_button = wx.Button(panel, label="Undo")
        undo_button.Bind(wx.EVT_BUTTON, self.on_undo)
        primary_toolbar.Add(undo_button, 0, wx.TOP | wx.BOTTOM | wx.RIGHT, 5)
        redo_button = wx.Button(panel, label="Redo")
        redo_button.Bind(wx.EVT_BUTTON, self.on_redo)
        primary_toolbar.Add(redo_button, 0, wx.TOP | wx.BOTTOM | wx.RIGHT, 5)
        if preview_handler is not None:
            preview_button = wx.Button(panel, label="Preview")
            preview_button.Bind(wx.EVT_BUTTON, self.on_preview)
            primary_toolbar.Add(preview_button, 0, wx.TOP | wx.BOTTOM | wx.RIGHT, 5)
        validate_button = wx.Button(panel, label="Validate")
        validate_button.Bind(wx.EVT_BUTTON, self.on_validate)
        primary_toolbar.Add(validate_button, 0, wx.TOP | wx.BOTTOM | wx.RIGHT, 5)
        primary_toolbar.Add(wx.StaticText(panel, label="Zoom:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 6)
        self.zoom_choice = wx.Choice(panel, choices=["Fit Page", "50%", "75%", "100%", "125%", "150%"])
        self.zoom_choice.SetStringSelection("Fit Page")
        self.zoom_choice.Bind(wx.EVT_CHOICE, self.on_zoom)
        primary_toolbar.Add(self.zoom_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 5)
        self.snap_checkbox = wx.CheckBox(panel, label="Snap to grid")
        self.snap_checkbox.Bind(wx.EVT_CHECKBOX, self.on_snap_toggle)
        primary_toolbar.Add(self.snap_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        toolbar.Add(primary_toolbar, 0, wx.EXPAND)
        self.canvas = ReportCanvas(
            panel, self.model, self.on_selection, self.delete_selected_control,
        )
        controls_panel = wx.Panel(panel, style=wx.BORDER_SIMPLE)
        controls_layout = wx.BoxSizer(wx.VERTICAL)
        controls_layout.Add(wx.StaticText(controls_panel, label="Report Controls"), 0, wx.ALL, 8)
        self.control_list = wx.ListBox(
            controls_panel, choices=list(self.model.controls.keys()), style=wx.LB_EXTENDED,
        )
        self.control_list.Bind(wx.EVT_LISTBOX, self.on_control_list_selection)
        controls_layout.Add(self.control_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        controls_layout.Add(
            wx.StaticText(
                controls_panel,
                label="Select a control, then drag it.\nDrag the blue corner to resize.",
            ),
            0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8,
        )
        controls_layout.Add(wx.StaticText(controls_panel, label="Report Sections"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        self.band_list = wx.ListBox(
            controls_panel, choices=list(self.model.report["bands"]), style=wx.LB_SINGLE,
        )
        self.band_list.Bind(wx.EVT_LISTBOX, self.on_band_selection)
        controls_layout.Add(self.band_list, 0, wx.EXPAND | wx.ALL, 8)
        band_height_button = wx.Button(controls_panel, label="Change Section Height")
        band_height_button.Bind(wx.EVT_BUTTON, self.on_change_band_height)
        controls_layout.Add(band_height_button, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.field_bindings = []
        if dataset_contract is not None:
            controls_layout.Add(wx.StaticText(controls_panel, label="Approved Data Fields"), 0, wx.ALL, 8)
            field_labels = []
            for collection in dataset_contract.collections:
                for field in collection.fields:
                    self.field_bindings.append((collection, field))
                    field_labels.append(f"{collection.label}: {field.label}")
            self.field_list = wx.ListBox(controls_panel, choices=field_labels, style=wx.LB_SINGLE)
            self.field_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_add_field)
            controls_layout.Add(self.field_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
            add_field_button = wx.Button(controls_panel, label="Add Selected Field")
            add_field_button.Bind(wx.EVT_BUTTON, self.on_add_field)
            controls_layout.Add(add_field_button, 0, wx.EXPAND | wx.ALL, 8)
        controls_panel.SetSizer(controls_layout)
        properties_panel = wx.Panel(panel, style=wx.BORDER_SIMPLE)
        properties_layout = wx.BoxSizer(wx.VERTICAL)
        properties_layout.Add(wx.StaticText(properties_panel, label="Properties"), 0, wx.ALL, 8)
        self.selection = wx.StaticText(
            properties_panel, label="No control selected", style=wx.ST_ELLIPSIZE_END,
        )
        self.selection.SetToolTip("Selected report control")
        properties_layout.Add(self.selection, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.selection_geometry = wx.StaticText(properties_panel, label="")
        properties_layout.Add(
            self.selection_geometry, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8,
        )
        grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=6)
        grid.AddGrowableCol(1, 1)
        self.property_controls = {}
        for key, label in (("x", "X"), ("y", "Y"), ("width", "Width"), ("height", "Height")):
            grid.Add(wx.StaticText(properties_panel, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            editor = wx.SpinCtrlDouble(
                properties_panel, min=0, max=2000, initial=0, inc=1,
                style=wx.SP_ARROW_KEYS | wx.TE_PROCESS_ENTER,
            )
            editor.SetDigits(0)
            editor.Bind(wx.EVT_SPINCTRLDOUBLE, self.on_geometry_change)
            editor.Bind(wx.EVT_TEXT_ENTER, self.on_geometry_change)
            self.property_controls[key] = editor
            grid.Add(editor, 1, wx.EXPAND)
        for key, label in (("label", "Label"), ("collection", "Collection"), ("field", "Field"), ("color", "Text color")):
            grid.Add(wx.StaticText(properties_panel, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            editor = wx.TextCtrl(properties_panel, style=wx.TE_PROCESS_ENTER)
            editor.Bind(wx.EVT_TEXT_ENTER, lambda event, property_name=key: self.on_text_property(event, property_name))
            editor.Bind(wx.EVT_KILL_FOCUS, lambda event, property_name=key: self.on_text_property(event, property_name))
            self.property_controls[key] = editor
            grid.Add(editor, 1, wx.EXPAND)
        grid.Add(wx.StaticText(properties_panel, label="Font size"), 0, wx.ALIGN_CENTER_VERTICAL)
        font_size = wx.SpinCtrlDouble(properties_panel, min=5, max=96, initial=10, inc=1)
        font_size.SetDigits(0)
        font_size.Bind(wx.EVT_SPINCTRLDOUBLE, self.on_style_change)
        self.property_controls["fontsize"] = font_size
        grid.Add(font_size, 1, wx.EXPAND)
        for key, label in (("bold", "Bold"), ("italic", "Italic")):
            grid.Add(wx.StaticText(properties_panel, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            editor = wx.CheckBox(properties_panel)
            editor.Bind(wx.EVT_CHECKBOX, self.on_style_change)
            self.property_controls[key] = editor
            grid.Add(editor, 0)
        grid.Add(wx.StaticText(properties_panel, label="Alignment"), 0, wx.ALIGN_CENTER_VERTICAL)
        alignment = wx.Choice(properties_panel, choices=["left", "center", "right"])
        alignment.Bind(wx.EVT_CHOICE, self.on_style_change)
        self.property_controls["align"] = alignment
        grid.Add(alignment, 1, wx.EXPAND)
        properties_layout.Add(grid, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        self.edit_repeater_button = wx.Button(properties_panel, label="Edit Detail Columns")
        self.edit_repeater_button.Bind(wx.EVT_BUTTON, self.on_edit_repeater)
        properties_layout.Add(self.edit_repeater_button, 0, wx.EXPAND | wx.ALL, 8)
        properties_layout.AddStretchSpacer()
        properties_panel.SetSizer(properties_layout)
        workspace = wx.BoxSizer(wx.HORIZONTAL)
        workspace.Add(controls_panel, 0, wx.EXPAND | wx.ALL, 5)
        workspace.Add(self.canvas, 1, wx.EXPAND | wx.TOP | wx.RIGHT | wx.BOTTOM, 5)
        workspace.Add(properties_panel, 0, wx.EXPAND | wx.TOP | wx.RIGHT | wx.BOTTOM, 5)
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(toolbar, 0, wx.EXPAND)
        layout.Add(workspace, 1, wx.EXPAND)
        panel.SetSizer(layout)
        self.CreateStatusBar()
        undo_id = wx.NewIdRef()
        redo_id = wx.NewIdRef()
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord("Z"), undo_id),
            (wx.ACCEL_CTRL, ord("Y"), redo_id),
        ]))
        self.Bind(wx.EVT_MENU, self.on_undo, id=undo_id)
        self.Bind(wx.EVT_MENU, self.on_redo, id=redo_id)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        if self.model.controls:
            first_control = next(iter(self.model.controls))
            self.model.select(first_control)
            self.canvas.selected_names = {first_control}
            self.on_selection(first_control)
        wx.CallAfter(self.canvas.fit_page)

    def build_menu_bar(self):
        menu_bar = wx.MenuBar()

        file_menu = wx.Menu()
        self._append_menu(file_menu, "&Open...\tCtrl+O", self.on_open)
        self._append_menu(file_menu, "&Save\tCtrl+S", self.on_save)
        self._append_menu(file_menu, "Save &As...\tCtrl+Shift+S", self.on_save_as)
        file_menu.AppendSeparator()
        if self.preview_handler is not None:
            self._append_menu(file_menu, "&Preview\tCtrl+P", self.on_preview)
        self._append_menu(file_menu, "Page Set&up...", self.on_page_setup)
        if self.starter_definition_path is not None:
            self._append_menu(file_menu, "&Restore Starter...", self.on_restore_starter)
        file_menu.AppendSeparator()
        self._append_menu(file_menu, "E&xit", lambda event: self.Close())
        menu_bar.Append(file_menu, "&File")

        edit_menu = wx.Menu()
        self._append_menu(edit_menu, "&Undo\tCtrl+Z", self.on_undo)
        self._append_menu(edit_menu, "&Redo\tCtrl+Y", self.on_redo)
        edit_menu.AppendSeparator()
        self._append_menu(edit_menu, "&Delete\tDel", self.on_delete_control)
        menu_bar.Append(edit_menu, "&Edit")

        insert_menu = wx.Menu()
        for control_type, label in (("label", "Label"), ("line", "Line"), ("rectangle", "Box")):
            self._append_menu(
                insert_menu, f"Add &{label}...",
                lambda event, value=control_type: self.add_control(value),
            )
        if self.dataset_contract is not None:
            insert_menu.AppendSeparator()
            self._append_menu(insert_menu, "Add Selected Data &Field...", self.on_add_field)
        menu_bar.Append(insert_menu, "&Insert")

        layout_menu = wx.Menu()
        for edge, label in (("left", "Left"), ("right", "Right"), ("top", "Top"), ("bottom", "Bottom")):
            self._append_menu(
                layout_menu, f"Align {label}",
                lambda event, value=edge: self.apply_alignment(value),
            )
        layout_menu.AppendSeparator()
        self._append_menu(
            layout_menu, "Distribute Across",
            lambda event: self.apply_distribution("horizontal"),
        )
        self._append_menu(
            layout_menu, "Distribute Down",
            lambda event: self.apply_distribution("vertical"),
        )
        menu_bar.Append(layout_menu, "&Layout")

        view_menu = wx.Menu()
        self._append_menu(view_menu, "Fit Page", lambda event: self.set_zoom("Fit Page"))
        for value in ("50%", "75%", "100%", "125%", "150%"):
            self._append_menu(view_menu, value, lambda event, zoom=value: self.set_zoom(zoom))
        view_menu.AppendSeparator()
        self.snap_menu_item = view_menu.AppendCheckItem(wx.ID_ANY, "Snap to Grid")
        self.Bind(wx.EVT_MENU, self.on_menu_snap_toggle, self.snap_menu_item)
        menu_bar.Append(view_menu, "&View")

        tools_menu = wx.Menu()
        self._append_menu(tools_menu, "&Validate Report", self.on_validate)
        menu_bar.Append(tools_menu, "&Tools")

        help_menu = wx.Menu()
        self._append_menu(help_menu, "Keyboard && Mouse Help", self.on_help)
        menu_bar.Append(help_menu, "&Help")
        self.SetMenuBar(menu_bar)

    def _append_menu(self, menu, label, handler):
        item = menu.Append(wx.ID_ANY, label)
        self.Bind(wx.EVT_MENU, handler, item)
        return item

    def on_help(self, event):
        wx.MessageBox(
            "Ctrl-click selects multiple controls.\n"
            "Arrow keys move; Shift+Arrow moves 10 points.\n"
            "Ctrl+Arrow resizes. Delete removes the selection.\n"
            "Ctrl+Z undoes and Ctrl+Y redoes.",
            "Report Designer Help", wx.OK | wx.ICON_INFORMATION, self,
        )

    def on_selection(self, name):
        if name:
            control = self.model.controls[name]
            names = list(self.model.controls)
            for index in self.control_list.GetSelections():
                self.control_list.Deselect(index)
            for selected_name in self.canvas.selected_names or {name}:
                if selected_name in self.model.controls:
                    self.control_list.SetSelection(names.index(selected_name))
            self.selection.SetLabel(name)
            self.selection_geometry.SetLabel(
                f"Position {control['position']}   Size {control['size']}"
            )
            self.populate_properties(control)
        else:
            self.selection.SetLabel("No control selected")
            self.selection_geometry.SetLabel("")
            self.control_list.SetSelection(wx.NOT_FOUND)

    def populate_properties(self, control):
        self.updating_properties = True
        x, y = control["position"]
        width, height = control["size"]
        for key, value in (("x", x), ("y", y), ("width", width), ("height", height)):
            self.property_controls[key].SetValue(value)
        for key in ("label", "collection", "field", "color"):
            editor = self.property_controls[key]
            editor.SetValue(str(control.get(key, "")))
            required = key in ("collection", "field") and control["type"] in ("text", "image")
            supported = key not in ("collection", "field") or control["type"] in ("text", "image")
            editor.Enable(required or supported)
        self.property_controls["label"].Enable(control["type"] == "label")
        self.property_controls["fontsize"].SetValue(control.get("fontsize", 10))
        self.property_controls["bold"].SetValue(control.get("bold", False))
        self.property_controls["italic"].SetValue(control.get("italic", False))
        self.property_controls["align"].SetStringSelection(control.get("align", "left"))
        self.edit_repeater_button.Enable(control["type"] == "repeater")
        self.updating_properties = False

    def refresh_selected(self):
        name = self.model.selected
        self.on_selection(name)
        self.canvas.Refresh()

    def on_geometry_change(self, event):
        if getattr(self, "updating_properties", False) or not self.model.selected:
            return
        values = self.property_controls
        self.model.set_geometry(
            self.model.selected,
            [values["x"].GetValue(), values["y"].GetValue()],
            [values["width"].GetValue(), values["height"].GetValue()],
        )
        self.refresh_selected()

    def on_text_property(self, event, key):
        if getattr(self, "updating_properties", False) or not self.model.selected:
            event.Skip()
            return
        editor = self.property_controls[key]
        value = editor.GetValue().strip()
        try:
            self.model.set_property(self.model.selected, key, value or None)
            self.SetStatusText(f"Updated {key}")
        except ReportDefinitionError as error:
            self.SetStatusText(str(error))
        self.refresh_selected()
        event.Skip()

    def on_style_change(self, event):
        if getattr(self, "updating_properties", False) or not self.model.selected:
            return
        source = event.GetEventObject()
        key = next(key for key, editor in self.property_controls.items() if editor is source)
        if key in ("bold", "italic"):
            value = source.GetValue()
        elif key == "align":
            value = source.GetStringSelection()
        else:
            value = source.GetValue()
        try:
            self.model.set_property(self.model.selected, key, value)
            self.SetStatusText(f"Updated {key}")
        except ReportDefinitionError as error:
            self.SetStatusText(str(error))
        self.refresh_selected()

    def on_control_list_selection(self, event):
        names = list(self.model.controls)
        indexes = self.control_list.GetSelections()
        self.canvas.selected_names = {names[index] for index in indexes}
        name = names[event.GetSelection()] if event.GetSelection() != wx.NOT_FOUND else None
        self.model.select(name)
        self.on_selection(name)
        self.canvas.reveal_control(name)
        self.canvas.SetFocus()

    def refresh_control_list(self):
        names = list(self.model.controls)
        self.control_list.Set(names)
        if self.model.selected:
            self.control_list.SetSelection(names.index(self.model.selected))

    def on_align(self, event):
        self.apply_alignment(event.GetEventObject().alignment_edge)

    def apply_alignment(self, edge):
        try:
            self.model.align_controls(self.canvas.selected_names, edge)
        except ValueError as error:
            self.SetStatusText(str(error))
            return
        self.canvas.Refresh()
        self.on_selection(self.model.selected)
        self.SetStatusText(f"Aligned {len(self.canvas.selected_names)} controls")

    def on_distribute(self, event):
        self.apply_distribution(event.GetEventObject().distribution_axis)

    def apply_distribution(self, axis):
        try:
            self.model.distribute_controls(self.canvas.selected_names, axis)
        except ValueError as error:
            self.SetStatusText(str(error))
            return
        self.canvas.Refresh()
        self.on_selection(self.model.selected)
        self.SetStatusText(f"Distributed {len(self.canvas.selected_names)} controls evenly")

    def on_change_band_height(self, event):
        band_name = self.band_list.GetStringSelection()
        if not band_name:
            self.SetStatusText("Select a report section first")
            return
        current = self.model.report["bands"][band_name]["height"]
        dialog = wx.NumberEntryDialog(
            self, f"Enter the height for {band_name} in points.",
            "Section height", "Change Section Height", int(current), 4, 2000,
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            height = dialog.GetValue()
        finally:
            dialog.Destroy()
        try:
            self.model.set_band_height(band_name, height)
        except ValueError as error:
            wx.MessageBox(str(error), "Cannot resize section", wx.OK | wx.ICON_WARNING, self)
            return
        self.canvas.refresh_extent()
        if self.model.selected:
            self.canvas.reveal_control(self.model.selected)
        self.SetStatusText(f"{band_name} height changed to {height} points")

    def on_band_selection(self, event):
        self.canvas.selected_band = self.band_list.GetStringSelection() or None
        self.canvas.Refresh()
        if self.canvas.selected_band:
            height = self.model.report["bands"][self.canvas.selected_band]["height"]
            self.SetStatusText(
                f"Selected section: {self.canvas.selected_band} ({height:g} points high)"
            )

    def on_edit_repeater(self, event):
        name = self.model.selected
        if not name or self.model.controls[name]["type"] != "repeater":
            self.SetStatusText("Select a repeating detail control first")
            return
        dialog = RepeaterItemsDialog(self, self.model, name)
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()
        self.refresh_selected()

    def refresh_after_history(self, action):
        self.canvas.model = self.model
        self.canvas.selected_names = {self.model.selected} if self.model.selected else set()
        self.canvas.refresh_extent()
        self.refresh_control_list()
        self.on_selection(self.model.selected)
        self.SetStatusText(action)

    def on_undo(self, event):
        if self.model.undo():
            self.refresh_after_history("Undid last change")
        else:
            self.SetStatusText("Nothing to undo")

    def on_redo(self, event):
        if self.model.redo():
            self.refresh_after_history("Redid last change")
        else:
            self.SetStatusText("Nothing to redo")

    def on_zoom(self, event):
        self.set_zoom(self.zoom_choice.GetStringSelection())

    def set_zoom(self, selection):
        self.zoom_choice.SetStringSelection(selection)
        if selection == "Fit Page":
            self.canvas.fit_page()
            return
        self.canvas.scale = int(selection.rstrip("%")) / 100
        self.canvas.refresh_extent()
        if self.model.selected:
            self.canvas.reveal_control(self.model.selected)

    def on_snap_toggle(self, event):
        self.canvas.snap_enabled = self.snap_checkbox.GetValue()
        self.snap_menu_item.Check(self.canvas.snap_enabled)
        self.canvas.Refresh()
        self.SetStatusText(
            "Snap to 6-point grid enabled" if self.canvas.snap_enabled else "Snap to grid disabled"
        )

    def on_menu_snap_toggle(self, event):
        self.snap_checkbox.SetValue(self.snap_menu_item.IsChecked())
        self.on_snap_toggle(event)

    def choose_band(self):
        bands = list(self.model.report["bands"])
        dialog = wx.SingleChoiceDialog(
            self, "Choose the section where the control belongs.", "Report section", bands,
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            return dialog.GetStringSelection()
        finally:
            dialog.Destroy()

    def on_add_control(self, event):
        self.add_control(event.GetEventObject().control_type)

    def add_control(self, control_type):
        band = self.choose_band()
        if not band:
            return
        name = self.model.add_control(control_type, band=band)
        self.canvas.selected_names = {name}
        self.refresh_control_list()
        self.on_selection(name)
        self.canvas.reveal_control(name)
        self.canvas.SetFocus()

    def on_add_field(self, event):
        selection = self.field_list.GetSelection()
        if selection == wx.NOT_FOUND:
            self.SetStatusText("Select an approved data field first")
            return
        band = self.choose_band()
        if not band:
            return
        collection, field = self.field_bindings[selection]
        name = self.model.add_bound_field(
            collection.name, field.name, field.label, field.data_type, band,
        )
        self.canvas.selected_names = {name}
        self.refresh_control_list()
        self.on_selection(name)
        self.canvas.reveal_control(name)
        self.canvas.SetFocus()

    def on_delete_control(self, event):
        self.delete_selected_control()

    def delete_selected_control(self):
        name = self.model.selected
        if not name:
            self.SetStatusText("Select a control to delete")
            return
        dialog = wx.MessageDialog(
            self, f"Delete the report control {name}?", "Delete report control",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )
        try:
            if dialog.ShowModal() != wx.ID_YES:
                return
        finally:
            dialog.Destroy()
        self.model.delete_control(name)
        self.canvas.selected_names.discard(name)
        self.refresh_control_list()
        self.on_selection(None)
        self.canvas.Refresh()
        self.SetStatusText(f"Deleted {name}")

    def on_save(self, event):
        self.model.save(self.path)
        self.SetStatusText("Report definition saved") if self.GetStatusBar() else None

    def on_save_as(self, event):
        dialog = wx.FileDialog(
            self, "Save report definition as", defaultDir=str(self.path.parent),
            defaultFile=self.path.name,
            wildcard="Report definitions (*.json)|*.json",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            target = Path(dialog.GetPath())
        finally:
            dialog.Destroy()
        if target.suffix.casefold() != ".json":
            target = target.with_suffix(".json")
        try:
            definition = self.model.validated_definition()
            if self.dataset_contract is not None:
                self.dataset_contract.validate_definition(definition)
            self.model.save(target)
        except (ReportDefinitionError, ValueError) as error:
            wx.MessageBox(str(error), "Cannot save report", wx.OK | wx.ICON_ERROR, self)
            return
        self.path = target
        self.SetTitle(f"JSForm Report Designer - {definition.title}")
        self.SetStatusText(f"Report saved as {target.name}")

    def on_page_setup(self, event):
        dialog = PageSetupDialog(self, self.model)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            pagesize, orientation, margins = dialog.values()
        finally:
            dialog.Destroy()
        try:
            self.model.set_page_setup(pagesize, orientation, margins)
        except ValueError as error:
            wx.MessageBox(str(error), "Cannot change page setup", wx.OK | wx.ICON_WARNING, self)
            return
        self.canvas.refresh_extent()
        if self.zoom_choice.GetStringSelection() == "Fit Page":
            self.canvas.fit_page()
        self.SetStatusText(f"Page setup changed to {pagesize.upper()} {orientation}")

    def confirm_discard_or_save(self):
        if not self.model.dirty:
            return True
        dialog = wx.MessageDialog(
            self, "Save changes to this report definition?", "Unsaved report changes",
            wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION,
        )
        try:
            result = dialog.ShowModal()
        finally:
            dialog.Destroy()
        if result == wx.ID_CANCEL:
            return False
        if result == wx.ID_YES:
            self.model.save(self.path)
        return True

    def on_open(self, event):
        if not self.confirm_discard_or_save():
            return
        dialog = wx.FileDialog(
            self, "Open report definition", defaultDir=str(self.path.parent),
            wildcard="Report definitions (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            selected_path = Path(dialog.GetPath())
        finally:
            dialog.Destroy()
        try:
            definition = ReportDefinitionLoader().load(selected_path)
            if self.dataset_contract is not None:
                self.dataset_contract.validate_definition(definition)
        except (ReportDefinitionError, ValueError) as error:
            wx.MessageBox(str(error), "Cannot open report", wx.OK | wx.ICON_ERROR, self)
            return
        replacement = ReportDesignerFrame(
            selected_path, dataset_contract=self.dataset_contract,
            preview_handler=self.preview_handler,
            starter_definition_path=self.starter_definition_path,
        )
        replacement.Show()
        self.Destroy()

    def on_preview(self, event):
        try:
            definition = self.model.validated_definition()
            output = Path(self.preview_handler(definition))
            if not output.is_file():
                raise RuntimeError("The report preview was not created.")
            wx.LaunchDefaultApplication(str(output))
            self.SetStatusText(f"Preview created: {output.name}")
        except Exception as error:
            wx.MessageBox(str(error), "Cannot preview report", wx.OK | wx.ICON_ERROR, self)

    def on_validate(self, event):
        try:
            definition = self.model.validated_definition()
            if self.dataset_contract is not None:
                self.dataset_contract.validate_definition(definition)
            warnings = self.model.layout_warnings()
        except (ReportDefinitionError, ValueError) as error:
            wx.MessageBox(str(error), "Report validation failed", wx.OK | wx.ICON_ERROR, self)
            return
        if warnings:
            message = "The report is valid, but these layout items need review:\n\n" + "\n".join(
                f"• {warning}" for warning in warnings
            )
            wx.MessageBox(message, "Report validation", wx.OK | wx.ICON_WARNING, self)
            self.SetStatusText(f"Valid report with {len(warnings)} layout warning(s)")
        else:
            wx.MessageBox(
                "The report definition, data fields, and layout are valid.",
                "Report validation", wx.OK | wx.ICON_INFORMATION, self,
            )
            self.SetStatusText("Report validation passed")

    def on_restore_starter(self, event):
        dialog = wx.MessageDialog(
            self,
            "Replace the current layout with the original starter layout?\n\n"
            "The change is not permanent until you click Save.",
            "Restore starter layout",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )
        try:
            if dialog.ShowModal() != wx.ID_YES:
                return
        finally:
            dialog.Destroy()
        try:
            definition = ReportDefinitionLoader().load(self.starter_definition_path)
            if self.dataset_contract is not None:
                self.dataset_contract.validate_definition(definition)
            self.model.replace_definition(definition)
        except (ReportDefinitionError, ValueError) as error:
            wx.MessageBox(str(error), "Cannot restore starter", wx.OK | wx.ICON_ERROR, self)
            return
        self.canvas.model = self.model
        self.canvas.selected_names = {self.model.selected} if self.model.selected else set()
        self.canvas.refresh_extent()
        self.refresh_control_list()
        self.on_selection(self.model.selected)
        self.SetStatusText("Starter layout restored; click Save to keep it")

    def on_close(self, event):
        if not self.confirm_discard_or_save():
            event.Veto()
            return
        event.Skip()


def open_report_designer(
    definition_path, dataset_contract=None, preview_handler=None,
    starter_definition_path=None,
):
    application = wx.App.Get() or wx.App(False)
    frame = ReportDesignerFrame(
        definition_path, dataset_contract=dataset_contract,
        preview_handler=preview_handler,
        starter_definition_path=starter_definition_path,
    )
    frame.Show()
    if not wx.App.Get().IsMainLoopRunning():
        application.MainLoop()
    return frame
