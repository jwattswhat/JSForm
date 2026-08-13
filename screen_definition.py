"""Validated loading and safe persistence for native JSForm screen JSON."""

from copy import deepcopy
import json
from pathlib import Path
import shutil

from jsonschema import validate

from JSForm.form_services import FormDefinitionError, resolve_form_schema


class ScreenDefinition:
    def __init__(self, data, path=None):
        self._data = deepcopy(data)
        self.path = Path(path) if path else None
        self.root_name = next(iter(self._data))

    @property
    def form_name(self):
        return self.root_name[:-4]

    @property
    def form(self):
        return self._data[self.root_name]["FORM"]

    @property
    def controls(self):
        return self._data[self.root_name]["CONTROLS"]

    def to_dict(self):
        return deepcopy(self._data)


class ScreenDefinitionLoader:
    def __init__(self, schema_path=None):
        self.schema_path = Path(schema_path) if schema_path else resolve_form_schema(__file__)

    def from_dict(self, data, expected_name=None):
        if not isinstance(data, dict) or len(data) != 1:
            raise FormDefinitionError("A screen definition must contain exactly one named root")
        root_name = next(iter(data))
        if not root_name.endswith("FORM"):
            raise FormDefinitionError("The screen root name must end with FORM")
        form_name = root_name[:-4]
        if expected_name and form_name.casefold() != expected_name.casefold():
            raise FormDefinitionError(
                "The filename and screen root name must match: {}".format(expected_name)
            )
        try:
            schema = json.loads(self.schema_path.read_text(encoding="utf-8-sig"))
            validate(instance=data, schema=schema)
            root = data[root_name]
        except FormDefinitionError:
            raise
        except Exception as error:
            raise FormDefinitionError("Invalid screen definition: {}".format(error)) from error
        return ScreenDefinition(data)

    def load(self, path):
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as error:
            raise FormDefinitionError("Cannot read screen definition: {}".format(path)) from error
        definition = self.from_dict(data, path.stem)
        definition.path = path
        return definition


def save_screen_definition(definition, path):
    path = Path(path)
    loader = ScreenDefinitionLoader()
    validated = loader.from_dict(definition.to_dict(), path.stem)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    previous = path.with_suffix(path.suffix + ".bak")
    temporary.write_text(
        json.dumps(validated.to_dict(), indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if path.is_file():
        shutil.copyfile(path, previous)
    temporary.replace(path)
    return path
