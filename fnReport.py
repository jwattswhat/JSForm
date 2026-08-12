import wx
import mysql
import datetime
import os
import subprocess
import re
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

import JSForm
from JSForm.report_runtime import LimeReportProcess
from JSForm.report_credentials import encode_lime_password


def prepare_lime_report_template(source, database_name, connection_settings=None):
    """Return a temporary template targeting the active database safely.

    ChurchManager test databases are local by policy.  Older LimeReport
    templates contain the historical production host, so a staged test copy
    must change both the database name and the host.  The source template is
    never modified.
    """
    source = Path(source)
    content = source.read_text(encoding="utf-8-sig")
    pattern = r'(<databaseName\s+Type="QString">)([^<]*)(</databaseName>)'
    database_names = re.findall(pattern, content)
    is_test_database = str(database_name).casefold().endswith("test")
    database_matches = (
        not database_names
        or all(value[1].casefold() == database_name.casefold() for value in database_names)
    )
    host_pattern = r'(<host\s+Type="QString">)([^<]*)(</host>)'
    host_matches = not is_test_database or all(
        value[1].casefold() in {"localhost", "127.0.0.1", "::1"}
        for value in re.findall(host_pattern, content)
    )
    if database_matches and host_matches and not connection_settings:
        return str(source), None

    staged = re.sub(
        pattern,
        lambda match: "{}{}{}".format(match.group(1), database_name, match.group(3)),
        content,
    )
    if is_test_database:
        staged = re.sub(
            host_pattern,
            lambda match: "{}localhost{}".format(match.group(1), match.group(3)),
            staged,
        )
    if connection_settings:
        configured_database = str(connection_settings["database"])
        if configured_database.casefold() != str(database_name).casefold():
            raise RuntimeError("LimeReport database does not match the active database.")
        configured_host = str(connection_settings["server"])
        if is_test_database and configured_host.casefold() not in {
            "localhost", "127.0.0.1", "::1"
        }:
            raise RuntimeError("Test reports may use only the local database host.")
        text_values = {
            "databaseName": configured_database,
            "host": configured_host,
            "userName": str(connection_settings["user"]),
        }
        for tag, value in text_values.items():
            tag_pattern = rf'(<{tag}\s+Type="QString">)([^<]*)(</{tag}>)'
            staged = re.sub(
                tag_pattern,
                lambda match, replacement=escape(value): (
                    match.group(1) + replacement + match.group(3)
                ),
                staged,
            )
        encoded_password = encode_lime_password(connection_settings["password"])
        staged = re.sub(
            r'(<password\b[^>]*\bValue=")[^"]*("[^>]*/>)',
            lambda match: match.group(1) + encoded_password + match.group(2),
            staged,
        )
    temp_dir = Path(tempfile.gettempdir()) / "ChurchManager-LimeReport-Test"
    temp_dir.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=source.suffix,
        prefix=source.stem + "-", dir=temp_dir, delete=False,
    )
    with handle:
        handle.write(staged)
    target = Path(handle.name)
    return str(target), target


def current_database_name(dbconnection):
    cursor = dbconnection.cursor()
    try:
        cursor.execute("SELECT DATABASE();")
        return cursor.fetchone()[0]
    finally:
        cursor.close()

def RunReport(reportid,frm,dbconnection,connection_settings=None):
    class _requiredfielddialog(wx.Dialog):
        def __init__(self, parent, title, report="", field=""):
            super().__init__(parent, title=title, size=(400, 200))
            panel = wx.Panel(self)
            self.text = wx.StaticText(
                panel,
                wx.ID_ANY,
                label="Field {field} Required for FORM {report}.".format(field=field,report=report),
                pos=(10, 50),
            )
            self.btn = wx.Button(
                panel,
                JSForm.CONST.FORM_CONTINUE,
                label="Continue",
                size=(100, 30),
                pos=(10, 100),
            )

    #   Check for Report ID
    if reportid == None:
        dlg = _requiredfielddialog(frm.FORM,"Report Selection Required")
        result = dlg.ShowModal()
        dlg.Destroy()
        return None

    reportpattern = JSForm.CONFIG.get_Config_Value(
        "Location", "LimeReportPattern"
    )
    reportlocation = JSForm.CONFIG.get_Config_Value("Location", "Report")
    limedir = JSForm.CONFIG.get_Config_Value("Location", "LimeReport")

    #   Read the Report Record from DB
    SQL = "SELECT * FROM tblReports WHERE ID = {ID};".format(ID=reportid)
    cursor = dbconnection.cursor()
    cursor.execute(SQL)
    row = cursor.fetchone()
    cursor.close()
    if row == None:
        dlg = _requiredfielddialog(frm.FORM,"Report Not Found",str(reportid),"Report")
        result = dlg.ShowModal()
        dlg.Destroy()
        return None

    #   Name the record values
    rptReport = row[1]
    rptTitle = row[2]
    if row[3]:
        rptParams = row[3].replace("[", "")
        rptParams = rptParams.replace("]", "")
        rptParams = rptParams.replace(",", "")
        rptParams = rptParams.splitlines()
    else:
        rptParams = []

    if row[4]:
        rptBatch = row[4].replace("[", "")
        rptBatch = rptBatch.replace("]", "")
        rptBatch = rptBatch.replace(",", "")
        rptBatch = rptBatch.splitlines()
    else:
        rptBatch = [rptReport]
    rptNote = row[5]

    for rptReport in rptBatch:
        #   Delete the current pdf report
        try:
            os.remove(
                "{reportlocation}{rptreport}.pdf".format(
                    reportlocation=reportlocation, rptreport=rptReport
                )
            )
        except FileNotFoundError:
            pass

        #   build the commandline
        source_template = "{reportpattern}{rptreport}.lrxml".format(
            reportpattern=reportpattern, rptreport=rptReport
        )
        lime_template, temporary_template = prepare_lime_report_template(
            source_template, current_database_name(dbconnection), connection_settings
        )
        output_path = "{reportlocation}{rptreport}.pdf".format(
            reportlocation=reportlocation, rptreport=rptReport
        )
        parameters = {}

        for param in rptParams:
            try:
                match param:
                    case "StartDate"|"EndDate":
                        pvalue = frm.CONTROLID[param].GetValue(format="%Y/%m/%d")
                    case _:
                        pvalue = frm.CONTROLID[param].GetValue()
                if pvalue == None:
                    dlg = _requiredfielddialog(frm.FORM,"Required Field",rptTitle,param)
                    result = dlg.ShowModal()
                    dlg.Destroy()
                    return None
                else:
                    parameters[param] = pvalue
            except (AttributeError, KeyError, TypeError, ValueError):
                dlg = _requiredfielddialog(frm.FORM,"Required Field",rptTitle,param)
                result = dlg.ShowModal()
                dlg.Destroy()
                return None

        #   Process the report
        process = LimeReportProcess(limedir)
        try:
            process.generate(lime_template, output_path, parameters)
        finally:
            if temporary_template:
                temporary_template.unlink(missing_ok=True)
        process.open_output(output_path)
