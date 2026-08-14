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
from JSForm.form_lifecycle import ChildFormRegistry
from JSForm.form_services import (
    ControlFactory, FormDefinitionLoader, required_fields, resolve_form_schema,
)
from JSForm.layout_engine import apply_responsive_layout, supports_responsive_layout
from JSForm.security import AuthorizationDenied, FormSecurity

#
#   import system classes
#
import subprocess
from jsonschema import validate


class clsForm:
    """
    clsBASEForm: Process a form
    Rev. Jonathan C. Watt
    July 2021

        Parameters
            parent - Parent form or None
            dbconnection - dbConnection for records displayed in form
            formname - name of the form corrisponds to json form file
            controls - standard form controls. (see btnNavigationCONTROLS clsConstant.py)
            frmdescription - dictionary containing json form informaion
            position - position on screen (upper right corner), overrides json "posch" value
            parentrecord - Parent record from calling form
            fillonblank - Fields to fill when new record is generated.


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
        fillonblank=None,
        authorization_policy=None,
        audit_hook=None,
    ):
        self.create(
            parent,
            dbconnection,
            formname,
            controls,
            frmdescription,
            position,
            parentrecord,
            fillonblank,
            authorization_policy,
            audit_hook,
        )

    def create(
        self,
        parent,
        dbconnection,
        formname,
        controls=None,
        frmdescription=None,
        position=None,
        parentrecord=None,
        fillonblank=None,
        authorization_policy=None,
        audit_hook=None,
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
        self.AUTHORIZATION_POLICY = authorization_policy
        self.AUDIT_HOOK = audit_hook
        self.RECORDS = None

        self.LINKEDFORM = ChildFormRegistry()
        self.SUBFORM = ChildFormRegistry()

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

        self.SECURITY = FormSecurity(
            formname, self.FORMDESCRIPTON, self.CONTROLDESCRIPTION,
            authorization_policy,
        )
        self.SECURITY.require("open")
        self.CONTROLDESCRIPTION = self.SECURITY.secured_control_descriptions()

        self.RESPONSIVE_LAYOUT = supports_responsive_layout(
            self.FORMDESCRIPTON, self.CONTROLDESCRIPTION
        )
        self.FORMDESCRIPTON["_responsive_layout"] = self.RESPONSIVE_LAYOUT

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
        for name, description in self.CONTROLDESCRIPTION.items():
            if description.get("security_hidden") and name in self.CONTROLID:
                self.CONTROLID[name].Hide()
            if description.get("security_disabled") and name in self.CONTROLID:
                self.CONTROLID[name].Disable()
        if self.RESPONSIVE_LAYOUT:
            layout_settings = dict(self.FORMDESCRIPTON.get("layout") or {})
            layout_settings.setdefault(
                "center",
                self.FORMDESCRIPTON["pos"][0] <= -1
                and self.FORMDESCRIPTON["pos"][1] <= -1,
            )
            apply_responsive_layout(
                self.FORM, self.FRAME, self.CONTROLID, self.CONTROLDESCRIPTION,
                layout_settings,
            )

        self.RECORDS = self.initialize_data_record(self.FORMDESCRIPTON)
        if self.RECORDS is not None:
            self.RECORDS.load_records(self.FORMDESCRIPTON["table"], parentrecord)

        self.initialize_linked_forms()
        self.initialize_sub_forms()

        self.bind_form_controls()
        self.apply_navigation_security()

        if not self.RECORDS:
            return

        if self.fillonblank:
            for i in range(0, len(self.fillonblank), 2):
                self.RECORDS._record[self.RECORDS._position][
                    self.fillonblank[i]
                ] = self.parentkey[self.fillonblank[i + 1]]

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

            # formdescription["pos"] = [0, 0]
            panel_class = (
                wx.ScrolledWindow
                if formdescription.get("_responsive_layout")
                else wx.Panel
            )
            FORM = panel_class(FRAME, wx.ID_ANY, **JSForm.getcontrolparameters(formdescription))
            if isinstance(FORM, wx.ScrolledWindow):
                FORM.SetScrollRate(10, 10)

        elif formdescription["type"] == "StaticBox":
            FORM = wx.StaticBox(
                self.PARENT.FORM,
                wx.ID_ANY,
                **JSForm.getcontrolparameters(formdescription),
            )
            FRAME = FORM

        if (formdescription["pos"][0] <= -1) and (formdescription["pos"][1] <= -1):
            FRAME.Center(wx.BOTH)
        else:
            if formdescription["pos"][0] <= -1:
                FRAME.Center(wx.HORIZONTAL)
            if formdescription["pos"][1] <= -1:
                FRAME.Center(wx.VERTICAL)

        FRAME.SetFont(JSForm.FONT.Get_Current_Font())
        FORM.SetFont(JSForm.FONT.Get_Current_Font())

        return FRAME, FORM

    def load_form_from_json(self, Form):
        """
        loads form description from a JSON file.
        """
        JSForm.LG.log(Form=Form)

        form_location = JSForm.CONFIG.get_Config_Value("Location", "Form")
        fallback = os.path.join(os.path.dirname(JSForm.__file__), "Forms")
        check_schema = JSForm.OPTION.get_Option_Value("JSONSchema", "CheckForms") == "Yes"
        schema_path = None
        if check_schema:
            schema_path = resolve_form_schema(
                JSForm.__file__,
                JSForm.CONFIG.get_Config_Value("Location", "JSONSchema"),
            )
        return FormDefinitionLoader(
            form_location, fallback, schema_path, validate if check_schema else None
        ).load(Form)

    def build_form(self):
        JSForm.LG.log()
        return ControlFactory(JSForm.clsField, wx.ID_ANY).build(
            self,
            self.CONTROLDESCRIPTION,
            self.DBConnection,
            readonly=self.FORMDESCRIPTON.get("readonly", False),
            readonly_fields=self.FORMDESCRIPTON.get("readonlyfields", []),
        )

    def refresh_layout(self, font=None):
        """Recalculate an open form after a font or display-setting change."""
        font = font or JSForm.FONT.Get_Current_Font()
        self.FRAME.SetFont(font)
        self.FORM.SetFont(font)
        for control in self.CONTROLID.values():
            control.SetFont(font)
        self.FORM.Layout()
        if hasattr(self.FORM, "FitInside"):
            self.FORM.FitInside()
        self.FRAME.Layout()

    def initialize_data_record(self, formdescription, SQL=None):
        JSForm.LG.log(formdescription=formdescription)
        if "table" in formdescription:
            return JSForm.clsRecord(self.DBConnection, formdescription["table"])

    def update_choices(self):  # defunct
        JSForm.LG.log()
        for field in self.CONTROLID:
            if self.CONTROLDESCRIPTION[field]["type"] == "ComboBox":
                choices = self.CONTROLID[field].choices.load_choices(
                    self.CONTROLDESCRIPTION[field]
                )
                if choices != None:
                    self.CONTROLDESCRIPTION[field].update({"choices": choices})
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
            default = self.CONTROLDESCRIPTION[key].get("defaultvalue")

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
                    case "TextCtrl" | "Multiline" | "CheckListEdit" | "TextNumber" | "ComboBox":
                        self.CONTROLID[key].ChangeValue(value)
                    case _:
                        self.CONTROLID[key].SetValue(value)

        for linkedfrm in self.LINKEDFORM:
            try:
                self.LINKEDFORM[linkedfrm].fill_form(
                    self.LINKEDFORM[linkedfrm].RECORDS.load_records(
                        None, self.RECORDS.current()
                    )
                )
            except (AttributeError, RuntimeError):
                continue
        for subfrm in self.SUBFORM:
            try:
                self.SUBFORM[subfrm].fill_form(
                    self.SUBFORM[subfrm].RECORDS.load_records(
                        None, self.RECORDS.current()
                    )
                )
            except (AttributeError, RuntimeError):
                continue
        for field in self.CONTROLID:
            if self.CONTROLDESCRIPTION[field]["type"] == "DataViewListCtrl":
                self.CONTROLID[field].SetValueTable(
                    record, self.CONTROLDESCRIPTION[field]["table"]
                )
        self._save_control_value_baseline(record)
        return False

    def _save_control_value_baseline(self, record):
        """Compare later edits with the values controls show after loading."""
        if record is None or not self.RECORDS:
            return
        for field in record:
            if field == "ID" or field not in self.CONTROLID:
                continue
            try:
                value = self.CONTROLID[field].GetValue()
            except (AttributeError, TypeError, ValueError):
                value = record[field]
            self.RECORDS.original.savefield(field, value)

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
                self.open_linked_form(lnkdfrm, self.RECORDS.current())

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
            self,  # as parent
            dbconnection=self.DBConnection,
            formname=lnkdfrm,
            frmdescription=self.FORMDESCRIPTON["linkedform"][lnkdfrm],
            controls=self.FORMDESCRIPTON["linkedform"][lnkdfrm]["controls"],
            position=None,  # pyautogui.position(),
            parentrecord=record,
            fillonblank=fob,
            authorization_policy=self.AUTHORIZATION_POLICY,
            audit_hook=self.AUDIT_HOOK,
        )
        if LinkedForm.RECORDS is not None:
            LinkedForm.fill_form(LinkedForm.RECORDS.current())
        self.LINKEDFORM.register(lnkdfrm, LinkedForm)
        return LinkedForm.show()

    def initialize_sub_forms(self):
        JSForm.LG.log()
        if "subform" not in self.FORMDESCRIPTON:
            return

        for subfrm in self.FORMDESCRIPTON["subform"]:
            SubForm = self.__class__(
                self,  # as parent
                dbconnection=self.DBConnection,
                formname=subfrm,
                controls=self.FORMDESCRIPTON["subform"][subfrm]["controls"],
                frmdescription=self.FORMDESCRIPTON["subform"][subfrm].copy(),
                position=None,
                parentrecord=self.RECORDS.current(),
                authorization_policy=self.AUTHORIZATION_POLICY,
                audit_hook=self.AUDIT_HOOK,
            )

            self.SUBFORM.register(subfrm, SubForm)
            return SubForm.show()

    def bind_form_controls(self):
        JSForm.LG.log()
        self.FORM.Bind(wx.EVT_CLOSE, self._on_close)

        #
        #   Check for bound events
        #
        for field in self.CONTROLID:
            if "action" in self.CONTROLDESCRIPTION[field]:
                if not self.SECURITY.allows_control(field, "invoke"):
                    self.CONTROLID[field].Disable()
                    continue
                match self.CONTROLDESCRIPTION[field]["action"][0]:
                    case "mouse":
                        match self.CONTROLDESCRIPTION[field][1]:
                            case "left click":
                                self.CONTROLID[field].Bind(
                                    wx.EVT_LEFT_DOWN, self._capturemouse
                                )
                            case "right click":
                                self.CONTROLID[field].Bind(
                                    wx.EVT_RIGHT_DOWN, self._capturemouse
                                )
                            case "left double click":
                                self.CONTROLID[field].Bind(
                                    wx.EVT_LEFT_DCLICK, self._capturemouse
                                )
                            case "right double click":
                                self.CONTROLID[field].Bind(
                                    wx.EVT_LEFT_DCLICK, self._capturemouse
                                )
                    case "refreshform":
                        self.FORM.Bind(
                            wx.EVT_TEXT, self._refreshforms, self.CONTROLID[field]
                        )
                    case "openform" | "openlinkedform" | "openformfromfield":
                        self.CONTROLID[field].Bind(wx.EVT_BUTTON, self._openformevent)
                    case "openfile":
                        self.CONTROLID[field].Bind(wx.EVT_BUTTON, self._openfileevent)
                    case "openreport":
                        self.CONTROLID[field].Bind(wx.EVT_BUTTON, self._openreportevent)
                    case "editchecklist":
                        self.CONTROLID[field].Bind(wx.EVT_BUTTON, self._editchecklist)
                    case "process":
                        self.CONTROLID[field].Bind(wx.EVT_BUTTON, self._processaction)
                    case "onchange":
                        change_event = (
                            wx.EVT_LIST_ITEM_SELECTED
                            if self.CONTROLDESCRIPTION[field].get("type") in {"ListCtrl", "ListCtrlID"}
                            else wx.EVT_COMBOBOX
                        )
                        self.CONTROLID[field].Bind(change_event, self._processaction)
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
        self.CONTROLID[name].Enable()

    def enable_buttons(self, buttonlist):
        for b in buttonlist:
            self.enable_button(b)

    def disable_all_buttons(self):
        for b in self.CONTROLID:
            self.disable_button(b)

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
            self.apply_navigation_security()

    def apply_navigation_security(self):
        """Disable standard write buttons denied by form security."""
        if "btnNew" in self.CONTROLID and not self.SECURITY.allows("create"):
            self.CONTROLID["btnNew"].Disable()
        if "btnUpdate" in self.CONTROLID and not self.SECURITY.allows("update"):
            self.CONTROLID["btnUpdate"].Disable()
        if "btnDelete" in self.CONTROLID and not self.SECURITY.allows("delete"):
            self.CONTROLID["btnDelete"].Disable()

    def _authorize_operation(self, operation):
        try:
            self.SECURITY.require(operation)
            return True
        except AuthorizationDenied as error:
            dialog = wx.MessageDialog(self.FORM, str(error), "Access denied", wx.OK)
            dialog.ShowModal()
            dialog.Destroy()
            return False

    def _audit_operation(self, operation, changed_fields=None, record_id=None):
        if not self.AUDIT_HOOK:
            return
        record = self.RECORDS.current() if self.RECORDS else None
        table = self.FORMDESCRIPTON.get("table", {}).get("name")
        if record_id is None and record:
            record_id = record.get("ID")
        self.AUDIT_HOOK({
            "operation": operation,
            "form_name": self.FORMNAME,
            "table": table,
            "record_id": record_id,
            "changed_fields": tuple(changed_fields or ()),
        })

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
            if field in self.CONTROLID:
                self.RECORDS.setfieldvalue(field, self.CONTROLID[field].GetValue())

    def center(self):
        pass
        # self.FORM.centre()

    def centre(self):
        pass
        # self.FRAME.centre()

    def show(self):
        JSForm.LG.log()
        if "modal" in self.FORMDESCRIPTON:
            wx.CallAfter(self._reset_initial_scroll)
            return self.FRAME.ShowModal()
        self.FRAME.Show()
        if self.FORM is not self.FRAME:
            self.FORM.Show()
        wx.CallAfter(self._reset_initial_scroll)

    def _reset_initial_scroll(self):
        """Open scrolled forms at their upper-left content."""
        if hasattr(self.FORM, "Scroll"):
            self.FORM.Scroll(0, 0)

    def showmodal(self):
        JSForm.LG.log()
        return self.FRAME.ShowModal()

    def new_record(self):
        JSForm.LG.log()
        if not self._authorize_operation("create"):
            return
        if not self.FORMDirty():
            self.RECORDS.add(self.RECORDS.sql.get_blank_record())
            if self.fillonblank:
                for i in range(0, len(self.fillonblank), 2):
                    self.RECORDS._record[self.RECORDS._position][
                        self.fillonblank[i]
                    ] = self.parentkey[self.fillonblank[i + 1]]

            self.fill_form(self.RECORDS._record[self.RECORDS._position])
            self._close_linked_forms()
            if self.NavControlsPresent:
                self.disable_navigation_buttons()
                self.CONTROLID["btnUpdate"].Enable()

    def set_all_controls_to_normal_color(self):
        JSForm.LG.log()
        for field in self.CONTROLID:
            self.CONTROLID[field].SetNormalColor()

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
                    "Fields: " + ",".join(required),
                    "Required Fields",
                    wx.CANCEL | wx.OK,
                )
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

    #
    #   Event Handlers
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
                self.RECORDS.setfieldvalue(field, self.CONTROLID[field].GetValue())
                self.fill_form(self.RECORDS.current())

    def _openreportevent(self, event):
        JSForm.LG.log()
        field = event.GetEventObject().GetName()
        report = self.CONTROLDESCRIPTION[field]["action"][1]
        SQL = "SELECT * FROM tblReports WHERE Report = '{report}';".format(
            report=report
        )
        cursor = self.DBConnection.cursor()
        cursor.execute(SQL)
        row = cursor.fetchone()
        cursor.close()
        JSForm.RunReport(row[0], self, self.DBConnection)

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

    def _openformevent(self, event):
        JSForm.LG.log()
        field = event.GetEventObject().GetName()
        evnttype = event.GetEventType()
        openctrl = self.CONTROLDESCRIPTION[field]["action"][1]
        match self.CONTROLDESCRIPTION[field]["action"][0]:
            case "openform":
                form = JSForm.clsForms.clsForm(
                    None, self.DBConnection, openctrl, ["Navigation", "Close"]
                )
                form.show()
            case "openformfromfield":
                form = JSForm.clsForms.clsForm(
                    None,
                    self.DBConnection,
                    self.CONTROLID[openctrl].GetValue(),
                    ["Navigation", "Close"],
                )
                form.show()
            case "openlinkedform":
                record = self.RECORDS.current() if self.RECORDS else None
                self.open_linked_form(openctrl, record)

    def _editchecklist(self, event):
        JSForm.LG.log()
        field = event.GetEventObject().GetName()
        evnttype = event.GetEventType()
        ctrl = self.CONTROLDESCRIPTION[field]["action"][2]
        newlist = self.CONTROLDESCRIPTION[field]["action"][3]
        cursor = self.DBConnection.cursor()
        try:
            cursor.execute(
                "SELECT CheckList FROM tblCheckList WHERE ID = %s",
                (self.CONTROLID[newlist].GetValue(),),
            )
            row = cursor.fetchone()
        except Exception as error:
            self._show_operation_error("Unable to load the checklist.")
            return None
        finally:
            cursor.close()
        chklst = json.loads(row[0])
        match self.CONTROLDESCRIPTION[field]["action"][1]:
            case "replacelist":
                self.CONTROLID[ctrl].ReplaceList(chklst)
            case "mergelist":
                self.CONTROLID[ctrl].MergeList(chklst)
            case "clearlist":
                self.CONTROLID[ctrl].ClearList()

    def _processaction(self, event):
        field = event.GetEventObject().GetName()
        print(self.CONTROLDESCRIPTION[field]["action"][0])
        print(self.CONTROLDESCRIPTION[field]["action"][1])

    def _on_close_click(self, event):
        JSForm.LG.log()
        self.FORM.Close()

    def _on_close(self, event):
        JSForm.LG.log()

        if not self.FORMDirty():
            # Detach children before closing them. Their close handlers can call
            # back into this form, and wx may already have deleted a child panel.
            self._close_child_forms(self.LINKEDFORM)
            self._close_child_forms(self.SUBFORM)

            if self.PARENT:
                self.PARENT.LINKEDFORM.pop(self.FORMNAME, None)
                self.PARENT.SUBFORM.pop(self.FORMNAME, None)

            try:
                if not self.FRAME.IsBeingDeleted():
                    self.FRAME.Destroy()
            except RuntimeError:
                # The native wx object was already destroyed by its parent.
                pass

    def _close_child_forms(self, forms):
        """Close live child forms and discard stale wx wrapper references."""
        if hasattr(forms, "close_all"):
            forms.close_all()
            return
        children = list(forms.values())
        forms.clear()
        for child in children:
            try:
                if not child.FORM.IsBeingDeleted():
                    child.FORM.Close()
            except RuntimeError:
                # Accessing an already-deleted wx object raises RuntimeError.
                continue

    def _replace_checklist(self, event):
        JSForm.LG.log()
        field = event.GetEventObject().GetName()
        evnttype = event.GetEventType()

    def _merge_checklist(self, event):
        JSForm.LG.log()
        field = event.GetEventObject().GetName()
        evnttype = event.GetEventType()

    #
    #   Internal Methods
    #

    def _check_required_fields(self):
        return required_fields(self.RECORDS.sql.sqldescription, self.CONTROLID)

    def _on_new_record_click(self, event):
        JSForm.LG.log()
        self.new_record()

    def _on_delete_record_click(self, event):
        JSForm.LG.log()
        if not self._authorize_operation("delete"):
            return
        current = self.RECORDS.current()
        record_id = current.get("ID") if current else None
        if not self.FORMDirty():
            try:
                self.RECORDS.delete_record_from_DB()
            except RuntimeError as error:
                self._show_operation_error(str(error))
                return
            self._audit_operation("delete", ("ID",), record_id)
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
        self._close_child_forms(self.LINKEDFORM)

    def _on_update_record_click(self, event):
        JSForm.LG.log()
        if not self._authorize_operation("update"):
            return
        required = self._check_required_fields()
        if required:
            for fld in required:
                self.CONTROLID[fld].SetWarningColor()
            dlg = wx.MessageDialog(
                self.FORM, "Fields: " + ",".join(required), "Required Fields", wx.OK
            )
            result = dlg.ShowModal()
            dlg.Destroy()
            return
        self.update_screen_to_record()
        changed_fields = self.RECORDS.recordisdirty()
        try:
            self.RECORDS.update_current_record_in_DB()
        except RuntimeError as error:
            self._show_operation_error(str(error))
            return
        self._audit_operation("update", changed_fields)
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

    def _show_operation_error(self, message):
        dialog = wx.MessageDialog(self.FORM, message, "Database operation failed", wx.OK)
        dialog.ShowModal()
        dialog.Destroy()

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
