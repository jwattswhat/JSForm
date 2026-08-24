"""Application-neutral contracts and controls for dynamic profile fields.

Applications supply already-authorized descriptors and current values. JSForm
renders and validates them but does not discover definitions, enforce business
permissions, or persist application data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Any, Iterable, Mapping

import wx
import wx.adv


FIELD_TYPES = frozenset({
    "short_text", "long_text", "integer", "decimal", "date", "boolean",
    "single_choice", "multiple_choice",
})
FIELD_KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class DynamicFieldError(ValueError):
    """Raised when a dynamic-field descriptor or value is invalid."""


@dataclass(frozen=True)
class DynamicFieldOption:
    """One stable application-provided option for a choice field."""

    key: str
    label: str
    active: bool = True

    def __post_init__(self):
        if not FIELD_KEY.fullmatch(self.key or ""):
            raise DynamicFieldError("An option key must be a stable lowercase identifier.")
        if not str(self.label or "").strip():
            raise DynamicFieldError("An option label is required.")


@dataclass(frozen=True)
class DynamicFieldDescriptor:
    """Describe one authorized dynamic field without application policy data."""

    key: str
    label: str
    data_type: str
    section: str = "Additional information"
    order: int = 0
    required: bool = False
    readonly: bool = False
    visible: bool = True
    help_text: str = ""
    max_length: int | None = None
    minimum: int | Decimal | None = None
    maximum: int | Decimal | None = None
    decimal_places: int = 2
    options: tuple[DynamicFieldOption, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if not FIELD_KEY.fullmatch(self.key or ""):
            raise DynamicFieldError("A field key must be a stable lowercase identifier.")
        if not str(self.label or "").strip():
            raise DynamicFieldError("A field label is required.")
        if self.data_type not in FIELD_TYPES:
            raise DynamicFieldError(f"Unsupported dynamic field type: {self.data_type}")
        if self.order < 0:
            raise DynamicFieldError("Display order cannot be negative.")
        maximum_length = 255 if self.data_type == "short_text" else 2000
        if self.max_length is not None and (
            self.data_type not in {"short_text", "long_text"}
            or not 1 <= self.max_length <= maximum_length
        ):
            raise DynamicFieldError(
                f"{self.data_type.replace('_', ' ').title()} length must be between "
                f"1 and {maximum_length}."
            )
        if self.decimal_places not in range(0, 7):
            raise DynamicFieldError("Decimal places must be between 0 and 6.")
        if self.minimum is not None and self.maximum is not None:
            if Decimal(str(self.minimum)) > Decimal(str(self.maximum)):
                raise DynamicFieldError("Minimum cannot exceed maximum.")
        option_types = {"single_choice", "multiple_choice"}
        if self.data_type in option_types and not self.options:
            raise DynamicFieldError("Choice fields require at least one option.")
        if self.data_type not in option_types and self.options:
            raise DynamicFieldError("Only choice fields may contain options.")
        keys = [item.key.casefold() for item in self.options]
        if len(keys) != len(set(keys)):
            raise DynamicFieldError("Choice option keys must be unique.")


@dataclass(frozen=True)
class DynamicFieldChange:
    """One validated proposed change returned to the owning application."""

    key: str
    value: Any


def normalize_dynamic_value(descriptor: DynamicFieldDescriptor, value: Any) -> Any:
    """Return a typed value or raise a correction-oriented validation error."""
    if value is None or value == "":
        if descriptor.required:
            raise DynamicFieldError(f"{descriptor.label} is required.")
        return None
    kind = descriptor.data_type
    if kind in {"short_text", "long_text"}:
        result = str(value).strip()
        maximum = descriptor.max_length or (255 if kind == "short_text" else 2000)
        if len(result) > maximum:
            raise DynamicFieldError(f"{descriptor.label} cannot exceed {maximum} characters.")
        return result or None
    if kind == "integer":
        try:
            result = int(str(value).strip())
        except (TypeError, ValueError) as error:
            raise DynamicFieldError(f"{descriptor.label} must be a whole number.") from error
        return _bounded_number(descriptor, result)
    if kind == "decimal":
        try:
            result = Decimal(str(value).strip())
        except (InvalidOperation, TypeError, ValueError) as error:
            raise DynamicFieldError(f"{descriptor.label} must be a number.") from error
        exponent = Decimal(1).scaleb(-descriptor.decimal_places)
        return _bounded_number(descriptor, result.quantize(exponent, rounding=ROUND_HALF_UP))
    if kind == "date":
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value).strip())
        except ValueError as error:
            raise DynamicFieldError(f"{descriptor.label} must be a valid date.") from error
    if kind == "boolean":
        if isinstance(value, bool):
            return value
        folded = str(value).strip().casefold()
        if folded in {"1", "true", "yes", "y"}:
            return True
        if folded in {"0", "false", "no", "n"}:
            return False
        raise DynamicFieldError(f"{descriptor.label} must be Yes or No.")
    available = {item.key for item in descriptor.options}
    if kind == "single_choice":
        result = str(value).strip()
        if result not in available:
            raise DynamicFieldError(f"Select a valid value for {descriptor.label}.")
        return result
    if isinstance(value, str):
        values = [item.strip() for item in value.split(",") if item.strip()]
    else:
        values = list(value)
    if len(values) != len(set(values)) or any(item not in available for item in values):
        raise DynamicFieldError(f"Select valid unique values for {descriptor.label}.")
    if descriptor.required and not values:
        raise DynamicFieldError(f"{descriptor.label} is required.")
    return tuple(values)


def _bounded_number(descriptor, value):
    if descriptor.minimum is not None and value < Decimal(str(descriptor.minimum)):
        raise DynamicFieldError(f"{descriptor.label} cannot be less than {descriptor.minimum}.")
    if descriptor.maximum is not None and value > Decimal(str(descriptor.maximum)):
        raise DynamicFieldError(f"{descriptor.label} cannot exceed {descriptor.maximum}.")
    return value


def validate_dynamic_descriptors(
    descriptors: Iterable[DynamicFieldDescriptor], *, maximum_fields: int = 25,
) -> tuple[DynamicFieldDescriptor, ...]:
    """Validate uniqueness and return descriptors in presentation order."""
    items = tuple(descriptors)
    if len(items) > maximum_fields:
        raise DynamicFieldError(f"No more than {maximum_fields} dynamic fields are supported.")
    keys = [item.key.casefold() for item in items]
    if len(keys) != len(set(keys)):
        raise DynamicFieldError("Dynamic field keys must be unique.")
    return tuple(sorted(items, key=lambda item: (item.section.casefold(), item.order, item.label.casefold())))


class DynamicFieldHost(wx.ScrolledWindow):
    """Render authorized descriptors and return validated proposed changes."""

    def __init__(
        self, parent, descriptors: Iterable[DynamicFieldDescriptor],
        values: Mapping[str, Any] | None = None,
    ):
        super().__init__(parent, style=wx.VSCROLL | wx.TAB_TRAVERSAL)
        self.descriptors = validate_dynamic_descriptors(descriptors)
        self.original = dict(values or {})
        self.controls: dict[str, wx.Window] = {}
        self.SetScrollRate(0, 12)
        self._build()

    def _build(self):
        outer = wx.BoxSizer(wx.VERTICAL)
        sections: dict[str, list[DynamicFieldDescriptor]] = {}
        for descriptor in self.descriptors:
            if descriptor.visible:
                sections.setdefault(descriptor.section or "Additional information", []).append(descriptor)
        for section, descriptors in sections.items():
            box = wx.StaticBoxSizer(wx.VERTICAL, self, section)
            grid = wx.FlexGridSizer(cols=2, hgap=10, vgap=7)
            grid.AddGrowableCol(1, 1)
            for descriptor in descriptors:
                label = descriptor.label + (" *" if descriptor.required else "")
                grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
                control = self._control(descriptor, self.original.get(descriptor.key))
                control.Enable(not descriptor.readonly)
                if descriptor.help_text:
                    control.SetToolTip(descriptor.help_text)
                self.controls[descriptor.key] = control
                grid.Add(control, 1, wx.EXPAND)
            box.Add(grid, 1, wx.EXPAND | wx.ALL, 8)
            outer.Add(box, 0, wx.EXPAND | wx.BOTTOM, 8)
        self.SetSizer(outer)
        self.FitInside()

    def _control(self, descriptor, value):
        kind = descriptor.data_type
        if kind == "long_text":
            return wx.TextCtrl(self, value=str(value or ""), style=wx.TE_MULTILINE, size=(-1, 80))
        if kind in {"short_text", "integer", "decimal"}:
            return wx.TextCtrl(self, value="" if value is None else str(value))
        if kind == "boolean":
            control = wx.CheckBox(self)
            control.SetValue(bool(value))
            return control
        if kind == "date":
            control = wx.adv.DatePickerCtrl(self, style=wx.adv.DP_DROPDOWN | wx.adv.DP_ALLOWNONE)
            if value:
                current = normalize_dynamic_value(descriptor, value)
                control.SetValue(wx.DateTime.FromDMY(current.day, current.month - 1, current.year))
            return control
        labels = [item.label for item in descriptor.options]
        if kind == "single_choice":
            control = wx.Choice(self, choices=labels)
            keys = [item.key for item in descriptor.options]
            if value in keys:
                control.SetSelection(keys.index(value))
            return control
        control = wx.CheckListBox(self, choices=labels, size=(-1, min(130, 24 + 18 * len(labels))))
        selected = set(value or ())
        for index, option in enumerate(descriptor.options):
            control.Check(index, option.key in selected)
        return control

    def values(self) -> dict[str, Any]:
        """Return all visible control values after typed validation."""
        return {item.key: normalize_dynamic_value(item, self._raw(item))
                for item in self.descriptors if item.visible}

    def changes(self) -> tuple[DynamicFieldChange, ...]:
        """Return changed, validated values without writing application data."""
        proposed = self.values()
        changes = []
        for descriptor in self.descriptors:
            if not descriptor.visible or descriptor.readonly:
                continue
            original = normalize_dynamic_value(descriptor, self.original.get(descriptor.key))
            if proposed[descriptor.key] != original:
                changes.append(DynamicFieldChange(descriptor.key, proposed[descriptor.key]))
        return tuple(changes)

    def _raw(self, descriptor):
        control = self.controls[descriptor.key]
        if descriptor.data_type == "boolean":
            return control.GetValue()
        if descriptor.data_type == "date":
            value = control.GetValue()
            return None if not value.IsValid() else date(value.GetYear(), value.GetMonth() + 1, value.GetDay())
        if descriptor.data_type == "single_choice":
            index = control.GetSelection()
            return None if index == wx.NOT_FOUND else descriptor.options[index].key
        if descriptor.data_type == "multiple_choice":
            return tuple(descriptor.options[index].key for index in control.GetCheckedItems())
        return control.GetValue()
