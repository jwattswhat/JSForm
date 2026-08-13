"""Initial visual canvas and editing model for JSForm report definitions."""

from copy import deepcopy
from pathlib import Path
import shutil

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
    "systemtext": {"size": [140, 20], "systemvalue": "run_date", "prefix": "Run: ", "fontsize": 8},
    "line": {"size": [140, 1], "bordercolor": "#808080", "borderwidth": 1},
    "rectangle": {"size": [140, 50], "bordercolor": "#808080", "borderwidth": 1},
}


def export_preview_file(preview_path, target_path):
    source = Path(preview_path)
    target = Path(target_path)
    if not source.is_file():
        raise FileNotFoundError(f"Preview PDF was not created: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != target.resolve():
        shutil.copyfile(source, target)
    return target


class ReportDesignerModel:
    def __init__(self, definition, loader=None, protection_manifest=None):
        self.loader = loader or ReportDefinitionLoader()
        self.protection_manifest = protection_manifest
        if protection_manifest is not None:
            protection_manifest.validate(definition)
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
        required = (
            self.protection_manifest.required_controls.get(name, {})
            if self.protection_manifest else {}
        )
        if key in required and value != required[key]:
            raise ValueError(f"{name} is required and its {key} cannot be changed")
        if self.protection_manifest and name in self.protection_manifest.required_controls and key == "visible" and value is False:
            raise ValueError(f"{name} is required and cannot be hidden")
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

    def set_visibility_condition(self, name, condition=None):
        if self.protection_manifest and name in self.protection_manifest.required_controls:
            required = self.protection_manifest.required_controls[name]
            if required.get("visiblewhen") != condition:
                raise ValueError(f"{name} is required and its visibility condition cannot be changed")
        candidate = deepcopy(self.data)
        control = candidate[self.root_name]["CONTROLS"][name]
        if condition:
            control["visiblewhen"] = dict(condition)
        else:
            control.pop("visiblewhen", None)
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
        prefix = {"label": "Label", "systemtext": "SystemText", "line": "Line", "rectangle": "Rectangle"}[control_type]
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

    def add_aggregate(
        self, collection, field, operation, scope="report", group=None, format_name=None,
    ):
        candidate = deepcopy(self.data)
        candidate_report = candidate[self.root_name]["REPORT"]
        if scope == "group":
            group_item = next(
                (item for item in self.report.get("groups", []) if item["name"] == group), None
            )
            if group_item is None:
                raise ValueError(f"Unknown report group: {group}")
            band = group_item["footerband"]
            candidate_report["bands"][band]["height"] = max(
                28, candidate_report["bands"][band]["height"]
            )
        else:
            band = next(
                (name for name, item in self.report["bands"].items() if item["type"] == "reportfooter"),
                None,
            )
            if band is None:
                band = "ReportFooter"
                number = 2
                while band in candidate_report["bands"]:
                    band = f"ReportFooter{number}"
                    number += 1
                candidate_report["bands"][band] = {"type": "reportfooter", "height": 28}
        name = self.unique_control_name(f"{operation.title()}{field}")
        control = {
            "type": "aggregate", "band": band, "position": [self.content_width - 180, 4],
            "size": [180, 20], "collection": collection, "field": field,
            "operation": operation, "scope": scope, "fontsize": 10, "bold": True,
            "align": "right",
        }
        if group is not None:
            control["group"] = group
        if format_name is not None:
            control["format"] = format_name
        candidate[self.root_name]["CONTROLS"][name] = control
        validated = self.loader.from_dict(candidate)
        self._record_change()
        self.data = validated.to_dict()
        self.selected = name
        self.dirty = True
        return name

    def add_matrix(self, collection, rowfield, columnfield, valuefield, rowlabel, band=None):
        band = band or next(
            (name for name, item in self.report["bands"].items() if item["type"] == "detail"),
            None,
        )
        if band is None:
            raise ValueError("A matrix requires a detail report section")
        name = self.unique_control_name("Matrix")
        control = {
            "type": "matrix", "band": band, "position": [0, 0],
            "size": [self.content_width, min(60, self.report["bands"][band]["height"])],
            "repeatcollection": collection, "rowfield": rowfield,
            "columnfield": columnfield, "valuefield": valuefield,
            "rowlabel": rowlabel, "rowwidth": min(220, self.content_width / 3),
            "format": "currency", "showrowtotals": True,
            "showcolumntotals": True, "showgrandtotal": True,
        }
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
        if self.protection_manifest and name in self.protection_manifest.required_controls:
            raise ValueError(f"{name} is required and cannot be deleted")
        self._record_change()
        del self.controls[name]
        if self.selected == name:
            self.selected = None
        self.dirty = True

    def replace_definition(self, definition):
        if self.protection_manifest is not None:
            self.protection_manifest.validate(definition)
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
        definition = self.loader.from_dict(deepcopy(self.data))
        if self.protection_manifest is not None:
            self.protection_manifest.validate(definition)
        return definition

    def layout_warnings(self):
        warnings = []
        by_band = {}
        for name, control in self.controls.items():
            x, y = control["position"]
            width, height = control["size"]
            band_height = self.report["bands"][control["band"]]["height"]
            if x + width > self.content_width or y + height > band_height:
                warnings.append(f"{name} extends outside its report section")
            if control["type"] in ("text", "image", "aggregate"):
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

    def set_table_column(self, control_name, column_name, label=None, width=None, format_name=None, align=None):
        control = self.controls[control_name]
        if control["type"] != "table":
            raise ValueError(f"{control_name} is not a table control")
        candidate = deepcopy(self.data)
        candidate_control = candidate[self.root_name]["CONTROLS"][control_name]
        column = next((item for item in candidate_control["columns"] if item["name"] == column_name), None)
        if column is None:
            raise ValueError(f"Unknown table column: {column_name}")
        if label is not None:
            column["label"] = label
        if width is not None:
            column["width"] = max(MINIMUM_SIZE, width)
        if format_name:
            column["format"] = format_name
        else:
            column.pop("format", None)
        if align and align != "left":
            column["align"] = align
        else:
            column.pop("align", None)
        total_width = sum(item["width"] for item in candidate_control["columns"])
        if total_width > candidate_control["size"][0] + 0.01:
            raise ValueError(
                f"Table columns require {total_width:g} points but the table is only "
                f"{candidate_control['size'][0]:g} points wide"
            )
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

    def set_sort(self, sort_items):
        candidate = deepcopy(self.data)
        settings = candidate[self.root_name]["REPORT"]
        if sort_items:
            settings["sort"] = [dict(item) for item in sort_items]
        else:
            settings.pop("sort", None)
        validated = self.loader.from_dict(candidate)
        self._record_change()
        self.data = validated.to_dict()
        self.dirty = True

    def set_groups(self, groups):
        candidate = deepcopy(self.data)
        root = candidate[self.root_name]
        settings = root["REPORT"]
        controls = root["CONTROLS"]
        old_groups = {item["name"]: item for item in settings.get("groups", [])}
        new_groups = [dict(item) for item in groups]
        retained_names = {item["name"] for item in new_groups}
        for name, item in old_groups.items():
            if name in retained_names:
                continue
            removed_bands = {item["headerband"], item["footerband"]}
            for control_name in [
                key for key, control in controls.items() if control["band"] in removed_bands
            ]:
                del controls[control_name]
            for band_name in removed_bands:
                settings["bands"].pop(band_name, None)

        for item in new_groups:
            if item["name"] in old_groups:
                continue
            header = item["headerband"]
            footer = item["footerband"]
            settings["bands"][header] = {"type": "groupheader", "height": 24}
            settings["bands"][footer] = {"type": "groupfooter", "height": 8}
            control_name = self.unique_control_name(f"{item['name']}Value")
            controls[control_name] = {
                "type": "text", "band": header, "position": [0, 2],
                "size": [self.content_width, 20], "collection": item["collection"],
                "field": item["field"], "fontsize": 11, "bold": True,
            }

        if new_groups:
            settings["groups"] = new_groups
            existing_sort = settings.get("sort", [])
            group_keys = {(item["collection"], item["field"]) for item in new_groups}
            settings["sort"] = [
                {"collection": item["collection"], "field": item["field"], "direction": "ascending"}
                for item in new_groups
            ] + [
                item for item in existing_sort
                if (item["collection"], item["field"]) not in group_keys
            ]
        else:
            settings.pop("groups", None)
        settings["bands"] = self._ordered_group_bands(settings["bands"], new_groups)
        validated = self.loader.from_dict(candidate)
        self._record_change()
        self.data = validated.to_dict()
        self.dirty = True

    @staticmethod
    def _ordered_group_bands(bands, groups):
        group_band_names = {
            item[key] for item in groups for key in ("headerband", "footerband")
        }
        ordinary = [(name, band) for name, band in bands.items() if name not in group_band_names]
        result = {}
        for name, band in ordinary:
            if band["type"] in ("reportheader", "pageheader"):
                result[name] = band
        for item in groups:
            result[item["headerband"]] = bands[item["headerband"]]
        for name, band in ordinary:
            if band["type"] == "detail":
                result[name] = band
        for item in reversed(groups):
            result[item["footerband"]] = bands[item["footerband"]]
        for name, band in ordinary:
            if band["type"] not in ("reportheader", "pageheader", "detail"):
                result[name] = band
        return result

    def copy_controls(self, names):
        names = [name for name in names if name in self.controls]
        return [(name, deepcopy(self.controls[name])) for name in names]

    def paste_controls(self, copied_controls, offset=12):
        if not copied_controls:
            raise ValueError("There are no copied controls to paste")
        candidate = deepcopy(self.data)
        candidate_controls = candidate[self.root_name]["CONTROLS"]
        created = []
        for original_name, original in copied_controls:
            name = self.unique_control_name(f"{original_name}Copy")
            control = deepcopy(original)
            x, y = control["position"]
            width, height = control["size"]
            band_height = self.report["bands"][control["band"]]["height"]
            control["position"] = [
                min(max(0, x + offset), max(0, self.content_width - width)),
                min(max(0, y + offset), max(0, band_height - height)),
            ]
            candidate_controls[name] = control
            created.append(name)
        validated = self.loader.from_dict(candidate)
        self._record_change()
        self.data = validated.to_dict()
        self.selected = created[-1]
        self.dirty = True
        return created

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
    def __init__(
        self, parent, model, on_selection=None, on_delete=None,
        on_activate=None, scale=1.0,
    ):
        super().__init__(parent, style=wx.BORDER_SIMPLE | wx.WANTS_CHARS)
        self.model = model
        self.on_selection = on_selection
        self.on_delete = on_delete
        self.on_activate = on_activate
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
        self.Bind(wx.EVT_LEFT_DCLICK, self.on_left_double_click)
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

    def on_left_double_click(self, event):
        position = self.CalcUnscrolledPosition(event.GetPosition())
        name, _ = self.hit_test(position)
        if not name:
            return
        self.selected_names = {name}
        self.model.select(name)
        if self.on_selection:
            self.on_selection(name)
        if self.on_activate:
            self.on_activate(name)

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
            border = wx.Colour(control.get("bordercolor", "#376991"))
            background = wx.Colour(control.get("background", "#EBF6FF"))
            dc.SetPen(wx.Pen(
                wx.Colour(0, 92, 190) if selected else border,
                3 if selected else max(1, round(control.get("borderwidth", 1))),
                wx.PENSTYLE_SOLID if control.get("visible", True) else wx.PENSTYLE_SHORT_DASH,
            ))
            dc.SetBrush(wx.Brush(wx.Colour(214, 234, 255) if selected else background))
            dc.DrawRectangle(rect)
            dc.SetTextForeground(wx.Colour(control.get("color", "#000000")))
            dc.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            label = control.get("label") or f"{name}: {control.get('field', control['type'])}"
            dc.SetClippingRegion(rect)
            dc.DrawText(label, rect.x + 3, rect.y + 3)
            dc.DestroyClippingRegion()
            if control["type"] == "repeater":
                self.draw_repeater_items(dc, rect, control, selected)
            elif control["type"] in ("table", "matrix"):
                self.draw_table_columns(dc, rect, control)
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

    def draw_table_columns(self, dc, table_rect, control):
        if control["type"] == "matrix":
            labels = [control["rowlabel"], "Dynamic columns"]
            widths = [control["rowwidth"], control["size"][0] - control["rowwidth"]]
            columns = ({"label": label, "width": width} for label, width in zip(labels, widths))
        else:
            columns = control["columns"]
        x = table_rect.x
        for column in columns:
            width = max(1, int(column["width"] * self.scale))
            rect = wx.Rect(x, table_rect.y, width, table_rect.height)
            dc.SetPen(wx.Pen(wx.Colour(90, 145, 180), 1, wx.PENSTYLE_DOT))
            dc.SetBrush(wx.Brush(wx.Colour(250, 253, 255)))
            dc.DrawRectangle(rect)
            dc.SetTextForeground(wx.Colour(35, 70, 95))
            dc.SetFont(wx.Font(7, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            dc.SetClippingRegion(rect)
            dc.DrawText(column["label"], rect.x + 2, rect.y + 1)
            dc.DestroyClippingRegion()
            x += width


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


class TableColumnsDialog(wx.Dialog):
    def __init__(self, parent, model, control_name):
        super().__init__(parent, title="Edit Table Columns", size=(520, 350))
        self.model = model
        self.control_name = control_name
        self.columns = model.controls[control_name]["columns"]
        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(panel, label="Choose a column, then adjust its heading, width, format, and alignment."), 0, wx.ALL, 10)
        body = wx.BoxSizer(wx.HORIZONTAL)
        self.item_list = wx.ListBox(panel, choices=[item["name"] for item in self.columns])
        self.item_list.Bind(wx.EVT_LISTBOX, self.on_selection)
        body.Add(self.item_list, 1, wx.EXPAND | wx.RIGHT, 10)
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=8)
        grid.Add(wx.StaticText(panel, label="Heading"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.label = wx.TextCtrl(panel)
        grid.Add(self.label, 1, wx.EXPAND)
        grid.Add(wx.StaticText(panel, label="Width"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.width = wx.SpinCtrlDouble(panel, min=4, max=2000, initial=80, inc=1)
        self.width.SetDigits(0)
        grid.Add(self.width, 1, wx.EXPAND)
        grid.Add(wx.StaticText(panel, label="Format"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.format = wx.Choice(panel, choices=["text", "integer", "decimal", "currency", "date", "time", "datetime", "boolean", "phone", "address"])
        grid.Add(self.format, 1, wx.EXPAND)
        grid.Add(wx.StaticText(panel, label="Alignment"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.align = wx.Choice(panel, choices=["left", "center", "right"])
        grid.Add(self.align, 1, wx.EXPAND)
        grid.AddGrowableCol(1, 1)
        body.Add(grid, 1, wx.EXPAND)
        layout.Add(body, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        buttons.AddStretchSpacer()
        apply_button = wx.Button(panel, label="Apply")
        apply_button.Bind(wx.EVT_BUTTON, self.on_apply)
        buttons.Add(apply_button, 0, wx.RIGHT, 8)
        close_button = wx.Button(panel, wx.ID_CLOSE, "Close")
        close_button.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_CLOSE))
        buttons.Add(close_button)
        layout.Add(buttons, 0, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(layout)
        if self.columns:
            self.item_list.SetSelection(0)
            self.load(0)

    def on_selection(self, event):
        self.load(event.GetSelection())

    def load(self, index):
        column = self.model.controls[self.control_name]["columns"][index]
        self.label.SetValue(column["label"])
        self.width.SetValue(column["width"])
        self.format.SetStringSelection(column.get("format", "text"))
        self.align.SetStringSelection(column.get("align", "left"))

    def on_apply(self, event):
        index = self.item_list.GetSelection()
        if index == wx.NOT_FOUND:
            return
        column = self.model.controls[self.control_name]["columns"][index]
        try:
            self.model.set_table_column(
                self.control_name, column["name"], self.label.GetValue(), self.width.GetValue(),
                self.format.GetStringSelection(), self.align.GetStringSelection(),
            )
        except ValueError as error:
            wx.MessageBox(str(error), "Cannot change table column", wx.OK | wx.ICON_WARNING, self)
            return
        self.GetParent().canvas.Refresh()
        self.GetParent().SetStatusText(f"Updated table column {column['name']}")


class SortRecordsDialog(wx.Dialog):
    def __init__(self, parent, dataset_contract, sort_items):
        super().__init__(parent, title="Sort Report Records", size=(620, 390))
        self.fields = [
            (collection.name, field.name, f"{collection.label}: {field.label}")
            for collection in dataset_contract.collections
            for field in collection.fields
            if field.data_type != "image"
        ]
        self.items = [dict(item) for item in sort_items]
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(
            wx.StaticText(
                self,
                label="Add fields in priority order. The first field is the primary sort.",
            ), 0, wx.ALL, 10,
        )
        self.list = wx.ListBox(self)
        layout.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        choices = wx.BoxSizer(wx.HORIZONTAL)
        self.field_choice = wx.Choice(self, choices=[item[2] for item in self.fields])
        if self.fields:
            self.field_choice.SetSelection(0)
        self.direction_choice = wx.Choice(self, choices=["Ascending", "Descending"])
        self.direction_choice.SetSelection(0)
        add_button = wx.Button(self, label="Add Sort")
        add_button.Bind(wx.EVT_BUTTON, self.on_add)
        choices.Add(self.field_choice, 1, wx.RIGHT, 8)
        choices.Add(self.direction_choice, 0, wx.RIGHT, 8)
        choices.Add(add_button, 0)
        layout.Add(choices, 0, wx.EXPAND | wx.ALL, 10)

        actions = wx.BoxSizer(wx.HORIZONTAL)
        for label, handler in (
            ("Move Up", self.on_up), ("Move Down", self.on_down),
            ("Remove", self.on_remove),
        ):
            button = wx.Button(self, label=label)
            button.Bind(wx.EVT_BUTTON, handler)
            actions.Add(button, 0, wx.RIGHT, 8)
        actions.AddStretchSpacer()
        actions.Add(wx.Button(self, wx.ID_CANCEL), 0, wx.RIGHT, 8)
        actions.Add(wx.Button(self, wx.ID_OK), 0)
        layout.Add(actions, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.SetSizer(layout)
        self.refresh()

    def refresh(self, selection=None):
        names = {(collection, field): label for collection, field, label in self.fields}
        labels = [
            f"{number}. {names.get((item['collection'], item['field']), item['collection'] + '.' + item['field'])}"
            f" — {item['direction'].title()}"
            for number, item in enumerate(self.items, start=1)
        ]
        self.list.Set(labels)
        if labels:
            self.list.SetSelection(min(selection if selection is not None else 0, len(labels) - 1))

    def on_add(self, event):
        selection = self.field_choice.GetSelection()
        if selection == wx.NOT_FOUND:
            return
        collection, field, _ = self.fields[selection]
        self.items = [
            item for item in self.items
            if (item["collection"], item["field"]) != (collection, field)
        ]
        self.items.append({
            "collection": collection,
            "field": field,
            "direction": self.direction_choice.GetStringSelection().casefold(),
        })
        self.refresh(len(self.items) - 1)

    def on_remove(self, event):
        selection = self.list.GetSelection()
        if selection != wx.NOT_FOUND:
            del self.items[selection]
            self.refresh(max(0, selection - 1))

    def _move(self, offset):
        selection = self.list.GetSelection()
        target = selection + offset
        if selection == wx.NOT_FOUND or target < 0 or target >= len(self.items):
            return
        self.items[selection], self.items[target] = self.items[target], self.items[selection]
        self.refresh(target)

    def on_up(self, event):
        self._move(-1)

    def on_down(self, event):
        self._move(1)

    def values(self):
        return [dict(item) for item in self.items]


class GroupRecordsDialog(wx.Dialog):
    def __init__(self, parent, dataset_contract, groups):
        super().__init__(parent, title="Group Report Records", size=(620, 390))
        self.fields = [
            (collection.name, field.name, f"{collection.label}: {field.label}")
            for collection in dataset_contract.collections
            for field in collection.fields
            if field.data_type != "image"
        ]
        self.items = [dict(item) for item in groups]
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(
            wx.StaticText(
                self,
                label="Groups create editable heading and footer sections. Outer groups come first.",
            ), 0, wx.ALL, 10,
        )
        self.list = wx.ListBox(self)
        layout.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        add_row = wx.BoxSizer(wx.HORIZONTAL)
        self.field_choice = wx.Choice(self, choices=[item[2] for item in self.fields])
        if self.fields:
            self.field_choice.SetSelection(0)
        self.keep_together = wx.CheckBox(self, label="Keep heading with first record")
        self.keep_together.SetValue(True)
        add_button = wx.Button(self, label="Add Group")
        add_button.Bind(wx.EVT_BUTTON, self.on_add)
        add_row.Add(self.field_choice, 1, wx.RIGHT, 8)
        add_row.Add(self.keep_together, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        add_row.Add(add_button, 0)
        layout.Add(add_row, 0, wx.EXPAND | wx.ALL, 10)

        actions = wx.BoxSizer(wx.HORIZONTAL)
        for label, handler in (
            ("Move Up", self.on_up), ("Move Down", self.on_down),
            ("Remove", self.on_remove),
        ):
            button = wx.Button(self, label=label)
            button.Bind(wx.EVT_BUTTON, handler)
            actions.Add(button, 0, wx.RIGHT, 8)
        actions.AddStretchSpacer()
        actions.Add(wx.Button(self, wx.ID_CANCEL), 0, wx.RIGHT, 8)
        actions.Add(wx.Button(self, wx.ID_OK), 0)
        layout.Add(actions, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.SetSizer(layout)
        self.refresh()

    def refresh(self, selection=None):
        names = {(collection, field): label for collection, field, label in self.fields}
        labels = [
            f"{number}. {names.get((item['collection'], item['field']), item['collection'] + '.' + item['field'])}"
            for number, item in enumerate(self.items, start=1)
        ]
        self.list.Set(labels)
        if labels:
            self.list.SetSelection(min(selection if selection is not None else 0, len(labels) - 1))

    def on_add(self, event):
        selection = self.field_choice.GetSelection()
        if selection == wx.NOT_FOUND:
            return
        collection, field, _ = self.fields[selection]
        if any(
            (item["collection"], item["field"]) == (collection, field) for item in self.items
        ):
            return
        used = {item["name"] for item in self.items}
        number = 1
        while f"Group{number}" in used:
            number += 1
        name = f"Group{number}"
        self.items.append({
            "name": name, "collection": collection, "field": field,
            "headerband": f"{name}Header", "footerband": f"{name}Footer",
            "keeptogether": self.keep_together.GetValue(),
        })
        self.refresh(len(self.items) - 1)

    def on_remove(self, event):
        selection = self.list.GetSelection()
        if selection != wx.NOT_FOUND:
            del self.items[selection]
            self.refresh(max(0, selection - 1))

    def _move(self, offset):
        selection = self.list.GetSelection()
        target = selection + offset
        if selection == wx.NOT_FOUND or target < 0 or target >= len(self.items):
            return
        self.items[selection], self.items[target] = self.items[target], self.items[selection]
        self.refresh(target)

    def on_up(self, event):
        self._move(-1)

    def on_down(self, event):
        self._move(1)

    def values(self):
        return [dict(item) for item in self.items]


class AddTotalDialog(wx.Dialog):
    def __init__(self, parent, dataset_contract, groups):
        super().__init__(parent, title="Add Report Total", size=(460, 300))
        self.fields = [
            (collection.name, field.name, field.data_type, f"{collection.label}: {field.label}")
            for collection in dataset_contract.collections
            for field in collection.fields
            if field.data_type != "image"
        ]
        self.groups = list(groups)
        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(cols=2, vgap=10, hgap=10)
        grid.AddGrowableCol(1, 1)
        grid.Add(wx.StaticText(panel, label="Field"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.field_choice = wx.Choice(panel, choices=[item[3] for item in self.fields])
        if self.fields:
            self.field_choice.SetSelection(0)
        grid.Add(self.field_choice, 1, wx.EXPAND)
        grid.Add(wx.StaticText(panel, label="Calculation"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.operation = wx.Choice(
            panel, choices=["Count", "Sum", "Average", "Minimum", "Maximum"],
        )
        self.operation.SetSelection(0)
        grid.Add(self.operation, 1, wx.EXPAND)
        grid.Add(wx.StaticText(panel, label="Total for"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.scope = wx.Choice(
            panel, choices=["Entire report"] + [f"Each {item['name']}" for item in self.groups],
        )
        self.scope.SetSelection(0)
        grid.Add(self.scope, 1, wx.EXPAND)
        layout.Add(grid, 1, wx.EXPAND | wx.ALL, 15)
        buttons = wx.StdDialogButtonSizer()
        buttons.AddButton(wx.Button(panel, wx.ID_OK))
        buttons.AddButton(wx.Button(panel, wx.ID_CANCEL))
        buttons.Realize()
        layout.Add(buttons, 0, wx.ALIGN_RIGHT | wx.ALL, 12)
        panel.SetSizer(layout)

    def values(self):
        collection, field, data_type, _ = self.fields[self.field_choice.GetSelection()]
        scope_selection = self.scope.GetSelection()
        group = self.groups[scope_selection - 1]["name"] if scope_selection > 0 else None
        operation = self.operation.GetStringSelection().casefold()
        format_name = data_type if data_type in ("integer", "decimal", "currency") else None
        if operation == "count":
            format_name = "integer"
        return collection, field, operation, ("group" if group else "report"), group, format_name


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
        starter_definition_path=None, export_directory=None, protection_manifest=None,
    ):
        self.path = Path(definition_path)
        definition = ReportDefinitionLoader().load(self.path)
        self.protection_manifest = protection_manifest
        self.model = ReportDesignerModel(definition, protection_manifest=protection_manifest)
        self.dataset_contract = dataset_contract
        self.preview_handler = preview_handler
        self.control_clipboard = []
        self.starter_definition_path = (
            Path(starter_definition_path) if starter_definition_path else None
        )
        self.export_directory = Path(export_directory) if export_directory else self.path.parent
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
        self.customized_label = wx.StaticText(panel, label="CUSTOMIZED")
        self.customized_label.SetForegroundColour(wx.Colour(0, 102, 204))
        font = self.customized_label.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.customized_label.SetFont(font)
        primary_toolbar.Add(self.customized_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        toolbar.Add(primary_toolbar, 0, wx.EXPAND)
        self.canvas = ReportCanvas(
            panel, self.model, self.on_selection, self.delete_selected_control,
            self.activate_control,
        )
        self.refresh_customized_indicator()
        controls_panel = wx.Panel(panel, style=wx.BORDER_SIMPLE)
        controls_layout = wx.BoxSizer(wx.VERTICAL)
        controls_layout.Add(wx.StaticText(controls_panel, label="Report Controls"), 0, wx.ALL, 8)
        self.control_list = wx.ListBox(
            controls_panel, choices=list(self.model.controls.keys()), style=wx.LB_EXTENDED,
        )
        self.control_list.Bind(wx.EVT_LISTBOX, self.on_control_list_selection)
        self.control_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_control_list_double_click)
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
        properties_panel = wx.ScrolledWindow(panel, style=wx.BORDER_SIMPLE)
        properties_panel.SetScrollRate(0, 10)
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
        for key, label in (("label", "Label"), ("prefix", "Prefix"), ("collection", "Collection"), ("field", "Field")):
            grid.Add(wx.StaticText(properties_panel, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            editor = wx.TextCtrl(properties_panel, style=wx.TE_PROCESS_ENTER)
            editor.Bind(wx.EVT_TEXT_ENTER, lambda event, property_name=key: self.on_text_property(event, property_name))
            editor.Bind(wx.EVT_KILL_FOCUS, lambda event, property_name=key: self.on_text_property(event, property_name))
            self.property_controls[key] = editor
            grid.Add(editor, 1, wx.EXPAND)
        grid.Add(wx.StaticText(properties_panel, label="Report value"), 0, wx.ALIGN_CENTER_VERTICAL)
        system_value = wx.Choice(
            properties_panel,
            choices=["run_date", "run_datetime", "page_number", "report_title", "report_code"],
        )
        system_value.Bind(wx.EVT_CHOICE, self.on_style_change)
        self.property_controls["systemvalue"] = system_value
        grid.Add(system_value, 1, wx.EXPAND)
        grid.Add(wx.StaticText(properties_panel, label="Font"), 0, wx.ALIGN_CENTER_VERTICAL)
        font = wx.Choice(properties_panel, choices=["Helvetica", "Times-Roman", "Courier"])
        font.Bind(wx.EVT_CHOICE, self.on_style_change)
        self.property_controls["font"] = font
        grid.Add(font, 1, wx.EXPAND)
        grid.Add(wx.StaticText(properties_panel, label="Data format"), 0, wx.ALIGN_CENTER_VERTICAL)
        data_format = wx.Choice(
            properties_panel,
            choices=["text", "integer", "decimal", "currency", "date", "time", "datetime", "boolean", "phone", "address"],
        )
        data_format.Bind(wx.EVT_CHOICE, self.on_style_change)
        self.property_controls["format"] = data_format
        grid.Add(data_format, 1, wx.EXPAND)
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
        grid.Add(wx.StaticText(properties_panel, label="Vertical"), 0, wx.ALIGN_CENTER_VERTICAL)
        vertical = wx.Choice(properties_panel, choices=["top", "middle", "bottom"])
        vertical.Bind(wx.EVT_CHOICE, self.on_style_change)
        self.property_controls["verticalalign"] = vertical
        grid.Add(vertical, 1, wx.EXPAND)
        for key, label, default in (
            ("color", "Text color", "#000000"),
            ("background", "Background", "#FFFFFF"),
            ("bordercolor", "Border color", "#000000"),
        ):
            grid.Add(wx.StaticText(properties_panel, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            editor = wx.ColourPickerCtrl(properties_panel, colour=default)
            editor.Bind(wx.EVT_COLOURPICKER_CHANGED, self.on_style_change)
            self.property_controls[key] = editor
            grid.Add(editor, 1, wx.EXPAND)
        grid.Add(wx.StaticText(properties_panel, label="Border width"), 0, wx.ALIGN_CENTER_VERTICAL)
        border_width = wx.SpinCtrlDouble(properties_panel, min=0, max=10, initial=0, inc=0.5)
        border_width.SetDigits(1)
        border_width.Bind(wx.EVT_SPINCTRLDOUBLE, self.on_style_change)
        self.property_controls["borderwidth"] = border_width
        grid.Add(border_width, 1, wx.EXPAND)
        grid.Add(wx.StaticText(properties_panel, label="Visible"), 0, wx.ALIGN_CENTER_VERTICAL)
        visible = wx.CheckBox(properties_panel)
        visible.Bind(wx.EVT_CHECKBOX, self.on_style_change)
        self.property_controls["visible"] = visible
        grid.Add(visible, 0)
        properties_layout.Add(grid, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        self.edit_repeater_button = wx.Button(properties_panel, label="Edit Repeating Columns")
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
            self._append_menu(file_menu, "&Export PDF...\tCtrl+E", self.on_export_pdf)
        self._append_menu(file_menu, "Page Set&up...", self.on_page_setup)
        if self.starter_definition_path is not None:
            self._append_menu(file_menu, "&Restore Starter...", self.on_restore_starter)
        self._append_menu(file_menu, "&Delete Customization...", self.on_delete_customization)
        self._append_menu(file_menu, "Restore Previous &Version...", self.on_restore_previous)
        file_menu.AppendSeparator()
        self._append_menu(file_menu, "E&xit", lambda event: self.Close())
        menu_bar.Append(file_menu, "&File")

        edit_menu = wx.Menu()
        self._append_menu(edit_menu, "&Undo\tCtrl+Z", self.on_undo)
        self._append_menu(edit_menu, "&Redo\tCtrl+Y", self.on_redo)
        edit_menu.AppendSeparator()
        self._append_menu(edit_menu, "&Copy\tCtrl+C", self.on_copy)
        self._append_menu(edit_menu, "&Paste\tCtrl+V", self.on_paste)
        self._append_menu(edit_menu, "D&uplicate\tCtrl+D", self.on_duplicate)
        edit_menu.AppendSeparator()
        self._append_menu(edit_menu, "&Delete\tDel", self.on_delete_control)
        menu_bar.Append(edit_menu, "&Edit")

        insert_menu = wx.Menu()
        for control_type, label in (("label", "Label"), ("systemtext", "Report Value"), ("line", "Line"), ("rectangle", "Box")):
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

        if self.dataset_contract is not None:
            data_menu = wx.Menu()
            self._append_menu(data_menu, "&Sort Records...", self.on_sort_records)
            self._append_menu(data_menu, "&Group Records...", self.on_group_records)
            data_menu.AppendSeparator()
            self._append_menu(data_menu, "Add &Total...", self.on_add_total)
            self._append_menu(data_menu, "Add &Matrix...", self.on_add_matrix)
            data_menu.AppendSeparator()
            self._append_menu(data_menu, "Set Conditional &Visibility...", self.on_visibility_condition)
            menu_bar.Append(data_menu, "&Data")

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
            "Ctrl+C copies, Ctrl+V pastes, and Ctrl+D duplicates.\n"
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
        for key in ("label", "prefix", "collection", "field"):
            editor = self.property_controls[key]
            editor.SetValue(str(control.get(key, "")))
            required = key in ("collection", "field") and control["type"] in ("text", "image")
            supported = (
                (key == "label" and control["type"] == "label")
                or (key == "prefix" and control["type"] == "systemtext")
                or (key in ("collection", "field") and control["type"] in ("text", "image"))
            )
            editor.Enable(required or supported)
        self.property_controls["label"].Enable(control["type"] == "label")
        self.property_controls["systemvalue"].SetStringSelection(control.get("systemvalue", "run_date"))
        self.property_controls["systemvalue"].Enable(control["type"] == "systemtext")
        self.property_controls["fontsize"].SetValue(control.get("fontsize", 10))
        self.property_controls["bold"].SetValue(control.get("bold", False))
        self.property_controls["italic"].SetValue(control.get("italic", False))
        self.property_controls["align"].SetStringSelection(control.get("align", "left"))
        self.property_controls["verticalalign"].SetStringSelection(control.get("verticalalign", "middle"))
        self.property_controls["font"].SetStringSelection(control.get("font", "Helvetica"))
        self.property_controls["format"].SetStringSelection(control.get("format", "text"))
        self.property_controls["format"].Enable(control["type"] in ("text", "systemtext", "aggregate"))
        for key, default in (("color", "#000000"), ("background", "#FFFFFF"), ("bordercolor", "#000000")):
            self.property_controls[key].SetColour(control.get(key, default))
        self.property_controls["borderwidth"].SetValue(control.get("borderwidth", 0))
        self.property_controls["visible"].SetValue(control.get("visible", True))
        editable_columns = control["type"] in ("repeater", "table")
        self.edit_repeater_button.SetLabel(
            "Edit Table Columns" if control["type"] == "table" else "Edit Repeating Columns"
        )
        self.edit_repeater_button.Enable(editable_columns)
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
        except (ReportDefinitionError, ValueError) as error:
            self.SetStatusText(str(error))
        self.refresh_selected()
        event.Skip()

    def on_style_change(self, event):
        if getattr(self, "updating_properties", False) or not self.model.selected:
            return
        source = event.GetEventObject()
        key = next(key for key, editor in self.property_controls.items() if editor is source)
        if key in ("bold", "italic", "visible"):
            value = source.GetValue()
        elif key in ("align", "verticalalign", "font", "format", "systemvalue"):
            value = source.GetStringSelection()
        elif key in ("color", "background", "bordercolor"):
            colour = source.GetColour()
            value = f"#{colour.Red():02X}{colour.Green():02X}{colour.Blue():02X}"
        else:
            value = source.GetValue()
        try:
            self.model.set_property(self.model.selected, key, value)
            self.SetStatusText(f"Updated {key}")
        except (ReportDefinitionError, ValueError) as error:
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

    def on_control_list_double_click(self, event):
        name = self.control_list.GetString(event.GetSelection())
        self.canvas.selected_names = {name}
        self.model.select(name)
        self.on_selection(name)
        self.activate_control(name)

    def activate_control(self, name):
        control = self.model.controls[name]
        if control["type"] in ("repeater", "table"):
            self.on_edit_repeater(None)
            return
        if control["type"] == "label":
            editor = self.property_controls["label"]
        elif control["type"] in ("text", "image"):
            editor = self.property_controls["field"]
        else:
            editor = self.property_controls["width"]
        editor.SetFocus()
        if isinstance(editor, wx.TextCtrl):
            editor.SelectAll()
        self.SetStatusText(f"Editing {name}")

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
        if not name or self.model.controls[name]["type"] not in ("repeater", "table"):
            self.SetStatusText("Select a repeating detail or table control first")
            return
        dialog_class = (
            RepeaterItemsDialog if self.model.controls[name]["type"] == "repeater"
            else TableColumnsDialog
        )
        dialog = dialog_class(self, self.model, name)
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

    def on_copy(self, event):
        self.control_clipboard = self.model.copy_controls(self.canvas.selected_names)
        self.SetStatusText(f"Copied {len(self.control_clipboard)} control(s)")

    def on_paste(self, event):
        try:
            created = self.model.paste_controls(self.control_clipboard)
        except ValueError as error:
            self.SetStatusText(str(error))
            return
        self.canvas.selected_names = set(created)
        self.refresh_control_list()
        self.on_selection(self.model.selected)
        self.canvas.reveal_control(self.model.selected)
        self.SetStatusText(f"Pasted {len(created)} control(s)")

    def on_duplicate(self, event):
        copied = self.model.copy_controls(self.canvas.selected_names)
        try:
            created = self.model.paste_controls(copied)
        except ValueError as error:
            self.SetStatusText(str(error))
            return
        self.canvas.selected_names = set(created)
        self.refresh_control_list()
        self.on_selection(self.model.selected)
        self.canvas.reveal_control(self.model.selected)
        self.SetStatusText(f"Duplicated {len(created)} control(s)")

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
        try:
            self.model.delete_control(name)
        except ValueError as error:
            wx.MessageBox(str(error), "Protected report control", wx.OK | wx.ICON_INFORMATION, self)
            return
        self.canvas.selected_names.discard(name)
        self.refresh_control_list()
        self.on_selection(None)
        self.canvas.Refresh()
        self.SetStatusText(f"Deleted {name}")

    def refresh_customized_indicator(self):
        customized = False
        if self.starter_definition_path and self.starter_definition_path.is_file():
            try:
                starter = ReportDefinitionLoader().load(self.starter_definition_path)
                customized = self.model.data != starter.to_dict()
            except Exception:
                customized = True
        elif self.starter_definition_path is None:
            customized = True
        self.customized_label.Show(customized)
        self.customized_label.GetParent().Layout()

    def on_save(self, event):
        self.model.save(self.path)
        self.refresh_customized_indicator()
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
        self.refresh_customized_indicator()
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

    def on_sort_records(self, event):
        dialog = SortRecordsDialog(
            self, self.dataset_contract, self.model.report.get("sort", ()),
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            sort_items = dialog.values()
        finally:
            dialog.Destroy()
        try:
            self.model.set_sort(sort_items)
            self.dataset_contract.validate_definition(self.model.validated_definition())
        except (ReportDefinitionError, ValueError) as error:
            wx.MessageBox(str(error), "Cannot change sorting", wx.OK | wx.ICON_ERROR, self)
            return
        self.SetStatusText(
            f"Report sorting updated ({len(sort_items)} field{'s' if len(sort_items) != 1 else ''})"
        )

    def on_group_records(self, event):
        dialog = GroupRecordsDialog(
            self, self.dataset_contract, self.model.report.get("groups", ()),
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            groups = dialog.values()
        finally:
            dialog.Destroy()
        try:
            self.model.set_groups(groups)
            self.dataset_contract.validate_definition(self.model.validated_definition())
        except (ReportDefinitionError, ValueError) as error:
            wx.MessageBox(str(error), "Cannot change grouping", wx.OK | wx.ICON_ERROR, self)
            return
        self.canvas.refresh_extent()
        self.band_list.Set(list(self.model.report["bands"]))
        self.refresh_control_list()
        self.on_selection(self.model.selected)
        self.SetStatusText(
            f"Report grouping updated ({len(groups)} group{'s' if len(groups) != 1 else ''})"
        )

    def on_add_total(self, event):
        dialog = AddTotalDialog(
            self, self.dataset_contract, self.model.report.get("groups", ()),
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            values = dialog.values()
        finally:
            dialog.Destroy()
        try:
            name = self.model.add_aggregate(*values)
            self.dataset_contract.validate_definition(self.model.validated_definition())
        except (ReportDefinitionError, ValueError) as error:
            wx.MessageBox(str(error), "Cannot add total", wx.OK | wx.ICON_ERROR, self)
            return
        self.canvas.selected_names = {name}
        self.canvas.refresh_extent()
        self.band_list.Set(list(self.model.report["bands"]))
        self.refresh_control_list()
        self.on_selection(name)
        self.canvas.reveal_control(name)
        self.SetStatusText("Report total added; position and format it like any other control")

    def on_add_matrix(self, event):
        collections = [item for item in self.dataset_contract.collections if len(item.fields) >= 3]
        if not collections:
            self.SetStatusText("No approved collection has enough fields for a matrix")
            return
        dialog = wx.SingleChoiceDialog(
            self, "Choose the repeating data collection.", "Add Matrix",
            [item.label for item in collections],
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            collection = collections[dialog.GetSelection()]
        finally:
            dialog.Destroy()

        def choose(prompt, candidates):
            if not candidates:
                return None
            chooser = wx.SingleChoiceDialog(
                self, prompt, "Add Matrix", [item.label for item in candidates],
            )
            try:
                if chooser.ShowModal() != wx.ID_OK:
                    return None
                return candidates[chooser.GetSelection()]
            finally:
                chooser.Destroy()

        fields = list(collection.fields)
        row = choose("Choose the row field.", fields)
        if row is None:
            return
        column = choose("Choose the dynamic column field.", fields)
        if column is None:
            return
        numeric = [item for item in fields if item.data_type in ("integer", "decimal", "currency")]
        value = choose("Choose the numeric value field.", numeric)
        if value is None:
            self.SetStatusText("A matrix requires an approved numeric value field")
            return
        try:
            name = self.model.add_matrix(
                collection.name, row.name, column.name, value.name, row.label,
            )
            self.dataset_contract.validate_definition(self.model.validated_definition())
        except (ReportDefinitionError, ValueError) as error:
            wx.MessageBox(str(error), "Cannot add matrix", wx.OK | wx.ICON_ERROR, self)
            return
        self.canvas.selected_names = {name}
        self.refresh_control_list()
        self.on_selection(name)
        self.canvas.reveal_control(name)
        self.SetStatusText("Matrix added; dynamic columns will appear in preview")

    def on_visibility_condition(self, event):
        name = self.model.selected
        if not name:
            self.SetStatusText("Select a report control first")
            return
        bindings = [
            (collection.name, field.name, f"{collection.label}: {field.label}")
            for collection in self.dataset_contract.collections for field in collection.fields
        ]
        field_dialog = wx.SingleChoiceDialog(
            self, "Show this control based on which approved field?",
            "Conditional Visibility", [item[2] for item in bindings],
        )
        try:
            if field_dialog.ShowModal() != wx.ID_OK:
                return
            collection, field, _ = bindings[field_dialog.GetSelection()]
        finally:
            field_dialog.Destroy()
        operators = ["equals", "not_equals", "empty", "not_empty"]
        operator_dialog = wx.SingleChoiceDialog(
            self, "Choose the condition.", "Conditional Visibility", operators,
        )
        try:
            if operator_dialog.ShowModal() != wx.ID_OK:
                return
            operator = operators[operator_dialog.GetSelection()]
        finally:
            operator_dialog.Destroy()
        condition = {"collection": collection, "field": field, "operator": operator}
        if operator in ("equals", "not_equals"):
            value_dialog = wx.TextEntryDialog(
                self, "Enter the exact value to compare.", "Conditional Visibility",
            )
            try:
                if value_dialog.ShowModal() != wx.ID_OK:
                    return
                condition["value"] = value_dialog.GetValue()
            finally:
                value_dialog.Destroy()
        try:
            self.model.set_visibility_condition(name, condition)
            self.dataset_contract.validate_definition(self.model.validated_definition())
        except (ReportDefinitionError, ValueError) as error:
            wx.MessageBox(str(error), "Cannot set condition", wx.OK | wx.ICON_ERROR, self)
            return
        self.refresh_selected()
        self.SetStatusText(f"Conditional visibility set for {name}")

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
            if self.protection_manifest is not None:
                self.protection_manifest.validate(definition)
            if self.dataset_contract is not None:
                self.dataset_contract.validate_definition(definition)
        except (ReportDefinitionError, ValueError) as error:
            wx.MessageBox(str(error), "Cannot open report", wx.OK | wx.ICON_ERROR, self)
            return
        replacement = ReportDesignerFrame(
            selected_path, dataset_contract=self.dataset_contract,
            preview_handler=self.preview_handler,
            starter_definition_path=self.starter_definition_path,
            export_directory=self.export_directory,
            protection_manifest=self.protection_manifest,
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

    def on_export_pdf(self, event):
        dialog = wx.FileDialog(
            self, "Export report as PDF", defaultDir=str(self.export_directory),
            defaultFile=f"{self.model.report['name']}.pdf",
            wildcard="PDF files (*.pdf)|*.pdf",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            target = Path(dialog.GetPath())
        finally:
            dialog.Destroy()
        if target.suffix.casefold() != ".pdf":
            target = target.with_suffix(".pdf")
        try:
            definition = self.model.validated_definition()
            output = self.preview_handler(definition)
            export_preview_file(output, target)
        except Exception as error:
            wx.MessageBox(str(error), "Cannot export report", wx.OK | wx.ICON_ERROR, self)
            return
        self.SetStatusText(f"Exported PDF: {target}")

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
        self.refresh_customized_indicator()

    def on_restore_previous(self, event):
        backup = self.path.with_suffix(self.path.suffix + ".bak")
        if not backup.is_file():
            wx.MessageBox(
                "No previous saved version exists for this report yet.",
                "Restore previous version", wx.OK | wx.ICON_INFORMATION, self,
            )
            return
        dialog = wx.MessageDialog(
            self,
            "Load the previous saved version?\n\n"
            "The current file will not change until you click Save.",
            "Restore previous version",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )
        try:
            if dialog.ShowModal() != wx.ID_YES:
                return
        finally:
            dialog.Destroy()
        try:
            definition = ReportDefinitionLoader().load(backup)
            if self.dataset_contract is not None:
                self.dataset_contract.validate_definition(definition)
            previous_controls = definition.to_dict()[definition.root_name]["CONTROLS"]
            changed = [
                name for name in set(self.model.controls) | set(previous_controls)
                if self.model.controls.get(name) != previous_controls.get(name)
            ]
            self.model.replace_definition(definition)
        except (ReportDefinitionError, ValueError) as error:
            wx.MessageBox(str(error), "Cannot restore previous version", wx.OK | wx.ICON_ERROR, self)
            return
        self.canvas.model = self.model
        if changed and changed[0] in self.model.controls:
            self.model.select(changed[0])
        self.canvas.selected_names = {self.model.selected} if self.model.selected else set()
        self.canvas.refresh_extent()
        self.refresh_control_list()
        self.on_selection(self.model.selected)
        if self.model.selected:
            self.canvas.reveal_control(self.model.selected)
        self.SetStatusText(
            f"Previous version loaded ({len(changed)} changed control(s)); click Save to keep it"
        )
        wx.MessageBox(
            f"The previous version is now displayed.\n\n"
            f"Changed controls: {len(changed)}\n"
            "Click Save to make this restoration permanent.",
            "Previous version loaded", wx.OK | wx.ICON_INFORMATION, self,
        )

    def on_delete_customization(self, event):
        has_starter = bool(
            self.starter_definition_path and self.starter_definition_path.is_file()
        )
        if has_starter and self.path.resolve() == self.starter_definition_path.resolve():
            wx.MessageBox(
                "This report is already using its starter definition.",
                "No customization", wx.OK | wx.ICON_INFORMATION, self,
            )
            return
        message = (
            "Delete this customized layout and return to the shipped starter?"
            if has_starter else
            "Permanently delete this user-created report definition?"
        )
        dialog = wx.MessageDialog(
            self, message, "Delete customization",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )
        try:
            if dialog.ShowModal() != wx.ID_YES:
                return
        finally:
            dialog.Destroy()
        for target in (self.path, self.path.with_suffix(self.path.suffix + ".bak")):
            if target.is_file():
                target.unlink()
        self.model.dirty = False
        self.Destroy()

    def on_close(self, event):
        if not self.confirm_discard_or_save():
            event.Veto()
            return
        event.Skip()


def open_report_designer(
    definition_path, dataset_contract=None, preview_handler=None,
    starter_definition_path=None, export_directory=None, protection_manifest=None,
):
    application = wx.App.Get() or wx.App(False)
    frame = ReportDesignerFrame(
        definition_path, dataset_contract=dataset_contract,
        preview_handler=preview_handler,
        starter_definition_path=starter_definition_path,
        export_directory=export_directory,
        protection_manifest=protection_manifest,
    )
    frame.Show()
    if not wx.App.Get().IsMainLoopRunning():
        application.MainLoop()
    return frame
