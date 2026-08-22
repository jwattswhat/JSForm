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
    if mode in {"responsive", "master_detail", "columns"}:
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


def _collection_positions(descriptions):
    """Use grid coordinates only when the whole layout level defines them."""
    visible = {
        name: description for name, description in descriptions.items()
        if name not in NAVIGATION_NAMES
        and not description.get("layout", {}).get("hidden")
    }
    use_grid = bool(visible) and all(
        "row" in description.get("layout", {})
        and "column" in description.get("layout", {})
        for description in visible.values()
    )
    if use_grid:
        return {
            name: (description["layout"]["row"], description["layout"]["column"])
            for name, description in visible.items()
        }
    return {
        name: tuple(description.get("posch", (0, 0))[::-1])
        for name, description in visible.items()
    }


def build_layout_plan(descriptions, include_navigation=True):
    """Convert logical positions into dense sizer rows and columns."""
    content = {
        name: description for name, description in descriptions.items()
        if name not in NAVIGATION_NAMES and not description.get("layout", {}).get("hidden")
    }
    positions = _collection_positions(content)
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


def master_detail_orientation(width, settings=None):
    """Choose side-by-side or stacked panes from the available client width."""
    settings = settings or {}
    return "vertical" if int(width) < int(settings.get("breakpoint", 850)) else "horizontal"


def master_detail_panes(descriptions):
    """Partition controls into master and detail panes, inheriting group roles."""
    groups = grouped_controls(descriptions)
    inherited = {
        child: descriptions[group].get("layout", {}).get("pane", "detail")
        for group, children in groups.items()
        for child in children
    }
    panes = {"master": {}, "detail": {}}
    for name, description in descriptions.items():
        if name in NAVIGATION_NAMES:
            continue
        pane = inherited.get(name, description.get("layout", {}).get("pane", "detail"))
        if pane not in panes:
            raise ValueError("Unknown master-detail pane: {}".format(pane))
        panes[pane][name] = description
    return panes


def column_layout_panes(descriptions):
    """Partition top-level controls into independently stacked columns."""
    groups = grouped_controls(descriptions)
    assigned = {name for members in groups.values() for name in members}
    top_level = {
        name: description for name, description in descriptions.items()
        if name not in assigned and name not in NAVIGATION_NAMES
        and not description.get("layout", {}).get("hidden")
    }
    columns = {}
    for name, description in top_level.items():
        column = _logical_position(description)[1]
        pane = columns.setdefault(column, {})
        pane[name] = description
        for child in groups.get(name, ()):
            pane[child] = descriptions[child]
    return tuple(columns[key] for key in sorted(columns))


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
    def build_content_grid(pane_descriptions):
        groups = grouped_controls(pane_descriptions)
        assigned = {name for members in groups.values() for name in members}
        top_descriptions = {
            name: description for name, description in pane_descriptions.items()
            if name not in assigned
        }
        content = wx.GridBagSizer(gap, gap)
        plan = build_layout_plan(top_descriptions, include_navigation=False)
        expanding_rows = set()
        expanding_columns = set()
        for item in plan:
            flags = wx.ALL | wx.ALIGN_CENTER_VERTICAL
            window_or_sizer = controls[item.name]
            if item.name in groups:
                inner = wx.GridBagSizer(gap, gap)
                inner_plan = build_layout_plan({
                    name: pane_descriptions[name] for name in groups[item.name]
                })
                inner_rows = set()
                inner_columns = set()
                for child in inner_plan:
                    child_flags = wx.ALL | wx.ALIGN_CENTER_VERTICAL
                    if child.expand:
                        child_flags |= wx.EXPAND
                        inner_columns.add(child.column)
                        if pane_descriptions[child.name].get("type") in VERTICALLY_EXPANDING_TYPES:
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
                    pane_descriptions[name].get("type") in VERTICALLY_EXPANDING_TYPES
                    for name in groups[item.name]
                ):
                    expanding_rows.add(item.row)
            if item.expand:
                flags |= wx.EXPAND
                expanding_columns.add(item.column)
                if pane_descriptions[item.name].get("type") in VERTICALLY_EXPANDING_TYPES:
                    expanding_rows.add(item.row)
            content.Add(
                window_or_sizer, pos=(item.row, item.column),
                span=(item.row_span, item.column_span), flag=flags, border=item_padding,
            )
        for row in expanding_rows:
            content.AddGrowableRow(row, 1)
        for column in expanding_columns:
            content.AddGrowableCol(column, 1)
        return content

    layout_type = settings.get("type", "responsive")
    if layout_type == "master_detail":
        panes = master_detail_panes(descriptions)
        master = build_content_grid(panes["master"])
        detail = build_content_grid(panes["detail"])
        allowance = max(0, int(settings.get("scrollbar_allowance", 20)))
        master.SetMinSize((max(180, int(settings.get("master_min_width", 260))) + allowance, -1))
        detail.SetMinSize((max(260, int(settings.get("detail_min_width", 440))) + allowance, -1))
        content_sizer = wx.BoxSizer(wx.HORIZONTAL)
        content_sizer.Add(master, max(1, int(settings.get("master_proportion", 1))), wx.EXPAND | wx.ALL, item_padding)
        content_sizer.Add(detail, max(1, int(settings.get("detail_proportion", 2))), wx.EXPAND | wx.ALL, item_padding)

        def reflow(event):
            orientation = master_detail_orientation(form.GetClientSize().width, settings)
            desired_orientation = wx.VERTICAL if orientation == "vertical" else wx.HORIZONTAL
            if content_sizer.GetOrientation() != desired_orientation:
                content_sizer.SetOrientation(desired_orientation)
                form.Layout()
                if hasattr(form, "FitInside"):
                    form.FitInside()
            event.Skip()

        form.Bind(wx.EVT_SIZE, reflow)
        form._jsform_master_detail_reflow = reflow
    elif layout_type == "columns":
        content_sizer = wx.BoxSizer(wx.HORIZONTAL)
        for pane in column_layout_panes(descriptions):
            content_sizer.Add(
                build_content_grid(pane), 1, wx.EXPAND | wx.ALL, item_padding,
            )
    else:
        content_sizer = build_content_grid(descriptions)

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
