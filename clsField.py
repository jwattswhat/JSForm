"""
    frmFields.py - Church Manager Form Classes

    Rev. Jonathan C. Watt
    September 11, 2021

"""
from mysql.connector import FieldType
import datetime
import json
import io
import os
import pathlib
import itertools
import sys
import locale
from decimal import *
c = getcontext()
c.traps[FloatOperation] = True
# import wxpython

import wx
import wx.adv
import wx.dataview
import wx.html
from JSForm.control_values import (
    checked_value,
    datetime_value,
    multiline_text,
    normalized_json,
    number_value,
    value_sequence,
)

# import framwork

import JSForm


def getcontrolparameters(controldictionary):
    """
    This function strips away the parameters that are not passed to the wx.<controls>
    so that the control can be called without errors and CMFormDescriptions.py
    can contain all the dynamic information about the field.
        (See table clsConstants.wxpythoncallparmameters)
    """
    global FONT

    newdict = {}
    if "stylelist" in controldictionary:
        newdict.update({"style": setstylefield(controldictionary["stylelist"])})
    # if "validatorstr" in controldictionary:
    #    newdict.update(
    #        {"validator": JSForm.setvalidatorfield(controldictionary["validatorstr"])}
    #    )

    controltype = controldictionary["type"]
    if controltype not in JSForm.CONST.wxpythoncallparmameters:
        raise ValueError("Unsupported JSForm control type: {}".format(controltype))
    for key in JSForm.CONST.wxpythoncallparmameters[controltype]:
        if key in controldictionary.keys():
            newdict.update({key: controldictionary[key]})
    return newdict


def setstylefield(sty):
    """
    This function replaces string "styles" with wxPython constants.
    """
    st = 0
    if "CAPTION" in sty:
        st = st | wx.CAPTION
    if "MINIMIZEBOX" in sty:
        st = st | wx.MINIMIZE_BOX
    if "MAXIMIZEBOX" in sty:
        st = st | wx.MAXIMIZE_BOX
    if "CLOSEBOX" in sty:
        st = st | wx.CLOSE_BOX
    if "MULTILINE" in sty:
        st = st | wx.TE_MULTILINE
    if "DONTWRAP" in sty:
        st = st | wx.TE_DONTWRAP
    if "WORDWRAP" in sty:
        st = st | wx.TE_WORDWRAP
    if "READONLY" in sty:
        st = st | wx.TE_READONLY
    if "PROCESSENTER" in sty:
        st = st | wx.TE_PROCESS_ENTER
    if "PROCESSTAB" in sty:
        st = st | wx.TE_PROCESS_TAB
    if "FLPCHANGEDIR" in sty:
        st = st | wx.FLP_CHANGE_DIR
    if "FLPSMALL" in sty:
        st = st | wx.FLP_SMALL
    if "FLPUSETEXTCTRL" in sty:
        st = st | wx.FLP_USE_TEXTCTRL
    if "ALLOWNONE" in sty:
        st = st | wx.adv.DP_ALLOWNONE
    if "DROPDOWN" in sty:
        st = st | wx.adv.DP_DROPDOWN
    if "MULTIPLE" in sty:
        st = st | wx.LB_MULTIPLE
    if "JUSTIFYRIGHT" in sty:
        st = st | wx.TE_RIGHT
    return st


FORMColors = {
    "Warning": {"fcolor": "White", "bcolor": "Red"},
    "Error": {"fcolor": "White", "bcolor": "Red"},
    "Notice": {"fcolor": "Blue", "bcolor": "White"},
    "Normal": {"fcolor": "Black", "bcolor": "White"},
}


class clsField:
    """
    this class processes all the form fields.
        initialization:
            parent - parent calling parent
            id - wxpython ID
            controldescription - dictionary control description (see - )
            dbconnection - database connection
        subclasses:


    """

    PARENT = None
    FIELD = 0
    ID = None
    DBConnection = 0

    def __init__(
        self,
        parent,
        id,
        controldescription,
        dbconnection,
    ):
        self.PARENT = parent
        self.ID = id
        self.DBConnection = dbconnection

        # all fields pre process

        # here the field is parsed according to field "type".
        match controldescription["type"]:
            case "StaticBox":
                self.FIELD = self.clsStaticBox(self, controldescription)
            case "StaticText":
                self.FIELD = self.clsStaticText(self, controldescription)
            case "MultiLine":
                self.FIELD = self.clsMultiLine(self, controldescription)
            case "TextCtrl":
                self.FIELD = self.clsTextCtrl(self, controldescription)
            case "TextNumber":
                self.FIELD = self.clsTextNumber(self, controldescription)
            case "Currency":
                self.FIELD = self.clsCurrency(self, controldescription)
            case "Float":
                self.FIELD = self.clsFloat(self, controldescription)
            case "JSON":
                self.FIELD = self.clsJSON(self, controldescription)
            case "ComboBox":
                self.FIELD = self.clsComboBox(self, controldescription)
            case "ListCtrl":
                self.FIELD = self.clsListCtrl(self, controldescription)
            case "ListCtrlID":
                self.FIELD = self.clsListCtrlID(self, controldescription)
            case "CheckBox":
                self.FIELD = self.clsCheckBox(self, controldescription)
            case "CheckListBox":
                self.FIELD = self.clsCheckListBox(self, controldescription)
            case "CheckListEdit":
                self.FIELD = self.clsCheckListEdit(self, controldescription)
            case "Button":
                self.FIELD = self.clsButton(self, controldescription)
            case "DataViewListCtrl":
                self.FIELD = self.clsDataListViewCtrl(self, controldescription)
            case "DateTime":
                self.FIELD = self.clsDateTime(self, controldescription)
            case "DatePickerCtrl":
                self.FIELD = self.clsDatePickerCtrl(self, controldescription)
            case "TimePickerCtrl":
                self.FIELD = self.clsTimePickerCtrl(self, controldescription)
            case "CalendarCtrl":
                self.FIELD = self.clsCalendarCtrl(self, controldescription)
            case "FilePickerCtrl":
                self.FIELD = self.clsFilePickerCtrl(self, controldescription)
            case "ImagePickerCtrl":
                self.FIELD = self.clsImagePickerCtrl(self, controldescription)
            case "HTMLCtrl":
                self.FIELD = self.clsHTMLCtrl(self, controldescription)
            case _:
                raise ValueError(
                    "Unsupported JSForm control type: {}".format(
                        controldescription["type"]
                    )
                )

        #  all fields post process

        # Check for Read Only Fields
        if controldescription.get("readonly", False):
            self.FIELD.Disable()

        tooltip = controldescription.get("tooltip")
        if tooltip:
            self.FIELD.SetToolTip(str(tooltip))

    def GetID(self):
        return self.ID

    def GetName(self):
        return self.FIELD.GetName()

    class clsFieldExtra:
        def init_field(self, parent, controldescription):
            self.parent = parent
            self.DIRTY = False
            self.DBConnection = parent.DBConnection
            self.CONTROLDESCRIPTION = controldescription.copy()
            self.choices = JSForm.clsChoice(self.DBConnection, self.CONTROLDESCRIPTION)

        def SetValue(self, value):
            if value == None:
                super().SetValue("")
            else:
                super().SetValue(value)

        def ChangeValue(self, value):
            if value == None:
                super().ChangeValue("")
            else:
                super().ChangeValue(value)

        def GetValue(self):
            value = super().GetValue()
            if value == "":
                value = None
            return value

        def SetWarningColor(self):
            self.SetBackgroundColour(FORMColors["Warning"]["bcolor"])
            self.SetForegroundColour(FORMColors["Warning"]["fcolor"])
            self.Refresh()

        def SetNormalColor(self):
            self.SetBackgroundColour(FORMColors["Normal"]["bcolor"])
            self.SetForegroundColour(FORMColors["Normal"]["fcolor"])
            self.Refresh()

    class clsStaticBox(wx.StaticBox, clsFieldExtra):
        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)
            # statictext preprocess

            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(self.CONTROLDESCRIPTION),
            )
            # self.SetNormalColor()

    class clsStaticText(wx.StaticText, clsFieldExtra):
        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)
            # statictext preprocess

            controldescription["label"] = self.getOption(controldescription["label"])

            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(controldescription),
            )

            # statictext postprocess

        def SetValue(self, value):
            if value != None:
                super().SetLabel(str(value))
            self.SetNormalColor()

        def getOption(self, txt):
            texttxt = txt
            pos = 0
            while True:
                start = txt.find("{OPTION", pos)
                if start == -1:
                    break
                end = txt.find("}", start)
                c1 = txt.find(":", start)
                c2 = txt.find(":", c1 + 1)
                optionfor = txt[c1 + 1 : c2]
                optiontype = txt[c2 + 1 : end]
                pos = start + 1
                texttxt = txt.replace(
                    txt[start : end + 1],
                    '"' + JSForm.OPTION.get_Option_Value(optionfor, optiontype) + '"',
                    1,
                )
            return texttxt

    class clsTextCtrl(wx.TextCtrl, clsFieldExtra):
        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)

            # textctrl preprocess

            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(self.CONTROLDESCRIPTION),
            )
            self.SetNormalColor()

            maximum = self.CONTROLDESCRIPTION.get("maxlength")
            if maximum is not None:
                self.SetMaxLength(int(maximum))
                self.Bind(wx.EVT_TEXT_MAXLEN, self._on_max_length)

            # textctrl postprocess

        def _on_max_length(self, event):
            message = self.CONTROLDESCRIPTION.get("maxlengthmessage")
            if not message:
                label = self.CONTROLDESCRIPTION.get("label") or self.CONTROLDESCRIPTION.get("name") or "This field"
                message = "{} accepts at most {} characters.".format(
                    label, self.CONTROLDESCRIPTION["maxlength"]
                )
            wx.MessageBox(str(message), "Entry too long", wx.OK | wx.ICON_WARNING)

        def SetValue(self, value):
            if value == None:
                super().SetValue("")
            else:
                super().SetValue(str(self.choices.getchoicedisplay(value)))

        def ChangeValue(self, value):
            if value == None:
                super().ChangeValue("")
            else:
                super().ChangeValue(str(self.choices.getchoicedisplay(value)))

        def GetValue(self):
            value = self.choices.getchoiceid(super().GetValue())
            if value == "":
                value = None
            return value

    class clsMultiLine(wx.TextCtrl, clsFieldExtra):
        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)

            # textctrl preprocess

            if "stylelist" in controldescription:
                a = ["MULTILINE", "PROCESSENTER"]
                b = list(controldescription["stylelist"])
                c = list(itertools.chain(a, b))  # only keep one of each.
                controldescription["stylelist"] = list(set(c))
            else:
                controldescription.update({"stylelist": ["MULTILINE", "PROCESSENTER"]})

            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(controldescription),
            )
            self.SetNormalColor()

            # textctrl postprocess

        def SetValue(self, value):
            super().SetValue(multiline_text(value))

        def ChangeValue(self, value):
            super().ChangeValue(multiline_text(value))

        def GetValue(self):
            value = super().GetValue()
            if value == "":
                value = None
            else:
                value = value.splitlines()
            return value

    class clsCheckListEdit(clsMultiLine):
        lst = {}

        def SetValue(self, value):
            if value in (None, ""):
                self.lst = {}
                super().SetValue(None)
                return
            self.lst = value if isinstance(value, dict) else json.loads(value)
            super().SetValue(list(self.lst.keys()))

        def ChangeValue(self, value):
            if value in (None, ""):
                self.lst = {}
                super().ChangeValue(None)
                return
            self.lst = value if isinstance(value, dict) else json.loads(value)
            super().ChangeValue(list(self.lst.keys()))

        def GetValue(self):
            value = super().GetValue()
            if value == None:
                return None
            chklst = {value[i]: "False" for i in range(0, len(value))}
            return json.dumps(chklst)

        def MergeList(self, lst):
            current = self.GetValue()
            chklst = {} if current is None else json.loads(current)
            value = chklst | lst
            self.ChangeValue(json.dumps(value))

        def ReplaceList(self, lst):
            value = json.dumps(lst)
            self.ChangeValue(value)

        def ClearList(self):
            self.ChangeValue(None)

    class clsTextNumber(wx.TextCtrl, clsFieldExtra):
        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)
            self.controldescription = controldescription
            # textctrl preprocess

            if "style" not in controldescription:
                controldescription["style"] = wx.TE_RIGHT
            else:
                controldescription["style"] = controldescription["style"] | wx.TE_RIGHT

            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(controldescription),
            )
            self.SetNormalColor()

            # textctrl postprocess

        def SetValue(self, value):
            if value == None:
                super().SetValue("")
            else:
                if "format" in self.controldescription:
                    super().SetValue(self.controldescription["format"].format(value))
                else:
                    super().SetValue(str(value))

        def ChangeValue(self, value):
            if value == None:
                super().ChangeValue("")
            else:
                if "format" in self.controldescription:
                    super().ChangeValue(self.controldescription["format"].format(value))
                else:
                    super().ChangeValue(str(value))

        def GetValue(self):
            value = self.choices.getchoicedisplay(super().GetValue()).replace(",", "")
            if value == "":
                return None
            return number_value(value)

    class clsCurrency(clsTextCtrl):
        def GetValue(self):
            value = super().GetValue()
            if value in (None, ""):
                return None
            return number_value(value, "currency")

        def SetValue(self, value):
            if value == None:
                super().SetValue("")
            else:
                super().SetValue(Decimal(value))

    class clsFloat(clsTextNumber):
        def GetValue(self):
            return number_value(wx.TextCtrl.GetValue(self), "float")

    class clsJSON(wx.TextCtrl, clsFieldExtra):
        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)

            # JSON preprocess

            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(self.CONTROLDESCRIPTION),
            )
            self.SetNormalColor()

            # JSON postprocess

        def SetValue(self, value):
            if value in (None, ""):
                super().SetValue("")
                return
            super().SetValue(normalized_json(value))

        def ChangeValue(self, value):
            if value in (None, ""):
                super().ChangeValue("")
                return
            super().ChangeValue(normalized_json(value))

        def GetValue(self):
            value = super().GetValue()
            if value == "":
                return None
            return normalized_json(value)

    class clsComboBox(wx.ComboBox, clsFieldExtra):
        def __init__(self, parent, controldesc):
            super().init_field(parent, controldesc)

            controldescription = self.CONTROLDESCRIPTION.copy()

            # combobox preproces
            choices = self.choices.load_choices(controldescription)
            if choices != None:
                controldescription.update({"choices": choices})

            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(controldescription),
            )
            self.SetNormalColor()

            # combobox postprocess

        def Set(self, choices):
            # override to remove EVT_TEXT when the control changes.
            self.parent.PARENT.FORM.Unbind(wx.EVT_TEXT, id=self.GetId())
            super().Set(choices)

        def SetValue(self, value):
            if value == None:
                super().SetValue("")
            else:
                if self.choices.len() == 0:
                    super().SetValue(str(value))
                else:
                    disp = self.choices.getchoicedisplay(value)
                    if disp == None:
                        return None
                    super().SetValue(disp)

        def ChangeValue(self, value):
            if value == None:
                super().ChangeValue("")
            else:
                if self.choices.len() == 0:
                    super().ChangeValue(str(value))
                else:
                    disp = self.choices.getchoicedisplay(value)
                    if disp == None:
                        return None
                    super().ChangeValue(str(disp))

        def GetValueText(self):
            value = super().GetValue()
            if value == "":
                return None
            return value

        def GetValue(self):
            if self.choices.len() == 0:
                value = super().GetValue()
            else:
                value = self.choices.getchoiceid(super().GetValue())
            if value == "" or value == "{}":
                value = None
            return value

    class clsListCtrl(wx.ListCtrl, clsFieldExtra):
        def __init__(self, parent, controldesc):
            super().init_field(parent, controldesc)

            controldescription = self.CONTROLDESCRIPTION.copy()

            # combobox preproces
            choices = self.choices.load_choices(controldescription)
            if choices != None:
                controldescription.update({"choices": choices})

            controldescription["style"] = wx.LC_REPORT

            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(controldescription),
            )

            self.InsertColumn(
                0,
                controldescription["label"],
                wx.LIST_FORMAT_LEFT,
                controldescription["size"][0],
            )
            if "choices" in controldescription:
                for i in range(0, len(controldescription["choices"])):
                    self.InsertItem(i, controldescription["choices"][i])

            self.SetNormalColor()

            # clsListCtrl postprocess

        def SetValue(self, value):
            #   clear all the selections
            for item in range(self.GetItemCount()):
                self.SetItemState(item, 0, wx.LIST_STATE_SELECTED)

            #   Set selections
            if value != None:
                for val in value_sequence(value):
                    for item in range(self.GetItemCount()):
                        if val == self.GetItemText(item):
                            self.SetItemState(
                                item, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED
                            )

        def GetValue(self):
            selecteditems = []
            item = -1
            while 1:
                item = self.GetNextItem(item, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
                if item == -1:
                    break
                selecteditems.append(self.GetItemText(item))
            if selecteditems == []:
                return None
            return selecteditems

    class clsListCtrlID(wx.ListCtrl, clsFieldExtra):
        def __init__(self, parent, controldesc):
            super().init_field(parent, controldesc)

            controldescription = self.CONTROLDESCRIPTION.copy()

            # combobox preproces
            choices = self.choices.load_choices(controldescription)
            if choices != None:
                controldescription.update({"choices": choices})

            controldescription["style"] = wx.LC_REPORT
            if controldescription.get("singleselect", False):
                controldescription["style"] |= wx.LC_SINGLE_SEL

            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(controldescription),
            )

            columns = controldescription.get("column") or [
                {"label": controldescription.get("label", "Item"), "widthch": 20}
            ]
            for index, column in enumerate(columns):
                self.InsertColumn(
                    index, column.get("label", ""), wx.LIST_FORMAT_LEFT,
                    JSForm.FONT.chtopt(column.get("widthch", 20)),
                )
            if "choices" in controldescription:
                for i in range(0, len(controldescription["choices"])):
                    self.InsertItem(i, controldescription["choices"][i])

            self.SetNormalColor()

            # clsListCtrl postprocess

        def SetCatalogRows(self, rows):
            """Populate an ID-backed, optionally colored multi-column catalog."""
            self.DeleteAllItems()
            self.choices.id = []
            self.choices.display = []
            self.choices.fielddata = []
            for row_number, row in enumerate(rows):
                row_id = row["id"]
                values = [str(value) for value in row.get("values", [])]
                if not values:
                    values = [str(row_id)]
                item = self.InsertItem(row_number, values[0])
                for column, value in enumerate(values[1:], 1):
                    self.SetItem(item, column, value)
                foreground = row.get("foreground")
                if foreground:
                    self.SetItemTextColour(item, wx.Colour(foreground))
                self.choices.id.append(row_id)
                self.choices.display.append(values[0])
                self.choices.fielddata.append(values)
            if self.GetItemCount():
                self.Select(0)

        def SetValue(self, value):
            #   clear all the selections
            for item in range(self.GetItemCount()):
                self.SetItemState(item, 0, wx.LIST_STATE_SELECTED)

            #   Set the Selections
            if value != None:
                for val in value_sequence(value):
                    lookupval = self.choices.getchoicedisplay(int(val))
                    for item in range(self.GetItemCount()):
                        if lookupval == self.GetItemText(item):
                            self.SetItemState(
                                item, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED
                            )

        def GetValue(self):
            selecteditems = []
            item = -1
            while 1:
                item = self.GetNextItem(item, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
                if item == -1:
                    break
                selecteditems.append(
                    str(self.choices.getchoiceid(self.GetItemText(item)))
                )
            if selecteditems == []:
                return None
            if self.CONTROLDESCRIPTION.get("singleselect", False):
                return int(selecteditems[0])
            return selecteditems

    class clsCheckBox(wx.CheckBox, clsFieldExtra):
        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)

            # checkbox preprocess

            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(self.CONTROLDESCRIPTION),
            )
            self.SetNormalColor()

            # checkbox postprocess

        def SetValue(self, value):
            if checked_value(value):
                super().SetValue(wx.CHK_CHECKED)
            else:
                super().SetValue(wx.CHK_UNCHECKED)

        def GetValue(self):
            return super().IsChecked()

    class clsCheckListBox(wx.CheckListBox, clsFieldExtra):
        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)

            # checklistbox preprocess

            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(self.CONTROLDESCRIPTION),
            )

            choices = self.choices.load_choices(controldescription)
            if choices:
                self.InsertItems(choices, 0)

            self.SetNormalColor()

            # checklistbox postprocess

        def SetValue(self, value):
            self.Clear()
            checklist = {}
            if value not in (None, ""):
                checklist = value if isinstance(value, dict) else json.loads(value)
                try:
                    self.InsertItems(list(checklist.keys()), 0)
                except:
                    checklist = {}

            for check in checklist:
                if checklist[check] is True or str(checklist[check]).lower() == "true":
                    self.Check(self.FindString(check), True)
                else:
                    self.Check(self.FindString(check), False)

        def GetValue(self):
            checklist = super().GetStrings()
            checked = super().GetCheckedStrings()
            selected = super().GetSelections()
            di = {}
            for c in checklist:
                if c in checked:
                    di.update({c: "True"})
                else:
                    di.update({c: "False"})
            if di == {}:
                return None
            return json.dumps(di)

    class clsButton(wx.Button, clsFieldExtra):
        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)

            if "id" in controldescription:
                id = controldescription["id"]
                controldescription.pop("id")
            else:
                id = wx.ID_ANY

            super().__init__(
                parent.PARENT.FORM, id, **getcontrolparameters(self.CONTROLDESCRIPTION)
            )

    class clsDataListViewCtrl(wx.dataview.DataViewListCtrl, clsFieldExtra):
        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)

            # preprocess

            self.DLVCrecords = JSForm.clsRecord(
                self.DBConnection, self.CONTROLDESCRIPTION["table"]
            )

            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(self.CONTROLDESCRIPTION),
            )
            self.SetNormalColor()

            # postprocess

            self.columnnames = []
            for i in range(len(self.CONTROLDESCRIPTION["column"])):
                column = self.CONTROLDESCRIPTION["column"][i]
                width = (
                    JSForm.FONT.chtopt(column["widthch"])
                    if "widthch" in column
                    else int(column.get("width", 100))
                )
                self.AppendTextColumn(
                    label=column["label"],
                    width=width,
                )
                self.columnnames.append(self.CONTROLDESCRIPTION["column"][i]["name"])

        def GetColumnNames(self):
            return self.columnnames

        def SetValueTable(self, parentrecord=None, table=None):
            self.rowID = []

            self.parent.FIELD.DeleteAllItems()

            if table == None:
                table = self.CONTROLDESCRIPTION["table"]

            self.DLVCrecords.load_records(table=table, parentrecord=parentrecord)
            for rec in self.DLVCrecords._record:
                self.AppendTableRecord(rec)
            if self.GetItemCount():
                self.SelectRow(0)

        def AppendTableRecord(self, record):
            columnsforcontrol = []
            for column in self.columnnames:
                for i in range(len(self.CONTROLDESCRIPTION["column"])):
                    if column == self.CONTROLDESCRIPTION["column"][i]["name"]:
                        if "lookup" in self.CONTROLDESCRIPTION["column"][i]:
                            columnsforcontrol.append(
                                str(
                                    self._choicesID2display(
                                        record[column],
                                        self.CONTROLDESCRIPTION["column"][i]["lookup"],
                                    )
                                )
                            )
                        else:
                            columnsforcontrol.append(str(record[column]))
                        break
            super().AppendItem(columnsforcontrol)

        def SetValueRecord(self, row, record):
            for column, field in enumerate(self.columnnames):
                super().SetValue(str(record.get(field, "")), row, column)

        def GetSelectedRowID(self):
            record = self.GetSelectedRow()
            return None if record is None else record.get("ID")

        def GetSelectedRow(self):
            selectedrow = super().GetSelectedRow()
            if selectedrow == wx.NOT_FOUND:
                return None
            return self.DLVCrecords._record[selectedrow]

        def _choicesID2display(self, value, table=None):
            """
            this module scans the lookup query for the choice indicated by "value"

            JSON values

            """
            global CONFIG

            if value == None:
                return None
            choice = value

            if table == None:
                if "lookup" in self.CONTROLDESCRIPTION:
                    table = self.CONTROLDESCRIPTION["lookup"]
                else:
                    return choice

            sql = "SELECT {field} FROM {table} WHERE ID = {key};".format(
                field=table["display"],
                table=table["table"],
                key=value,
            )
            cursor = self.DBConnection.cursor()
            cursor.execute(sql)
            row = cursor.fetchone()
            cursor.close()
            choice = ""
            self.subfields = []
            for i in range(len(row)):
                f = row[i]
                if type(f) is datetime.datetime:
                    f = f.strftime(CONFIG.get_Config_Value("Format", "DateTime"))
                self.subfields.append(f)
                choice = choice + str(f) + " "
            return choice

        def _choicesdisplay2ID(self, value, table=None):
            """
            this module scans the choices query for the given value and returns the "choice" based on "value"

            JSON values

            """
            choice = value
            if table == None:
                if "lookup" in self.CONTROLDESCRIPTION:
                    table = self.CONTROLDESCRIPTION["lookup"]
                else:
                    return choice

            sql = "SELECT {key} FROM {table} WHERE {display} = '{field}';".format(
                key=table["key"],
                table=table["table"],
                display=table["display"],
                field=value,
            )
            # sql = SQL.select()
            cursor = self.DBConnection.cursor(buffered=True)
            cursor.execute(sql)
            row = cursor.fetchone()
            cursor.close()
            if row is None:
                return choice
            return row[0]

    class clsDateTime(wx.Panel, clsFieldExtra):
        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)
            description = self.CONTROLDESCRIPTION.copy()
            size = list(description.get("size", [300, 28]))
            position = description.get("pos", wx.DefaultPosition)
            wx.Panel.__init__(
                self, parent.PARENT.FORM, wx.ID_ANY, pos=position, size=size
            )

            class CompositeParent:
                pass

            proxy = CompositeParent()
            proxy.DBConnection = parent.DBConnection
            proxy.PARENT = CompositeParent()
            proxy.PARENT.FORM = self

            date_description = description.copy()
            date_description["type"] = "DatePickerCtrl"
            date_description["pos"] = [0, 0]
            date_description["size"] = [max(120, int(size[0] * 0.6)), size[1]]
            time_description = description.copy()
            time_description["type"] = "TimePickerCtrl"
            time_description["pos"] = [0, 0]
            time_description["size"] = [max(90, size[0] - date_description["size"][0]), size[1]]

            self.datefield = clsField.clsDatePickerCtrl(proxy, date_description)
            self.timefield = clsField.clsTimePickerCtrl(proxy, time_description)
            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(self.datefield, 3, wx.EXPAND)
            sizer.Add(self.timefield, 2, wx.EXPAND | wx.LEFT, 2)
            self.SetSizer(sizer)
            self.SetMinSize(sizer.GetMinSize())

        def SetFont(self, font):
            changed = wx.Panel.SetFont(self, font)
            if hasattr(self, "datefield"):
                self.datefield.SetFont(font)
            if hasattr(self, "timefield"):
                self.timefield.SetFont(font)
            if self.GetSizer():
                self.GetSizer().Layout()
            return changed

        def Disable(self):
            self.datefield.Disable()
            self.timefield.Disable()

        def SetToolTip(self, tooltip):
            wx.Panel.SetToolTip(self, tooltip)
            self.datefield.SetToolTip(tooltip)
            self.timefield.SetToolTip(tooltip)

        def SetValue(self, value):
            date_format = JSForm.CONFIG.get_Config_Value("Format", "Date")
            time_format = JSForm.CONFIG.get_Config_Value("Format", "Time")
            self.datefield.SetValue(value, date_format)
            self.timefield.SetValue(value, time_format)

        def GetValue(self):
            dt = self.datefield.GetValue()
            tm = self.timefield.GetValue()
            if dt is None or tm is None:
                return None
            return datetime.datetime.combine(
                dt, (datetime.datetime.min + tm).time()
            )

        def SetWarningColor(self):
            self.datefield.SetBackgroundColour(FORMColors["Warning"]["bcolor"])
            self.datefield.SetForegroundColour(FORMColors["Warning"]["fcolor"])
            self.timefield.SetBackgroundColour(FORMColors["Warning"]["bcolor"])
            self.timefield.SetForegroundColour(FORMColors["Warning"]["fcolor"])

        def SetNormalColor(self):
            self.datefield.SetBackgroundColour(FORMColors["Normal"]["bcolor"])
            self.datefield.SetForegroundColour(FORMColors["Normal"]["fcolor"])
            # self.timefield.SetForegroundColour(fcolor)    # not supported on all platforms

    class clsDatePickerCtrl(wx.adv.DatePickerCtrl, clsFieldExtra):
        nonevalue = False

        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)
            controldescription = self.CONTROLDESCRIPTION.copy()
            initial_value = controldescription.pop("dt", None)

            # datepicker preprocess
            try:
                controldescription["stylelist"].append("DROPDOWN")
            except:
                controldescription["stylelist"] = ["DROPDOWN"]

            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(controldescription),
            )
            self.SetNormalColor()

            # DatePicker postprocess
            if "stylelist" in controldescription:
                if "ALLOWNONE" in controldescription["stylelist"]:
                    super().SetNullText("")
                    super().SetValue(wx.DateTime())
            if initial_value is not None:
                self.SetValue(initial_value)

        def SetValue(self, value, dateformat=None):
            if not dateformat:
                dateformat = JSForm.CONFIG.get_Config_Value("Format", "Date")
            if not value:
                if (
                    "stylelist" in self.CONTROLDESCRIPTION
                    and "ALLOWNONE" in self.CONTROLDESCRIPTION["stylelist"]
                ):
                    super().SetNullText("")
                    super().SetValue(wx.DateTime())
                    return None
                value = datetime.date.today().strftime(dateformat)
            if isinstance(value, datetime.datetime):
                value = value
            elif isinstance(value, datetime.date):
                value = datetime.datetime.combine(value, datetime.time())
            else:
                value = datetime_value(value, dateformat, "date")
            super().SetValue(value)

        def GetValue(self, format=None):
            try:
                value = super().GetValue()
                dt = datetime.date(value.GetYear(), value.GetMonth() + 1, value.GetDay())
                self.nonevalue = False
            except:
                dt = None
                self.nonevalue = True
            if dt is None:
                return None
            return dt

    class clsTimePickerCtrl(wx.adv.TimePickerCtrl, clsFieldExtra):
        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)
            controldescription = self.CONTROLDESCRIPTION.copy()
            initial_value = controldescription.pop("dt", None)

            # timepicker preprocess

            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(controldescription),
            )
            self.SetNormalColor()
            if initial_value is not None:
                self.SetValue(initial_value)

            # timepicker postprocess

        def SetValue(self, value, timeformat=None):
            if not timeformat:
                timeformat = JSForm.CONFIG.get_Config_Value("Format", "Time")
            if not value:
                if (
                    "stylelist" in self.CONTROLDESCRIPTION
                    and "ALLOWNONE" in self.CONTROLDESCRIPTION["stylelist"]
                ):
                    # wx.adv.TimePickerCtrl has no SetNullText support. The
                    # nullable date in clsDateTime represents the null value.
                    super().SetValue(
                        datetime.datetime.combine(
                            datetime.date.today(), datetime.time()
                        )
                    )
                    return None
                value = datetime.datetime.now().strftime(timeformat)
            if isinstance(value, datetime.datetime):
                value = value
            elif isinstance(value, datetime.time):
                value = datetime.datetime.combine(datetime.date.today(), value)
            elif isinstance(value, datetime.timedelta):
                value = datetime.datetime.combine(datetime.date.today(), datetime.time()) + value
            else:
                value = datetime_value(value, timeformat, "time")
            super().SetValue(value)

        def GetValue(self):
            try:
                value = super().GetValue()
                return datetime.timedelta(
                    hours=value.GetHour(),
                    minutes=value.GetMinute(),
                    seconds=value.GetSecond(),
                )
            except (AttributeError, RuntimeError):
                return None

    class clsCalendarCtrl(wx.adv.CalendarCtrl, clsFieldExtra):
        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)
            description = self.CONTROLDESCRIPTION.copy()
            initial_value = description.pop("date", None)
            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(description),
            )
            self.SetNormalColor()
            if initial_value is not None:
                self.SetValue(initial_value)

        def SetValue(self, value):
            if value in (None, ""):
                value = datetime.date.today()
            if isinstance(value, str):
                dateformat = JSForm.CONFIG.get_Config_Value("Format", "Date")
                value = datetime_value(value, dateformat, "date")
            elif isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
                value = datetime.datetime.combine(value, datetime.time())
            super().SetDate(wx.DateTime.FromDMY(value.day, value.month - 1, value.year))

        def GetValue(self):
            value = super().GetDate()
            return datetime.date(value.GetYear(), value.GetMonth() + 1, value.GetDay())

    class clsFilePickerCtrl(wx.FilePickerCtrl, clsFieldExtra):
        path = ""

        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)

            # filepickerctrl preprocess

            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(self.CONTROLDESCRIPTION),
            )

            # filepickerctrl postprocess

            self.SetInitialDirectory(
                JSForm.CONFIG.get_Config_Value(
                    self.CONTROLDESCRIPTION["directory"][0],
                    self.CONTROLDESCRIPTION["directory"][1],
                )
            )

            self.SetNormalColor()

        def SetValue(self, value):
            filename = value
            if filename == None:
                super().SetPath("")
            else:
                filename = str(value)
                self.path = os.path.dirname(value)
                if not self.path:
                    self.path = JSForm.CONFIG.get_Config_Value(
                        self.CONTROLDESCRIPTION["directory"][0],
                        self.CONTROLDESCRIPTION["directory"][1],
                    )
                filename = os.path.splitext(os.path.basename(value))
                super().SetPath(filename[0] + filename[1])

        def GetValue(self):
            value = str(super().GetPath())
            if value == "":
                return None
            filename = os.path.splitext(os.path.basename(value))
            fn = filename[0] + filename[1]
            return fn

    class clsImagePickerCtrl(wx.Panel, clsFieldExtra):
        """Select, preview, and store an image as database bytes."""

        DEFAULT_WILDCARD = (
            "Image files (*.png;*.jpg;*.jpeg;*.bmp)|*.png;*.jpg;*.jpeg;*.bmp"
        )

        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)
            parameters = getcontrolparameters(self.CONTROLDESCRIPTION)
            super().__init__(parent.PARENT.FORM, wx.ID_ANY, **parameters)
            self._value = None

            self.preview = wx.StaticBitmap(self, wx.ID_ANY)
            self.choose_button = wx.Button(self, wx.ID_ANY, label="Choose image...")
            self.remove_button = wx.Button(self, wx.ID_ANY, label="Remove")
            self.choose_button.Bind(wx.EVT_BUTTON, self._choose_image)
            self.remove_button.Bind(wx.EVT_BUTTON, self._remove_image)

            buttons = wx.BoxSizer(wx.HORIZONTAL)
            buttons.Add(self.choose_button, 0, wx.RIGHT, 6)
            buttons.Add(self.remove_button, 0)
            layout = wx.BoxSizer(wx.VERTICAL)
            layout.Add(self.preview, 1, wx.EXPAND | wx.BOTTOM, 6)
            layout.Add(buttons, 0, wx.ALIGN_LEFT)
            self.SetSizer(layout)
            self.SetNormalColor()
            self._show_placeholder()

        def Enable(self, enable=True):
            result = super().Enable(enable)
            self.choose_button.Enable(enable)
            self.remove_button.Enable(enable and self._value is not None)
            return result

        def Disable(self):
            return self.Enable(False)

        @staticmethod
        def _as_bytes(value):
            if value is None:
                return None
            if isinstance(value, bytes):
                return value
            if isinstance(value, (bytearray, memoryview)):
                return bytes(value)
            raise TypeError("ImagePickerCtrl values must be binary image data or None")

        def SetValue(self, value):
            self._value = self._as_bytes(value)
            self._refresh_preview()

        def GetValue(self):
            return self._value

        def _show_placeholder(self):
            width, height = self._preview_size()
            bitmap = wx.Bitmap(max(width, 1), max(height, 1))
            dc = wx.MemoryDC(bitmap)
            dc.SetBackground(wx.Brush(wx.Colour(245, 245, 245)))
            dc.Clear()
            dc.SetTextForeground(wx.Colour(100, 100, 100))
            text = "No image selected"
            text_width, text_height = dc.GetTextExtent(text)
            dc.DrawText(text, max((width - text_width) // 2, 0), max((height - text_height) // 2, 0))
            dc.SelectObject(wx.NullBitmap)
            self.preview.SetBitmap(bitmap)
            self.remove_button.Enable(False)

        def _preview_size(self):
            width, height = self.GetClientSize()
            button_height = self.choose_button.GetBestSize().height + 8
            return max(width, 120), max(height - button_height, 80)

        def _refresh_preview(self):
            if not self._value:
                self._show_placeholder()
                return
            try:
                image = wx.Image(io.BytesIO(self._value))
                if not image.IsOk():
                    raise ValueError("The stored data is not a supported image.")
                width, height = self._preview_size()
                scale = min(width / image.GetWidth(), height / image.GetHeight())
                scaled_width = max(1, int(image.GetWidth() * scale))
                scaled_height = max(1, int(image.GetHeight() * scale))
                image.Rescale(scaled_width, scaled_height, wx.IMAGE_QUALITY_HIGH)
                self.preview.SetBitmap(wx.Bitmap(image))
                self.remove_button.Enable(self.IsEnabled())
            except (TypeError, ValueError, RuntimeError):
                self._value = None
                self._show_placeholder()

        def _choose_image(self, event):
            wildcard = self.CONTROLDESCRIPTION.get("wildcard", self.DEFAULT_WILDCARD)
            dialog = wx.FileDialog(
                self,
                message=self.CONTROLDESCRIPTION.get("message", "Choose an image"),
                wildcard=wildcard,
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            )
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return
                path = pathlib.Path(dialog.GetPath())
                maximum = self.CONTROLDESCRIPTION.get("maxbytes", 5 * 1024 * 1024)
                if path.stat().st_size > maximum:
                    wx.MessageBox(
                        "The image is too large. The maximum size is {:,.1f} MB.".format(
                            maximum / (1024 * 1024)
                        ),
                        "Image too large",
                        wx.OK | wx.ICON_WARNING,
                    )
                    return
                value = path.read_bytes()
                image = wx.Image(io.BytesIO(value))
                if not image.IsOk():
                    raise ValueError("Unsupported or damaged image file")
                self._value = value
                self._refresh_preview()
            except (OSError, ValueError) as error:
                wx.MessageBox(str(error), "Unable to load image", wx.OK | wx.ICON_ERROR)
            finally:
                dialog.Destroy()

        def _remove_image(self, event):
            self.SetValue(None)

    class clsHTMLCtrl(wx.html.HtmlWindow, clsFieldExtra):
        def __init__(self, parent, controldescription):
            super().init_field(parent, controldescription)
            self.htmlvalue = ""
            super().__init__(
                parent.PARENT.FORM,
                wx.ID_ANY,
                **getcontrolparameters(controldescription),
            )

        def SetValue(self, value):
            self.htmlvalue = "" if value is None else str(value)
            super().SetPage(self.htmlvalue)

        def GetValue(self):
            return self.htmlvalue or None
