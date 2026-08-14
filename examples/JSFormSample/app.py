"""Run the fictional JSForm School Bus Sample application."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PACKAGE_ROOT.parent))

import wx
import JSForm
import mysql.connector
from route_manifest import show_route_manifest
from route_stop_editor import show_ordered_route_stops
from student_finder import show_student_finder
from sample_tools import show_diagnostics, show_mail_preview
from version import __version__ as SAMPLE_VERSION
from JSForm.windows_credentials import read_credential


FORMS = Path(__file__).with_name("Forms")
EDIT_CONTROLS = ["Navigation", "New", "Update", "Delete", "Close"]
ROUTES = {
    "btnSchools": "frmSchool",
    "btnDrivers": "frmDriver",
    "btnBuses": "frmBus",
    "btnRoutes": "frmRoute",
    "btnStudents": "frmStudent",
}
SAMPLE_CREDENTIAL_TARGET = "JSFormSample/Database"


def arguments(argv=None):
    parser = argparse.ArgumentParser(
        description="JSForm School Bus Sample {} using JSForm {}".format(
            SAMPLE_VERSION, JSForm.__version__,
        )
    )
    parser.add_argument("--server", default="127.0.0.1")
    parser.add_argument("--database", default="JSFormSample")
    parser.add_argument("--user", default="jsform_sample")
    return parser.parse_args(argv)


def connect_database(settings, attempts=3):
    """Prompt for the isolated sample password, allowing simple typing errors."""
    try:
        stored_user, stored_password = read_credential(SAMPLE_CREDENTIAL_TARGET)
        if stored_user == settings.user:
            return JSForm.clsDB(
                settings.server, settings.database, settings.user, stored_password,
                jsform_database=settings.database,
            )
    except (KeyError, OSError, mysql.connector.Error):
        pass
    for attempt in range(1, attempts + 1):
        password = getpass.getpass("MariaDB password for {}: ".format(settings.user))
        try:
            return JSForm.clsDB(
                settings.server, settings.database, settings.user, password,
                jsform_database=settings.database,
            )
        except mysql.connector.Error as error:
            if error.errno != 1045 or attempt == attempts:
                raise
            print(
                "That password was not accepted. Please try again "
                "({} attempt(s) remaining).".format(attempts - attempt),
                file=sys.stderr,
            )
    raise RuntimeError("Unable to connect to the sample database.")


def main(argv=None):
    settings = arguments(argv)
    os.environ["JSFORM_SCREEN_OVERLAY"] = str(FORMS)
    wx_app = wx.App(0)
    database = connect_database(settings)
    JSForm.CONFIG.set_Config_DBConnection(database)
    JSForm.OPTION.set_Option_DBConnection(database)
    JSForm.FONT.set_Font_DBConnection(database)
    JSForm.FONT.Get_Config_Font()
    JSForm.CONST.btnNavigationCONTROLS = JSForm.convertNavButtons(
        JSForm.CONST.btnNavigationCONTROLS
    )
    JSForm.configure_error_reporting(
        application_name="JSFormSample",
        application_version=SAMPLE_VERSION,
        error_id_prefix="JSS",
        safe_context_provider=lambda: {
            "application_mode": "sample", "database_scope": "isolated_sample",
            "database_name": settings.database,
        },
    )
    JSForm.install_error_hooks()

    main_form = JSForm.clsForm(
        None, database.DBConnection, "frmSampleMain", ["Close"],
        authorization_policy=JSForm.AllowAllAuthorizationPolicy(),
    )

    def open_form(event):
        form_name = ROUTES[event.GetEventObject().GetName()]
        form = JSForm.clsForm(
            main_form, database.DBConnection, form_name, EDIT_CONTROLS,
            authorization_policy=JSForm.AllowAllAuthorizationPolicy(),
        )
        if form_name == "frmRoute":
            def open_ordered_stops(_event):
                record = form.RECORDS.current() or {}
                show_ordered_route_stops(form.FRAME, database.DBConnection, record.get("ID"))
                form.CONTROLID["StopList"].SetValueTable(form.RECORDS.current())
            form.CONTROLID["btnOrderedStops"].Bind(wx.EVT_BUTTON, open_ordered_stops)
        form.show()

    for control_name in ROUTES:
        main_form.CONTROLID[control_name].Bind(wx.EVT_BUTTON, open_form)
    main_form.CONTROLID["btnManifest"].Bind(
        wx.EVT_BUTTON,
        lambda _event: show_route_manifest(main_form.FRAME, database.DBConnection),
    )
    main_form.CONTROLID["btnDiagnostics"].Bind(
        wx.EVT_BUTTON, lambda _event: show_diagnostics(main_form.FRAME)
    )
    main_form.CONTROLID["btnMailPreview"].Bind(
        wx.EVT_BUTTON,
        lambda _event: show_mail_preview(main_form.FRAME, database.DBConnection),
    )
    main_form.CONTROLID["btnStudentFinder"].Bind(
        wx.EVT_BUTTON,
        lambda _event: show_student_finder(main_form.FRAME, database.DBConnection),
    )
    main_form.FRAME.SetTitle(
        "JSForm Sample {} - School Bus Routes - {}".format(
            SAMPLE_VERSION, settings.database,
        )
    )
    main_form.show()
    wx_app.MainLoop()
    database.DBConnection.close()
    database.JSConnection.close()


if __name__ == "__main__":
    main()
