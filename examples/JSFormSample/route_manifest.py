"""Native JSForm route-manifest report for the standalone sample."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import wx
import JSForm


ROOT = Path(__file__).resolve().parent
STARTER = ROOT / "Reports" / "SBRT01.json"
CUSTOM = ROOT / "Reports" / "Custom" / "SBRT01.json"
OUTPUT = ROOT / "Output" / "SBRT01.pdf"

CONTRACT = JSForm.ReportDatasetContract(
    "sample.routemanifest", 1, "sample.route_manifest",
    (
        JSForm.ReportCollection("route", "Route", (
            JSForm.ReportField("Route", "Route"),
            JSForm.ReportField("School", "School"),
            JSForm.ReportField("Assignment", "Assignment"),
        )),
        JSForm.ReportCollection("stops", "Stops", (
            JSForm.ReportField("Sequence", "Stop", "integer"),
            JSForm.ReportField("Time", "Time", "time"),
            JSForm.ReportField("StopName", "Location"),
            JSForm.ReportField("Address", "Address"),
        )),
    ),
)


def _all(connection, sql, values=()):
    cursor = connection.cursor()
    marker = "%s" if cursor.__class__.__module__.startswith("mysql.connector") else "?"
    cursor.execute(sql.replace("?", marker), values)
    rows = cursor.fetchall()
    cursor.close()
    return rows


def route_choices(connection):
    return _all(connection, """
        SELECT r.ID, CONCAT(r.Name, ' - ', r.TripType), s.Name
          FROM sb_route r JOIN sb_school s ON s.ID=r.SchoolID
         WHERE r.Active=1 ORDER BY r.Name, r.TripType
    """)


def build_dataset(connection, route_id):
    route = _all(connection, """
        SELECT r.Name, r.TripType, s.Name,
               COALESCE(b.BusNumber, 'No bus assigned'),
               COALESCE(CONCAT(d.FirstName, ' ', d.LastName), 'No driver assigned')
          FROM sb_route r JOIN sb_school s ON s.ID=r.SchoolID
          LEFT JOIN sb_bus b ON b.ID=r.BusID
          LEFT JOIN sb_driver d ON d.ID=r.DriverID WHERE r.ID=?
    """, (route_id,))[0]
    stops = _all(connection, """
        SELECT SequenceNumber, StopTime, StopName, COALESCE(Address, '')
          FROM sb_route_stop WHERE RouteID=? ORDER BY SequenceNumber
    """, (route_id,))
    return JSForm.ReportDataset.create(CONTRACT, {
        "route": [{
            "Route": f"{route[0]} - {route[1]}", "School": route[2],
            "Assignment": f"Bus {route[3]}   Driver: {route[4]}",
        }],
        "stops": [{"Sequence": row[0], "Time": row[1], "StopName": row[2], "Address": row[3]} for row in stops],
    })


def preview(connection, route_id):
    definition = JSForm.ReportDefinitionLoader().load(CUSTOM if CUSTOM.exists() else STARTER)
    JSForm.PDFReportRenderer().render(definition, build_dataset(connection, route_id), OUTPUT)
    os.startfile(OUTPUT)


class RouteManifestDialog(wx.Dialog):
    def __init__(self, parent, connection):
        super().__init__(parent, title="Route Manifest")
        self.connection = connection
        self.routes = route_choices(connection)
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(wx.StaticText(panel, label="Choose a route to preview or customize."), 0, wx.ALL, 10)
        self.choice = wx.Choice(panel, choices=[f"{row[1]} - {row[2]}" for row in self.routes])
        if self.routes:
            self.choice.SetSelection(0)
        outer.Add(self.choice, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        buttons = wx.BoxSizer(wx.HORIZONTAL)
        preview_button = wx.Button(panel, label="Preview PDF")
        designer_button = wx.Button(panel, label="Customize Layout")
        close_button = wx.Button(panel, wx.ID_CLOSE, "Close")
        buttons.Add(preview_button, 0, wx.RIGHT, 6)
        buttons.Add(designer_button, 0, wx.RIGHT, 6)
        buttons.AddStretchSpacer()
        buttons.Add(close_button)
        outer.Add(buttons, 0, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(outer)
        preview_button.Bind(wx.EVT_BUTTON, self.on_preview)
        designer_button.Bind(wx.EVT_BUTTON, self.on_designer)
        close_button.Bind(wx.EVT_BUTTON, lambda _event: self.EndModal(wx.ID_CLOSE))
        self.SetSize((520, 180))
        self.CentreOnParent()

    def selected_route(self):
        index = self.choice.GetSelection()
        return None if index == wx.NOT_FOUND else self.routes[index][0]

    def on_preview(self, _event):
        route_id = self.selected_route()
        if route_id is not None:
            preview(self.connection, route_id)

    def on_designer(self, _event):
        route_id = self.selected_route()
        if route_id is None:
            return
        CUSTOM.parent.mkdir(parents=True, exist_ok=True)
        if not CUSTOM.exists():
            shutil.copy2(STARTER, CUSTOM)
        JSForm.open_report_designer(
            CUSTOM, dataset_contract=CONTRACT,
            preview_handler=lambda definition: JSForm.PDFReportRenderer().render(
                definition, build_dataset(self.connection, route_id), OUTPUT
            ),
            starter_definition_path=STARTER,
            export_directory=ROOT / "Output",
        )


def show_route_manifest(parent, connection):
    dialog = RouteManifestDialog(parent, connection)
    try:
        dialog.ShowModal()
    finally:
        dialog.Destroy()
