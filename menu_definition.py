"""Immutable, validated JSON definitions for native application menus."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
from types import MappingProxyType

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "menu_definition_schema.json"


class MenuDefinitionError(ValueError):
    """Report a menu definition that cannot be read or safely validated."""


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value):
    if isinstance(value, MappingProxyType):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class MenuDefinition:
    """An immutable, schema-validated application menu definition."""

    _data: MappingProxyType
    path: Path | None = None
    customized: bool = False

    @property
    def schema_version(self):
        return self._data["schema_version"]

    @property
    def name(self):
        return self._data["name"]

    @property
    def menus(self):
        return self._data["menus"]

    def to_dict(self):
        """Return a detached, mutable representation suitable for JSON output."""
        return _thaw(self._data)


class MenuDefinitionLoader:
    """Load menu JSON and enforce both schema and cross-item invariants."""

    def __init__(self, schema_path=SCHEMA_PATH):
        try:
            schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise MenuDefinitionError(
                "Cannot read menu definition schema: {}".format(schema_path)
            ) from error
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as error:
            raise MenuDefinitionError("Invalid menu definition schema") from error
        self.validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def load(self, source, *, customized=False):
        """Load one UTF-8 menu file and retain its source metadata."""
        path = Path(source)
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as error:
            raise MenuDefinitionError(
                "Cannot read menu definition: {}".format(path)
            ) from error
        try:
            definition = self.from_dict(data)
        except MenuDefinitionError as error:
            raise MenuDefinitionError(
                "Invalid menu definition {}: {}".format(path, error)
            ) from error
        return MenuDefinition(definition._data, path=path, customized=customized)

    def load_application(
        self, starter, customization=None, *, fallback_to_starter=False
    ):
        """Resolve an optional customization with explicit invalid-file fallback.

        A present customization is authoritative. If it is invalid, the error is
        raised unless the application explicitly opts into protected-starter
        fallback. Neither source file is modified by this operation.
        """
        starter = Path(starter)
        custom = Path(customization) if customization is not None else None
        if custom is not None and custom.is_file():
            try:
                return self.load(custom, customized=True)
            except MenuDefinitionError:
                if not fallback_to_starter:
                    raise
        return self.load(starter, customized=False)

    def from_dict(self, data):
        """Validate a mapping and return its immutable definition object."""
        errors = sorted(
            self.validator.iter_errors(data),
            key=lambda error: [str(part) for part in error.absolute_path],
        )
        if errors:
            error = errors[0]
            location = ".".join(str(part) for part in error.absolute_path) or "definition"
            raise MenuDefinitionError(
                "Invalid menu definition at {}: {}".format(location, error.message)
            )
        self._validate_items(data["menus"])
        return MenuDefinition(_freeze(data))

    def _validate_items(self, menus):
        accelerators = {}
        for menu in menus:
            self._validate_menu(menu, accelerators)

    def _validate_menu(self, menu, accelerators):
        items = menu["items"]
        if "separator" in items[0] or "separator" in items[-1]:
            raise MenuDefinitionError(
                "Menu {!r} cannot start or end with a separator".format(menu["label"])
            )
        previous_separator = False
        closed_radio_groups = set()
        active_radio_group = None
        for item in items:
            separator = "separator" in item
            if separator and previous_separator:
                raise MenuDefinitionError(
                    "Menu {!r} cannot contain adjacent separators".format(menu["label"])
                )
            previous_separator = separator
            if "items" in item:
                self._validate_menu(item, accelerators)
            if "command" in item:
                accelerator = item.get("accelerator")
                if accelerator:
                    parts = accelerator.split("+")
                    modifiers = parts[:-1]
                    if len(modifiers) != len(set(modifiers)):
                        raise MenuDefinitionError(
                            "Accelerator {} repeats a modifier".format(accelerator)
                        )
                    normalized = accelerator.casefold()
                    if normalized in accelerators:
                        raise MenuDefinitionError(
                            "Accelerator {} is assigned to both {} and {}".format(
                                accelerator, accelerators[normalized], item["command"]
                            )
                        )
                    accelerators[normalized] = item["command"]
                radio_group = item.get("radio_group")
                if radio_group != active_radio_group:
                    if active_radio_group is not None:
                        closed_radio_groups.add(active_radio_group)
                    if radio_group in closed_radio_groups:
                        raise MenuDefinitionError(
                            "Radio group {!r} must contain adjacent items".format(radio_group)
                        )
                    active_radio_group = radio_group
            elif active_radio_group is not None:
                closed_radio_groups.add(active_radio_group)
                active_radio_group = None


def save_menu_definition(definition, path, *, loader=None):
    """Validate and atomically save a menu definition, retaining a `.bak` copy."""
    if not isinstance(definition, MenuDefinition):
        raise TypeError("definition must be a MenuDefinition")
    loader = loader or MenuDefinitionLoader()
    validated = loader.from_dict(definition.to_dict())
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(validated.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if target.is_file():
            shutil.copyfile(target, target.with_suffix(target.suffix + ".bak"))
        temporary.replace(target)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return target
