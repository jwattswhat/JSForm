"""
    frmForms.py - Church Manager Forms Classes
    Rev. Jonathan C. Watt
    July 1, 2021
"""
#
#   import wx classes
#
import wx
import wx.dataview

#
#   import Pyhton classes
#
import os
import json

#
#   import framework classes
#
import JSForm
import subprocess


class clsForm:
    """
    clsBASEForm: Process a form
    Rev. Jonathan C. Watt
    July 2021

       Class Variables.

       Parameters

    """

    class _dirtydialog(wx.Dialog):
        def __init__(self, parent, title):
            super().__init__(parent, title=title, size=(400, 200))
            panel = wx.Panel(self)
            self.text = wx.StaticText(
                panel,
                wx.ID_ANY,
                label="This form has been modified?",
                pos=(10, 50),
            )
            self.btn = wx.Button(
                panel,
                JSForm.CONST.FORM_CONTINUE,
                label="Continue",
                size=(100, 30),
                pos=(10, 100),
            )
            self.btn = wx.Button(
                panel,
                JSForm.CONST.FORM_CANCEL,
                label="Cancel",
                size=(100, 30),
                pos=(120, 100),
            )

    def __init__(
        self,
        parent,
        dbconnection,
        formname,
        controls=None,
        frmdescription=None,
        position=None,
        parentrecord=None,
        fillonblank=None
    ):
        self.create(parent,dbconnection,formname,controls,frmdescription,position,parentrecord,fillonblank)

    def create(
        self,
        parent,
        dbconnection,
        formname,
        controls=None,
        frmdescription=None,
        position=None,
        parentrecord=None,
        fillonblank=None
    ):

        JSForm.LG.log(
            formname=formname,
            controls=controls,
            frmdescription=frmdescription,
            position=position,
        )

        self.PARENT = parent
        self.FORMNAME = formname
        self.DBConnection = dbconnection  # Save the Connection Locally
        self.position = position
        self.parentkey = parentrecord
        self.fillonblank = fillonblank
        self.RECORDS = None

        self.LINKEDFORM = {}
        self.SUBFORM = {}

        self.FORMDESCRIPTON, self.CONTROLDESCRIPTION = self.load_form_from_json(
            formname
        )

        #   if form override is present do it here.
        if frmdescription is not None:
            self.FORMDESCRIPTON.update(frmdescription)

        self.override_linked_and_sub_forms()
        if "controls" not in self.FORMDESCRIPTON:
            self.FORMDESCRIPTON["controls"] = ["Navigation", "Close"]
        if controls != None:
            self.FORMDESCRIPTON["controls"] = controls

        self.FORMDESCRIPTON, self.CONTROLDESCRIPTION = JSForm.charactertopoint(
            self.FORMDESCRIPTON, self.CONTROLDESCRIPTION
        )

        #   add predfined controls to the control
        self.CONTROLDESCRIPTION = {
            **self.CONTROLDESCRIPTION,
            **self.process_predefined_controls(self.FORMDESCRIPTON["controls"]),
        }

        self.FRAME, self.FORM = self.process_form_type(self.FORMDESCRIPTON, position)

        self.CONTROLID = self.build_form()

        self.RECORDS = self.initialize_data_record(self.FORMDESCRIPTON)
        try:
            self.RECORDS.load_records(self.FORMDESCRIPTON["table"],parentrecord)
        except:
            pass

        self.initialize_linked_forms()
        self.initialize_sub_forms()

        self.bind_form_controls()

        if not self.RECORDS:
            return
        
        if self.fillonblank:
            for i in range(0,len(self.fillonblank),2):
                self.RECORDS._record[self.RECORDS._position][
                    self.fillonblank[i]
                ] = self.parentkey[self.fillonblank[i+1]]
        self.fill_form(self.RECORDS.current())

    def override_linked_and_sub_forms(self):
        JSForm.LG.log()
        if "linkedform" in self.FORMDESCRIPTON:
            for linkedform in self.FORMDESCRIPTON["linkedform"]:
                formdesc, controldesc = self.load_form_from_json(linkedform)
                formdesc.update(self.FORMDESCRIPTON["linkedform"][linkedform])
                self.FORMDESCRIPTON["linkedform"][linkedform] = formdesc
        if "subform" in self.FORMDESCRIPTON:
            for subform in self.FORMDESCRIPTON["subform"]:
                formdesc, controldesc = self.load_form_from_json(subform)
                formdesc.update(self.FORMDESCRIPTON["subform"][subform])
                self.FORMDESCRIPTON["subform"][subform] = formdesc

    def process_predefined_controls(self, controls):
        JSForm.LG.log(controls=controls)

        JSForm.CONST.btnNavigationCONTROLS = JSForm.fnUtil.convertNavButtons(
            JSForm.CONST.btnNavigationCONTROLS
        )

        lastcolumn = self.FORMDESCRIPTON["size"][0]
        lastline = self.FORMDESCRIPTON["size"][1] - (
            JSForm.FONT.Get_Current_Font().GetPixelSize()[1]
        )

        NavControls = {}
        self.NavControlsPresent = False
        x = 5  # start 5 in
        if "Navigation" in controls:
            self.NavControlsPresent = True

            for key in JSForm.CONST.btnNavigationCONTROLS["Navigation"]:
                NavControls[key] = JSForm.CONST.btnNavigationCONTROLS["Navigation"][key]
                NavControls[key]["pos"] = [
                    x,
                    lastline,
                ]
                x += JSForm.CONST.btnNavigationCONTROLS["Navigation"][key]["size"][0]
        else:
            if "Update" in controls:
                NavControls["btnUpdate"] = JSForm.CONST.btnNavigationCONTROLS[
                    "Navigation"
                ]["btnUpdate"]
                NavControls["btnUpdate"]["pos"] = [
                    x,
                    lastline,
                ]

        #   Predefined Controls "Close"
        self.ClosePresent = False
        if "Close" in controls:
            self.ClosePresent = True
            NavControls["btnClose"] = JSForm.CONST.btnNavigationCONTROLS["Close"][
                "btnClose"
            ]
            NavControls["btnClose"]["pos"] = [
                lastcolumn
                - JSForm.CONST.btnNavigationCONTROLS["Close"]["btnClose"]["size"][0],
                lastline,
            ]  # -CONST.btnNavigationCONTROLS["Close"]["btnClose"]["size"][1]]

        return NavControls

    def process_form_type(self, formdescription, position):
        """
        parameters
            formdescription["type"]
                "Dialog" - for Modal Forms
                "Panel" - Normal
                "StaticBox" - for SubForms
            position - override position for form

        """
        JSForm.LG.log(formdescription=formdescription, position=position)
        if position is not None:
            formdescription["pos"] = [position[0], position[1]]

        if formdescription["type"] == "Dialog":
            formdescription["size"][0] += 30
            formdescription["size"][1] += 70
            FRAME = wx.Dialog(
                None, id=wx.ID_ANY, **JSForm.getcontrolparameters(formdescription)
            )
            FORM = FRAME
        elif formdescription["type"] == "Panel":
            #   Panel must have a frame as a Parent.
            #   Invisible to the user.
            size = [formdescription["size"][0] + 30, formdescription["size"][1] + 70]
            FRAME = wx.Frame(
                None,
                id=wx.ID_ANY,
                title=formdescription["title"],
                pos=formdescription["pos"],
                size=size,
            )
            formdescription["pos"] = [0, 0]
            FORM = wx.Panel(
                FRAME, wx.ID_ANY, **JSForm.getcontrolparameters(formdescription)
            )
        elif formdescription["type"] == "StaticBox":
            FORM = wx.StaticBox(
                self.PARENT.FORM,
                wx.ID_ANY,
                **JSForm.getcontrolparameters(formdescription)
            )
            FRAME = FORM
        FRAME.SetFont(JSForm.FONT.Get_Current_Font())
        FORM.SetFont(JSForm.FONT.Get_Current_Font())

        return FRAME, FORM

    def load_form_from_json(self, Form):
        """
        loads form description from a JSON file.
        """
        JSForm.LG.log(Form=Form)

        FormLocation = JSForm.CONFIG.get_Config_Value("Location", "Form")

        formname = FormLocation + Form + ".json"
        f = open(
            formname,
        )
        jsonfrm = json.load(f)
        return jsonfrm[Form + "FORM"]["FORM"], jsonfrm[Form + "FORM"]["CONTROLS"]

    def build_form(self):
        JSForm.LG.log()
        controlid = {}
        if "readonly" in self.FORMDESCRIPTON:
            readonly = True
        else:
            readonly = False
        for key in self.CONTROLDESCRIPTION.copy():

            if readonly:
                self.CONTROLDESCRIPTION[key].update({"readonly": True})

            if "readonlyfields" in self.FORMDESCRIPTON:
                if key in self.FORMDESCRIPTON["readonlyfields"]:
                    self.CONTROLDESCRIPTION[key].update({"readonly": True})

            fld = JSForm.clsField(
                self, wx.ID_ANY, self.CONTROLDESCRIPTION[key], self.DBConnection
            )
            controlid.update({key: fld.FIELD})
        return controlid

    def initialize_data_record(self, formdescription):
        JSForm.LG.log(formdescription=formdescription)
        if "table" in formdescription:
            return JSForm.clsRecord(self.DBConnection, formdescription["table"])

    def update_choices(self):       # defunct
        JSForm.LG.log()
        for field in self.CONTROLID:
            if self.CONTROLDESCRIPTION[field]["type"] == "ComboBox":
                choices = self.CONTROLID[field].choices.Load_Choices(
                    self.CONTROLDESCRIPTION[field]
                )
                if choices != None:
                    self.CONTROLDESCRIPTION.update({"choices": choices})
                    value = self.CONTROLID[field].GetValue()
                    self.CONTROLID[field].Set(choices)
                    self.CONTROLID[field].ChangeValue(value)

    def fill_form(self, record):
        """
        fill the form with editable data from the Read record
        """
        JSForm.LG.log(record=record)
        for key in self.CONTROLDESCRIPTION:
            if key == "ID":
                continue

            #   get the  value 
            try:    #   Get the Default value
                default = self.CONTROLDESCRIPTION[key]["defaultvalue"]
            except:
                default = None

            #   set the value
            if record == None:
                continue

            if key in record:
                value = record[key]
                if value == None:
                    value = default

                match self.CONTROLDESCRIPTION[key]["type"]:
                    case "StaticText":
                        continue
                    case "TextCtrl"|"Multiline"|"CheckListEdit"|"TextNumber"|"ComboBox":
                        self.CONTROLID[key].ChangeValue(value)
                    case _:
                        self.CONTROLID[key].SetValue(value)

        for linkedfrm in self.LINKEDFORM:
            try:
                self.LINKEDFORM[linkedfrm].fill_form(
                    self.LINKEDFORM[linkedfrm].RECORDS.load_records(
                        None, 
                        self.RECORDS.current()))
            except:
                continue
        for subfrm in self.SUBFORM:
            try:
                self.SUBFORM[subfrm].fill_form(
                    self.SUBFORM[subfrm].RECORDS.load_records(
                        None, 
                        self.RECORDS.current()))
            except:
                continue
        for field in self.CONTROLID:
            if self.CONTROLDESCRIPTION[field]["type"] == "DataViewListCtrl":
                self.CONTROLID[field].SetValueTable(
                    record, self.CONTROLDESCRIPTION[field]["table"]
                )
        return False

    def initialize_linked_forms(self):
        JSForm.LG.log()

        if "linkedform" not in self.FORMDESCRIPTON:
            return

        for lnkdfrm in self.FORMDESCRIPTON["linkedform"]:
            found = False
            for ctrl in self.CONTROLDESCRIPTION:
                if "action" in self.CONTROLDESCRIPTION[ctrl]:
                    if self.CONTROLDESCRIPTION[ctrl]["action"][0] == "openlinkedform":
                        if self.CONTROLDESCRIPTION[ctrl]["action"][1] == lnkdfrm:
                            found = True
                            break
            if not found:
                self.open_linked_form(lnkdfrm,self.RECORDS.current())

    def open_linked_form(self, lnkdfrm, record=None):
        """
        open_linked_form - setup open linked form.
        """
        JSForm.LG.log(lnkdfrm=lnkdfrm, record=record)

        # make fillonblank optional for linked forms
        if "fillonblank" in self.FORMDESCRIPTON["linkedform"][lnkdfrm]:
            fob = self.FORMDESCRIPTON["linkedform"][lnkdfrm]["fillonblank"]
        else:
            fob = None 

        LinkedForm = self.__class__(
            self,   # as parent
            dbconnection=self.DBConnection,
            formname=lnkdfrm,
            frmdescription=self.FORMDESCRIPTON["linkedform"][lnkdfrm],
            controls=self.FORMDESCRIPTON["linkedform"][lnkdfrm]["controls"],
            position=None, #pyautogui.position(),
            parentrecord=record,
            fillonblank=fob
        )
        try: 
            LinkedForm.fill_form(LinkedForm.RECORDS.current())
        except:
            pass
        self.LINKEDFORM.update({lnkdfrm: LinkedForm})
        return LinkedForm.show()

    def initialize_sub_forms(self):
        JSForm.LG.log()
        if "subform" not in self.FORMDESCRIPTON:
            return

        for subfrm in self.FORMDESCRIPTON["subform"]:
            SubForm = self.__class__(
                self,       # as parent
                dbconnection=self.DBConnection,
                formname=subfrm,
                controls=self.FORMDESCRIPTON["subform"][subfrm]["controls"],
                frmdescription=self.FORMDESCRIPTON["subform"][subfrm].copy(),
                position=None, 
                parentrecord=self.RECORDS.current()
            )

            self.SUBFORM.update({subfrm: SubForm})
            return SubForm.show()

    def bind_form_controls(self):
        JSForm.LG.log()
        self.FORM.Bind(wx.EVT_CLOSE, self._on_close)

        #
        #   Check for bound events
        #
        for field in self.CONTROLID:
            if "action" in self.CONTROLDESCRIPTION[field]:
                match self.CONTROLDESCRIPTION[field]["action"][0]:
                    case "mouse":
                        match self.CONTROLDESCRIPTION[field][1]:
                            case "left click":
                                self.CONTROLID[field].Bind(
                                    wx.EVT_LEFT_DOWN,
                                    self._capturemouse
                                )
                            case "right click":
                                self.CONTROLID[field].Bind(
                                    wx.EVT_RIGHT_DOWN,
                                    self._capturemouse
                                )
                            case "left double click":
                                self.CONTROLID[field].Bind(
                                    wx.EVT_LEFT_DCLICK,
                                    self._capturemouse
                                )
                            case "right double click":
                                self.CONTROLID[field].Bind(
                                    wx.EVT_LEFT_DCLICK,
                                    self._capturemouse
                                )
                    case "refreshform":
                        self.FORM.Bind(
                            wx.EVT_TEXT, 
                            self._refreshforms, 
                            self.CONTROLID[field]
                        )
                    case "openform" | "openlinkedform" | "openformfromfield":
                        self.CONTROLID[field].Bind(
                            wx.EVT_BUTTON, 
                            self._openformevent
                        )
                    case "openfile":
                        self.CONTROLID[field].Bind(
                            wx.EVT_BUTTON, 
                            self._openfileevent
                        )
                    case "openreport":
                        self.CONTROLID[field].Bind(
                            wx.EVT_BUTTON,
                            self._openreportevent
                        )
                    case "editchecklist":
                        self.CONTROLID[field].Bind(
                            wx.EVT_BUTTON,
                            self._editchecklist
                        )
                    case _:
                        pass
        #
        #   Bind standard event buttons
        #
        if self.ClosePresent:
            self.FORM.Bind(
                wx.EVT_BUTTON, self._on_close_click, self.CONTROLID["btnClose"]
            )

        if self.NavControlsPresent:
            self.FORM.Bind(
                wx.EVT_BUTTON, self._on_new_record_click, self.CONTROLID["btnNew"]
            )
            self.FORM.Bind(
                wx.EVT_BUTTON, self._on_update_record_click, self.CONTROLID["btnUpdate"]
            )
            self.FORM.Bind(
                wx.EVT_BUTTON, self._on_first_record_click, self.CONTROLID["btnFirst"]
            )
            self.FORM.Bind(
                wx.EVT_BUTTON, self._on_prev_record_click, self.CONTROLID["btnPrev"]
            )
            self.FORM.Bind(
                wx.EVT_BUTTON, self._on_next_record_click, self.CONTROLID["btnNext"]
            )
            self.FORM.Bind(
                wx.EVT_BUTTON, self._on_last_record_click, self.CONTROLID["btnLast"]
            )
            self.FORM.Bind(
                wx.EVT_BUTTON, self._on_delete_record_click, self.CONTROLID["btnDelete"]
            )
            self.FORM.Bind(
                wx.EVT_BUTTON, self._on_close_click, self.CONTROLID["btnClose"]
            )
        elif "controls" in self.FORMDESCRIPTON:
            if "Update" in self.FORMDESCRIPTON["controls"]:
                self.FORM.Bind(
                    wx.EVT_BUTTON,
                    self._on_update_record_click,
                    self.CONTROLID["btnUpdate"],
                )

    def disable_button(self, name):
        JSForm.LG.log()
        self.CONTROLID[name].Disable()

    def enable_button(self, name):
        JSForm.LG.log()
        self.CONTROLID[name].Enbable()

    def enable_navigation_buttons(self):
        JSForm.LG.log()
        # pre-defined buttons
        if self.NavControlsPresent:
            self.CONTROLID["btnNew"].Enable()
            self.CONTROLID["btnDelete"].Enable()
            self.CONTROLID["btnFirst"].Enable()
            self.CONTROLID["btnPrev"].Enable()
            self.CONTROLID["btnNext"].Enable()
            self.CONTROLID["btnLast"].Enable()
            self.CONTROLID["btnUpdate"].Enable()

    def disable_navigation_buttons(self):
        JSForm.LG.log()
        # pre-defined buttons
        if self.NavControlsPresent:
            self.CONTROLID["btnNew"].Disable()
            self.CONTROLID["btnDelete"].Disable()
            self.CONTROLID["btnFirst"].Disable()
            self.CONTROLID["btnPrev"].Disable()
            self.CONTROLID["btnNext"].Disable()
            self.CONTROLID["btnLast"].Disable()
            self.CONTROLID["btnUpdate"].Disable()

    def validate_form(self):
        JSForm.LG.log()
        if self.FORM.Validate():
            return True
        else:
            return False

    def update_screen_to_record(self):
        JSForm.LG.log()
        if self.RECORDS.isempty():
            return None
        for field in self.RECORDS.current().keys():
            if field == "ID":
                continue
            self.RECORDS.setfieldvalue(field, self.CONTROLID[field].GetValue())

    def show(self):
        JSForm.LG.log()
        if "modal" in self.FORMDESCRIPTON:
            return self.FRAME.ShowModal()
        try:
            self.FRAME.Show()
        except:
            pass
        finally:
            self.FORM.Show()

    def showmodal(self):
        JSForm.LG.log()
        return self.FRAME.ShowModal()

    def new_record(self):
        JSForm.LG.log()
        if not self.FORMDirty():
            self.RECORDS.add(self.RECORDS.sql.get_blank_record())
            if self.fillonblank:
                for i in range(0,len(self.fillonblank),2):
                    self.RECORDS._record[self.RECORDS._position][
                        self.fillonblank[i]
                    ] = self.parentkey[self.fillonblank[i+1]]


            self.fill_form(self.RECORDS._record[self.RECORDS._position])
            self._close_linked_forms()
            if self.NavControlsPresent:
                self.disable_navigation_buttons()
                self.CONTROLID["btnUpdate"].Enable()

    def set_all_controls_to_normal_color(self):
        JSForm.LG.log()
        for field in self.CONTROLID:
            self.CONTROLID[field].SetNormalColor()

    #
    #   Evant Handlers
    #
       
    def _capturemouse(self, event):  # <TODO> implement.
        #
        # Future development
        #
        JSForm.LG.log()
        field = event.GetEventObject().GetName()

    def _refreshforms(self, event):
        JSForm.LG.log()
        field = event.GetEventObject().GetName()
        evnttype = event.GetEventType()
        if evnttype == wx.EVT_TEXT.typeId:
            if "table" in self.FORMDESCRIPTON:
                self.RECORDS.setfieldvalue(
                    field, 
                    self.CONTROLID[field].GetValue())
                self.fill_form(self.RECORDS.current())

    def _openreportevent(self,event):
        JSForm.LG.log()
        field = event.GetEventObject().GetName()
        report = self.CONTROLDESCRIPTION[field]["action"][1]
        SQL = "SELECT * FROM tblReports WHERE Report = '{report}';".format(report=report)
        cursor = self.DBConnection.cursor()
        cursor.execute(SQL)
        row = cursor.fetchone()
        cursor.close()
        JSForm.RunReport(row[0],self,self.DBConnection)

    def _openfileevent(self, event):
        JSForm.LG.log()
        file = None
        field = event.GetEventObject().GetName()
        evnttype = event.GetEventType()
        openctrl = self.CONTROLDESCRIPTION[field]["action"][1]
        match self.CONTROLDESCRIPTION[openctrl]["type"]:
            case "FilePickerCtrl":
                path = JSForm.CONFIG.get_Config_Value(
                    self.CONTROLDESCRIPTION[openctrl]["directory"][0],
                    self.CONTROLDESCRIPTION[openctrl]["directory"][1],
                )
                file = path + self.CONTROLID[openctrl].GetPath()
            case "TextCtrl":
                file = self.CONTROLID[openctrl].GetValue()
            case "ComboBox":
                table = self.CONTROLDESCRIPTION[openctrl]["table"]
                sql = JSForm.clsSQL(self.DBConnection, table, self.RECORDS.current())
                SQL = sql.select()
                cursor = self.DBConnection.cursor()
                cursor.execute(SQL)
                row = cursor.fetchone()
                file = row[0]
            case otherwise:
                file = None
        if file != None:
            os.startfile(file)

    def _openformevent(self,event):
        JSForm.LG.log()
        field = event.GetEventObject().GetName()
        evnttype = event.GetEventType()
        openctrl = self.CONTROLDESCRIPTION[field]["action"][1]
        match self.CONTROLDESCRIPTION[field]["action"][0]:
            case "openform": 
                form = JSForm.clsForms.clsForm(None, self.DBConnection, openctrl, ["Navigation", "Close"])
                form.show()
            case "openformfromfield":
                form = JSForm.clsForms.clsForm(None, self.DBConnection, 
                self.CONTROLID[openctrl].GetValue(), ["Navigation", "Close"])
                form.show()
            case "openlinkedform":
                try:
                    record = self.RECORDS.current()
                except:
                    record = None
                self.open_linked_form(openctrl,record)

    def _editchecklist(self,event):
        JSForm.LG.log()
        field = event.GetEventObject().GetName()
        evnttype = event.GetEventType()
        ctrl = self.CONTROLDESCRIPTION[field]["action"][2]
        newlist = self.CONTROLDESCRIPTION[field]["action"][3]
        cursor = self.DBConnection.cursor()
        try:
            cursor.execute("SELECT CheckList FROM tblCheckList WHERE ID = {ID}".format(ID=self.CONTROLID[newlist].GetValue()))
        except:
            return None
        row = cursor.fetchone()
        chklst = json.loads(row[0])
        match self.CONTROLDESCRIPTION[field]["action"][1]:
            case "replacelist":
                self.CONTROLID[ctrl].ReplaceList(chklst)
            case "mergelist":
                self.CONTROLID[ctrl].MergeList(chklst)
            case "clearlist":
                self.CONTROLID[ctrl].ClearList()

    def _on_close_click(self, event):
        JSForm.LG.log()
        self.FORM.Close()

    def _on_close(self, event):
        JSForm.LG.log()

        if not self.FORMDirty():

            if self.LINKEDFORM:
                for linkedform in self.LINKEDFORM.copy().keys():
                    self.LINKEDFORM[linkedform].FORM.Close()

            if self.PARENT:
                if self.FORMNAME in self.PARENT.LINKEDFORM:
                    self.PARENT.LINKEDFORM.pop(self.FORMNAME)
                if self.FORMNAME in self.PARENT.SUBFORM:
                    self.PARENT.SUBFORM.pop(self.FORMNAME)
    
            self.FRAME.Destroy()

    def _replace_checklist(self, event):
        JSForm.LG.log()
        field = event.GetEventObject().GetName()
        evnttype = event.GetEventType()

    def _merge_checklist(self,event):
        JSForm.LG.log()
        field = event.GetEventObject().GetName()
        evnttype = event.GetEventType()

    #
    #   Internal Methods
    #

    def FORMDirty(self):
        JSForm.LG.log()

        if not self.RECORDS:
            return False

        if "readonly" not in self.FORMDESCRIPTON:
            self.update_screen_to_record()

            required = self._check_required_fields()
            if required:
                for fld in required:
                    self.CONTROLID[fld].SetWarningColor()
                dlg = wx.MessageDialog(
                    self.FORM,
                    "Fields: "+",".join(required),
                    "Required Fields",
                    wx.CANCEL | wx.OK)
                result = dlg.ShowModal()
                dlg.Destroy()
                if result == wx.CANCEL:
                    return True

            dirtyfields = self.RECORDS.recordisdirty()
            if dirtyfields:
                for field in dirtyfields:
                    self.CONTROLID[field].SetWarningColor()
                dlg = self._dirtydialog(self.FORM, title="Form Modified(dirty)")
                result = dlg.ShowModal()
                dlg.Destroy()
                if result == JSForm.CONST.FORM_CANCEL:
                    return True

        return False

    def _check_required_fields(self):
        required = []
        for fld in self.RECORDS.sql.sqldescription:
            if fld == "ID":
                continue
            value = self.CONTROLID[fld].GetValue()
            if value == None:
                if not self.RECORDS.sql.sqldescription[fld]["null_ok"]:
                    required.append(fld)
                    continue
                try:
                    if self.CONTROLID[fld].CONTROLDESCRIPTION["required"]:
                        required.append(fld)
                except:
                    continue
        return required

    def _on_new_record_click(self, event):
        JSForm.LG.log()
        self.new_record()

    def _on_delete_record_click(self, event):
        JSForm.LG.log()
        if not self.FORMDirty():
            self.RECORDS.delete_record_from_DB()
            dlg = wx.MessageDialog(
                self.FORM,
                "Record Deleted.",
                "Deleted",
                wx.OK,
            )
            result = dlg.ShowModal()
            dlg.Destroy()
            self.fill_form(self.RECORDS.current())
            self._close_linked_forms()

    def _close_linked_forms(self):
        JSForm.LG.log()
        linked = self.LINKEDFORM.copy()
        for frm in linked:
            self.LINKEDFORM[frm].FORM.Close()
            self.LINKEDFORM.pop(frm)

    def _on_update_record_click(self, event):
        JSForm.LG.log()
        required = self._check_required_fields()
        if required:
            for fld in required:
                self.CONTROLID[fld].SetWarningColor()
            dlg = wx.MessageDialog(
                self.FORM,
                "Fields: "+",".join(required),
                "Required Fields",
                wx.OK)
            result = dlg.ShowModal()
            dlg.Destroy()
            return
        self.update_screen_to_record()
        self.RECORDS.update_current_record_in_DB()
        self.enable_navigation_buttons()
        dlg = wx.MessageDialog(
            self.FORM,
            "Record Updated.",
            "Updated",
            wx.OK,
        )
        result = dlg.ShowModal()
        dlg.Destroy()
        self.set_all_controls_to_normal_color()

    def _first_prev_next_last(self, firstprevnextlast):
        JSForm.LG.log()
        if not self.FORMDirty():

            self.RECORDS._record[
                self.RECORDS._position
            ] = self.RECORDS.original.restore()

            match firstprevnextlast:
                case JSForm.CONST.FORM_FIRST:
                    self.RECORDS.first()
                case JSForm.CONST.FORM_PREV:
                    self.RECORDS.prev()
                case JSForm.CONST.FORM_NEXT:
                    self.RECORDS.next()
                case JSForm.CONST.FORM_LAST:
                    self.RECORDS.last()

            self.fill_form(self.RECORDS.current())

    def _on_first_record_click(self, event):
        JSForm.LG.log()
        self._first_prev_next_last(JSForm.CONST.FORM_FIRST)

    def _on_prev_record_click(self, event):
        JSForm.LG.log()
        self._first_prev_next_last(JSForm.CONST.FORM_PREV)

    def _on_next_record_click(self, event):
        JSForm.LG.log()
        self._first_prev_next_last(JSForm.CONST.FORM_NEXT)

    def _on_last_record_click(self, event):
        JSForm.LG.log()
        self._first_prev_next_last(JSForm.CONST.FORM_LAST)


