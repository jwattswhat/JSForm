"""Responsive wxPython layout support for JSForm forms."""

from dataclasses import dataclass


EXPANDING_TYPES = {
    "CheckListBox", "CheckListEdit", "DataViewListCtrl", "FilePickerCtrl",
    "HTMLCtrl", "JSON", "ListCtrl", "ListCtrlID", "MultiLine", "TextCtrl",
}
VERTICALLY_EXPANDING_TYPES = {
    "CheckListBox", "CheckListEdit", "DataViewListCtrl", "HTMLCtrl", "JSON",
    "ListCtrl", "ListCtrlID", "MultiLine",
}
NAVIGATION_NAMES = (
    "btnFirst", "btnPrev", "btnNext", "btnLast", "btnNew", "btnUpdate",
    "btnDelete", "btnClose",
)


def supports_responsive_layout(form_description, control_descriptions):
    """Return whether a form can safely use the automatic grid migration."""
    layout = form_description.get("layout", {})
    mode = layout.get("type", "auto") if isinstance(layout, dict) else layout
    if mode == "legacy":
        return False
    if mode == "responsive":
        return True
    if form_description.get("type") == "StaticBox":
        return False
    grouped = grouped_controls(control_descriptions)
    assigned = {name for members in grouped.values() for name in members}
    top_level = {
        name: description for name, description in control_descriptions.items()
        if name not in assigned
    }
    collections = [top_level] + [
        {name: control_descriptions[name] for name in members}
        for members in grouped.values()
    ]
    for collection in collections:
        positions = []
        for name, description in collection.items():
            if name in NAVIGATION_NAMES:
                continue
            if "posch" not in description and not {
                "row", "column"
            }.intersection(description.get("layout", {})):
                return False
            positions.append(_logical_position(description))
        if len(positions) != len(set(positions)):
            return False
    return True


def grouped_controls(descriptions):
    """Map each StaticBox to controls positioned inside its logical bounds."""
    groups = {}
    assigned = set()
    boxes = {
        name: description for name, description in descriptions.items()
        if description.get("type") == "StaticBox" and description.get("posch")
        and description.get("sizech")
    }
    for box_name, box in boxes.items():
        left, top = box["posch"]
        width, height = box["sizech"]
        members = []
        for name, description in descriptions.items():
            if name == box_name or description.get("type") == "StaticBox":
                continue
            position = description.get("posch")
            if not position:
                continue
            x, y = position
            if left < x < left + width and top < y < top + height:
                if name in assigned:
                    return {}
                members.append(name)
                assigned.add(name)
        groups[box_name] = members
    return groups


@dataclass(frozen=True)
class LayoutItem:
    name: str
    row: int
    column: int
    row_span: int = 1
    column_span: int = 1
    expand: bool = False
    proportion: int = 0


def _logical_position(description):
    layout = description.get("layout", {})
    if "row" in layout or "column" in layout:
        return layout.get("row", 0), layout.get("column", 0)
    return tuple(description.get("posch", (0, 0))[::-1])


def build_layout_plan(descriptions, include_navigation=True):
    """Convert logical positions into dense sizer rows and columns."""
    content = {
        name: description for name, description in descriptions.items()
        if name not in NAVIGATION_NAMES and not description.get("layout", {}).get("hidden")
    }
    positions = {name: _logical_position(description) for name, description in content.items()}
    rows = {value: index for index, value in enumerate(sorted({pos[0] for pos in positions.values()}))}
    columns = {value: index for index, value in enumerate(sorted({pos[1] for pos in positions.values()}))}
    result = []
    for name, description in content.items():
        layout = description.get("layout", {})
        row, column = positions[name]
        control_type = description.get("type")
        result.append(LayoutItem(
            name, rows[row], columns[column],
            max(1, int(layout.get("row_span", 1))),
            max(1, int(layout.get("column_span", 1))),
            bool(layout.get("expand", control_type in EXPANDING_TYPES)),
            max(0, int(layout.get("proportion", 1 if control_type in EXPANDING_TYPES else 0))),
        ))
    if include_navigation:
        navigation_row = len(rows)
        for column, name in enumerate(name for name in NAVIGATION_NAMES if name in descriptions):
            result.append(LayoutItem(name, navigation_row, column))
    return result


def layout_spacing(settings=None):
    """Return compact grid spacing and per-control padding."""
    settings = settings or {}
    gap = max(0, int(settings.get("gap", 2)))
    border = max(0, int(settings.get("border", 2)))
    item_padding = max(0, int(settings.get("item_padding", border // 2)))
    return gap, border, item_padding


def frame_position(area, size, requested=None, margin=8):
    """Center or clamp a frame inside the usable display, including its header."""
    left, top, available_width, available_height = area
    width, height = size
    minimum_x = left + margin
    minimum_y = top + margin
    maximum_x = max(minimum_x, left + available_width - width - margin)
    maximum_y = max(minimum_y, top + available_height - height - margin)
    if requested is None:
        x = left + (available_width - width) // 2
        y = top + (available_height - height) // 2
    else:
        x, y = requested
    return min(max(x, minimum_x), maximum_x), min(max(y, minimum_y), maximum_y)


def apply_responsive_layout(form, frame, controls, descriptions, settings=None):
    """Attach a GridBagSizer and constrain the initial window to the display."""
    import wx

    settings = settings or {}
    gap, border, item_padding = layout_spacing(settings)
    groups = grouped_controls(descriptions)
    assigned = {name for members in groups.values() for name in members}
    top_descriptions = {
        name: description for name, description in descriptions.items()
        if name not in assigned
    }
    content_sizer = wx.GridBagSizer(gap, gap)
    plan = build_layout_plan(top_descriptions, include_navigation=False)
    expanding_rows = set()
    expanding_columns = set()
    for item in plan:
        flags = wx.ALL | wx.ALIGN_CENTER_VERTICAL
        window_or_sizer = controls[item.name]
        is_group = item.name in groups
        if is_group:
            inner = wx.GridBagSizer(gap, gap)
            inner_plan = build_layout_plan({
                name: descriptions[name] for name in groups[item.name]
            })
            inner_rows = set()
            inner_columns = set()
            for child in inner_plan:
                child_flags = wx.ALL | wx.ALIGN_CENTER_VERTICAL
                if child.expand:
                    child_flags |= wx.EXPAND
                    inner_columns.add(child.column)
                    if descriptions[child.name].get("type") in VERTICALLY_EXPANDING_TYPES:
                        inner_rows.add(child.row)
                inner.Add(
                    controls[child.name], pos=(child.row, child.column),
                    span=(child.row_span, child.column_span), flag=child_flags,
                    border=item_padding,
                )
            for row in inner_rows:
                inner.AddGrowableRow(row, 1)
            for column in inner_columns:
                inner.AddGrowableCol(column, 1)
            group_sizer = wx.StaticBoxSizer(controls[item.name], wx.VERTICAL)
            group_sizer.Add(inner, 1, wx.EXPAND | wx.ALL, item_padding)
            window_or_sizer = group_sizer
            flags |= wx.EXPAND
            expanding_columns.add(item.column)
            if any(
                descriptions[name].get("type") in VERTICALLY_EXPANDING_TYPES
                for name in groups[item.name]
            ):
                expanding_rows.add(item.row)
        if item.expand:
            flags |= wx.EXPAND
            expanding_columns.add(item.column)
            if descriptions[item.name].get("type") in VERTICALLY_EXPANDING_TYPES:
                expanding_rows.add(item.row)
        content_sizer.Add(
            window_or_sizer, pos=(item.row, item.column),
            span=(item.row_span, item.column_span), flag=flags, border=item_padding,
        )
    for row in expanding_rows:
        content_sizer.AddGrowableRow(row, 1)
    for column in expanding_columns:
        content_sizer.AddGrowableCol(column, 1)

    root_sizer = wx.BoxSizer(wx.VERTICAL)
    root_sizer.Add(content_sizer, 1, wx.EXPAND | wx.ALL, border)
    navigation = [name for name in NAVIGATION_NAMES if name in controls]
    if navigation:
        navigation_sizer = wx.BoxSizer(wx.HORIZONTAL)
        for name in navigation:
            if name == "btnClose":
                navigation_sizer.AddStretchSpacer(1)
            navigation_sizer.Add(controls[name], 0, wx.RIGHT, item_padding)
        root_sizer.Add(
            navigation_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border
        )
    form.SetSizer(root_sizer)
    form.Layout()
    if hasattr(form, "FitInside"):
        form.FitInside()
    desired = root_sizer.GetMinSize()
    display = wx.Display.GetFromWindow(frame)
    if display == wx.NOT_FOUND:
        display = 0
    area = wx.Display(display).GetClientArea()
    width = min(max(desired.width + 24, 360), int(area.width * 0.95))
    height = min(max(desired.height + 54, 240), int(area.height * 0.95))
    frame.SetMinSize((min(width, 480), min(height, 320)))
    frame.SetSize((width, height))
    requested = None if settings.get("center", True) else tuple(frame.GetPosition())
    frame.SetPosition(frame_position(
        (area.x, area.y, area.width, area.height), (width, height), requested
    ))
    frame.Layout()
    return root_sizer
