import wx
import mysql
import datetime
import os
import subprocess

import JSForm

def RunReport(reportid,frm,dbconnection):
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
        dlg = _requiredfielddialog(frm.FORM,"Report Not Found",rptTitle,"Report")
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
                    report=reportlocation, rptreport=rptReport
                )
            )
        except:
            pass

        #   build the commandline
        cmdline = "{limedir}limereport -s{reportpattern}{rptreport}.lrxml -d{reportlocation}{rptreport}.pdf".format(
            limedir=limedir,
            reportpattern=reportpattern,
            reportlocation=reportlocation,
            rptreport=rptReport,
        )

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
                    cmdline = cmdline + ' -p{param}="{pvalue}"'.format(param=param,pvalue=pvalue)
            except:
                dlg = _requiredfielddialog(frm.FORM,"Required Field",rptTitle,param)
                result = dlg.ShowModal()
                dlg.Destroy()
                return None

        #   Process the report
        sb = subprocess.Popen(cmdline)
        sb.wait()
        cmdline = "{reportlocation}{rptreport}.pdf".format(
            reportlocation=reportlocation, rptreport=rptReport
        )
        subprocess.Popen(cmdline, shell=True)
