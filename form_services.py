"""Small, testable services used by the JSForm form coordinator."""

import json
import os
from pathlib import Path

import wx


class FormDefinitionError(RuntimeError):
    pass


def resolve_form_schema(package_file, configured_directory=None):
    """Use JSForm's bundled schema, with the legacy configured path as fallback."""
    package_root = Path(package_file).resolve().parent
    canonical = package_root / "schema" / "unified_schema.json"
    if canonical.is_file():
        return canonical
    if configured_directory:
        legacy = Path(configured_directory) / "jsformschema.json"
        if legacy.is_file():
            return legacy
    raise FormDefinitionError("No JSForm JSON schema is available")


class FormDefinitionLoader:
    def __init__(self, primary_directory, fallback_directory, schema_path=None, validator=None):
        self.primary_directory = Path(primary_directory)
        self.fallback_directory = Path(fallback_directory)
        self.schema_path = Path(schema_path) if schema_path else None
        self.validator = validator

    def _path(self, form_name):
        overlay = os.environ.get("JSFORM_SCREEN_OVERLAY")
        if overlay:
            candidate = Path(overlay) / "{}.json".format(form_name)
            if candidate.is_file():
                return candidate
        primary = self.primary_directory / "{}.json".format(form_name)
        if primary.is_file():
            return primary
        fallback = self.fallback_directory / "{}.json".format(form_name)
        if fallback.is_file():
            return fallback
        raise FormDefinitionError("Form definition not found: {}".format(form_name))

    def load(self, form_name):
        path = self._path(form_name)
        try:
            definition = json.loads(path.read_text(encoding="utf-8-sig"))
            if self.schema_path and self.validator:
                schema = json.loads(self.schema_path.read_text(encoding="utf-8-sig"))
                self.validator(instance=definition, schema=schema)
            root = definition[form_name + "FORM"]
            return root["FORM"], root["CONTROLS"]
        except (KeyError, json.JSONDecodeError) as error:
            raise FormDefinitionError(
                "Invalid form definition: {}".format(path)
            ) from error


def required_fields(sql_description, controls):
    missing = []
    for field, description in sql_description.items():
        if field == "ID" or field not in controls:
            continue
        value = controls[field].GetValue()
        control_description = getattr(controls[field], "CONTROLDESCRIPTION", {})
        if value is None and (
            not description.get("null_ok", True)
            or control_description.get("required", False)
        ):
            missing.append(field)
    return missing


class ControlFactory:
    def __init__(self, field_class, control_id):
        self.field_class = field_class
        self.control_id = control_id

    def build(self, owner, descriptions, connection, readonly=False, readonly_fields=()):
        controls = {}
        readonly_fields = set(readonly_fields)
        for name, source in descriptions.items():
            description = source.copy()
            if readonly or name in readonly_fields:
                description["readonly"] = True
            descriptions[name] = description
            field = self.field_class(owner, self.control_id, description, connection)
            controls[name] = field.FIELD
            control = field.FIELD
            if description.get("foreground"):
                control.SetForegroundColour(description["foreground"])
            if description.get("background"):
                control.SetBackgroundColour(description["background"])
            if any(key in description for key in ("fontface", "fontsize", "bold", "italic")):
                font = control.GetFont()
                if description.get("fontface"):
                    font.SetFaceName(str(description["fontface"]))
                if description.get("fontsize"):
                    font.SetPointSize(int(description["fontsize"]))
                font.SetWeight(wx.FONTWEIGHT_BOLD if description.get("bold") else wx.FONTWEIGHT_NORMAL)
                font.SetStyle(wx.FONTSTYLE_ITALIC if description.get("italic") else wx.FONTSTYLE_NORMAL)
                control.SetFont(font)
        return controls
