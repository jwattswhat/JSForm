"""Ordered route-stop proof for the JSForm sample application."""

from __future__ import annotations

from datetime import time, timedelta

import wx
import JSForm


def _marker(cursor):
    return "%s" if cursor.__class__.__module__.startswith("mysql.connector") else "?"


def _execute(cursor, sql, values=()):
    return cursor.execute(sql.replace("?", _marker(cursor)), values)


def load_stops(connection, route_id):
    cursor = connection.cursor()
    try:
        _execute(cursor, "SELECT ID,SequenceNumber,StopName,Address,StopTime "
                         "FROM sb_route_stop WHERE RouteID=? ORDER BY SequenceNumber", (route_id,))
        return [
            {"id": row[0], "sequence": row[1], "name": row[2],
             "address": row[3] or "", "time": row[4] or ""}
            for row in cursor.fetchall()
        ]
    finally:
        cursor.close()


def save_stops(connection, route_id, rows):
    cursor = connection.cursor()
    try:
        _execute(cursor, "SELECT ID FROM sb_route_stop WHERE RouteID=?", (route_id,))
        existing = {row[0] for row in cursor.fetchall()}
        retained = {row.get("id") for row in rows if row.get("id") is not None}
        _execute(cursor, "UPDATE sb_route_stop SET SequenceNumber=-ID WHERE RouteID=?", (route_id,))
        for stop_id in existing - retained:
            _execute(cursor, "DELETE FROM sb_route_stop WHERE ID=? AND RouteID=?", (stop_id, route_id))
        for row in rows:
            values = (row["sequence"], row["name"], row.get("address") or None,
                      row.get("time") or None)
            if row.get("id") in existing:
                _execute(cursor, "UPDATE sb_route_stop SET SequenceNumber=?,StopName=?,Address=?,StopTime=? "
                                 "WHERE ID=? AND RouteID=?", values + (row["id"], route_id))
            else:
                _execute(cursor, "INSERT INTO sb_route_stop "
                                 "(RouteID,SequenceNumber,StopName,Address,StopTime) VALUES (?,?,?,?,?)",
                         (route_id,) + values)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def display_time(value):
    if isinstance(value, timedelta):
        seconds = int(value.total_seconds())
        return "{:02d}:{:02d}".format(seconds // 3600, (seconds % 3600) // 60)
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return str(value or "")[:5]


def edit_stop(parent, row=None):
    row = dict(row or {})
    dialog = wx.Dialog(parent, title="Edit Route Stop" if row else "Add Route Stop")
    panel = wx.Panel(dialog)
    outer = wx.BoxSizer(wx.VERTICAL)
    fields = wx.FlexGridSizer(cols=2, vgap=8, hgap=8)
    fields.AddGrowableCol(1, 1)
    name = wx.TextCtrl(panel, value=str(row.get("name", "")))
    address = wx.TextCtrl(panel, value=str(row.get("address", "")))
    stop_time = wx.TextCtrl(panel, value=display_time(row.get("time")))
    for label, control in (("Stop name:", name), ("Address:", address), ("Time (HH:MM):", stop_time)):
        fields.Add(wx.StaticText(panel, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
        fields.Add(control, 1, wx.EXPAND)
    outer.Add(fields, 1, wx.EXPAND | wx.ALL, 12)
    buttons = wx.StdDialogButtonSizer()
    ok = wx.Button(panel, wx.ID_OK)
    cancel = wx.Button(panel, wx.ID_CANCEL)
    buttons.AddButton(ok)
    buttons.AddButton(cancel)
    buttons.Realize()
    outer.Add(buttons, 0, wx.EXPAND | wx.ALL, 12)
    panel.SetSizer(outer)
    dialog_sizer = wx.BoxSizer(wx.VERTICAL)
    dialog_sizer.Add(panel, 1, wx.EXPAND)
    dialog.SetSizer(dialog_sizer)
    dialog.SetMinSize((440, 230))
    dialog.Fit()
    try:
        if dialog.ShowModal() != wx.ID_OK:
            return None
        if not name.GetValue().strip():
            raise ValueError("Enter a stop name.")
        entered_time = stop_time.GetValue().strip()
        if entered_time:
            time.fromisoformat(entered_time)
        row.update(name=name.GetValue().strip(), address=address.GetValue().strip(), time=entered_time)
        return row
    finally:
        dialog.Destroy()


def show_ordered_route_stops(parent, connection, route_id):
    if not route_id:
        wx.MessageBox("Save the route before editing its stops.", "Route Stops", parent=parent)
        return
    dialog = JSForm.OrderedChildEditorDialog(
        parent, title="Ordered Route Stops", rows=load_stops(connection, route_id),
        columns=(
            JSForm.OrderedChildColumn("Stop", "sequence", 65),
            JSForm.OrderedChildColumn("Location", "name", 240),
            JSForm.OrderedChildColumn("Time", "time", 100),
            JSForm.OrderedChildColumn("Address", "address", 280),
        ),
        create_item=lambda owner: edit_stop(owner),
        edit_item=lambda owner, row: edit_stop(owner, row),
        save_items=lambda rows: save_stops(connection, route_id, rows),
        instructions="Arrange the stops in travel order. Saving assigns simple 1, 2, 3 sequence numbers.",
    )
    try:
        dialog.ShowModal()
    finally:
        dialog.Destroy()
