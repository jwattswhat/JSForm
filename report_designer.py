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

    def set_property(self, name, key, value):
        candidate = deepcopy(self.data)
        candidate_control = candidate[self.root_name]["CONTROLS"][name]
        if value is None:
            candidate_control.pop(key, None)
        else:
            candidate_control[key] = value
        validated = self.loader.from_dict(candidate)
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
        self.data = validated.to_dict()
        self.selected = name
        self.dirty = True
        return name

    def delete_control(self, name):
        if name not in self.controls:
            raise KeyError(name)
        del self.controls[name]
        if self.selected == name:
            self.selected = None
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
        self.model.select(name)
        self.drag_origin = position if name else None
        self.drag_mode = mode
        if name:
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
            dc.SetPen(wx.Pen(wx.Colour(185, 195, 205), 1, wx.PENSTYLE_DOT))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRectangle(content_x, top, content_width, band_height)
            dc.SetTextForeground(wx.Colour(90, 105, 120))
            dc.SetFont(wx.Font(7, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            dc.DrawText(band_name, content_x + 2, top + 1)
        for name, control in self.model.controls.items():
            rect = self.control_rect(control)
            selected = name == self.model.selected
            dc.SetPen(wx.Pen(wx.Colour(0, 92, 190) if selected else wx.Colour(55, 105, 145), 3 if selected else 2))
            dc.SetBrush(wx.Brush(wx.Colour(214, 234, 255) if selected else wx.Colour(235, 246, 255)))
            dc.DrawRectangle(rect)
            dc.SetTextForeground(wx.BLACK)
            dc.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            label = control.get("label") or f"{name}: {control.get('field', control['type'])}"
            dc.SetClippingRegion(rect)
            dc.DrawText(label, rect.x + 3, rect.y + 3)
            dc.DestroyClippingRegion()
            if selected:
                dc.SetBrush(wx.Brush(wx.Colour(0, 100, 220)))
                dc.DrawRectangle(rect.right - HANDLE // 2, rect.bottom - HANDLE // 2, HANDLE, HANDLE)


class ReportDesignerFrame(wx.Frame):
    def __init__(self, definition_path, dataset_contract=None, preview_handler=None):
        self.path = Path(definition_path)
        definition = ReportDefinitionLoader().load(self.path)
        self.model = ReportDesignerModel(definition)
        self.dataset_contract = dataset_contract
        self.preview_handler = preview_handler
        if dataset_contract is not None:
            dataset_contract.validate_definition(definition)
        super().__init__(None, title=f"JSForm Report Designer - {definition.title}", size=(1100, 850))
        panel = wx.Panel(self)
        toolbar = wx.BoxSizer(wx.HORIZONTAL)
        open_button = wx.Button(panel, label="Open")
        open_button.Bind(wx.EVT_BUTTON, self.on_open)
        toolbar.Add(open_button, 0, wx.ALL, 5)
        save_button = wx.Button(panel, label="Save")
        save_button.Bind(wx.EVT_BUTTON, self.on_save)
        toolbar.Add(save_button, 0, wx.TOP | wx.BOTTOM | wx.RIGHT, 5)
        if preview_handler is not None:
            preview_button = wx.Button(panel, label="Preview")
            preview_button.Bind(wx.EVT_BUTTON, self.on_preview)
            toolbar.Add(preview_button, 0, wx.TOP | wx.BOTTOM | wx.RIGHT, 5)
        for control_type, label in (("label", "Add Label"), ("line", "Add Line"), ("rectangle", "Add Box")):
            button = wx.Button(panel, label=label)
            button.control_type = control_type
            button.Bind(wx.EVT_BUTTON, self.on_add_control)
            toolbar.Add(button, 0, wx.TOP | wx.BOTTOM | wx.RIGHT, 5)
        delete_button = wx.Button(panel, label="Delete")
        delete_button.Bind(wx.EVT_BUTTON, self.on_delete_control)
        toolbar.Add(delete_button, 0, wx.TOP | wx.BOTTOM | wx.RIGHT, 5)
        self.selection = wx.StaticText(panel, label="No control selected")
        toolbar.Add(self.selection, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
        self.canvas = ReportCanvas(
            panel, self.model, self.on_selection, self.delete_selected_control,
        )
        controls_panel = wx.Panel(panel, style=wx.BORDER_SIMPLE)
        controls_layout = wx.BoxSizer(wx.VERTICAL)
        controls_layout.Add(wx.StaticText(controls_panel, label="Report Controls"), 0, wx.ALL, 8)
        self.control_list = wx.ListBox(
            controls_panel, choices=list(self.model.controls.keys()), style=wx.LB_SINGLE,
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
        self.Bind(wx.EVT_CLOSE, self.on_close)
        if self.model.controls:
            first_control = next(iter(self.model.controls))
            self.model.select(first_control)
            self.on_selection(first_control)

    def on_selection(self, name):
        if name:
            control = self.model.controls[name]
            self.control_list.SetSelection(list(self.model.controls).index(name))
            self.selection.SetLabel(
                f"{name}   Position {control['position']}   Size {control['size']}"
            )
            self.populate_properties(control)
        else:
            self.selection.SetLabel("No control selected")
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
        name = self.control_list.GetStringSelection()
        self.model.select(name)
        self.on_selection(name)
        self.canvas.reveal_control(name)
        self.canvas.SetFocus()

    def refresh_control_list(self):
        names = list(self.model.controls)
        self.control_list.Set(names)
        if self.model.selected:
            self.control_list.SetSelection(names.index(self.model.selected))

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
        band = self.choose_band()
        if not band:
            return
        name = self.model.add_control(event.GetEventObject().control_type, band=band)
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
        self.refresh_control_list()
        self.on_selection(None)
        self.canvas.Refresh()
        self.SetStatusText(f"Deleted {name}")

    def on_save(self, event):
        self.model.save(self.path)
        self.SetStatusText("Report definition saved") if self.GetStatusBar() else None

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

    def on_close(self, event):
        if not self.confirm_discard_or_save():
            event.Veto()
            return
        event.Skip()


def open_report_designer(definition_path, dataset_contract=None, preview_handler=None):
    application = wx.App.Get() or wx.App(False)
    frame = ReportDesignerFrame(
        definition_path, dataset_contract=dataset_contract,
        preview_handler=preview_handler,
    )
    frame.Show()
    if not wx.App.Get().IsMainLoopRunning():
        application.MainLoop()
    return frame
