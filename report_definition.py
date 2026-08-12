"""Validated immutable definitions for JSForm visual reports."""

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
from types import MappingProxyType

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "report_definition_schema.json"


class ReportDefinitionError(ValueError):
    pass


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
class ReportDefinition:
    _data: MappingProxyType

    @property
    def root_name(self):
        return next(iter(self._data))

    @property
    def root(self):
        return self._data[self.root_name]

    @property
    def settings(self):
        return self.root["REPORT"]

    @property
    def schema_version(self):
        return self.settings["schema_version"]

    @property
    def report_id(self):
        return self.settings["name"]

    @property
    def title(self):
        return self.settings["title"]

    @property
    def dataset_name(self):
        return self.settings["dataset"]

    @property
    def dataset_version(self):
        return self.settings["datasetversion"]

    @property
    def bands(self):
        return self.settings["bands"]

    @property
    def controls(self):
        return self.root["CONTROLS"]

    def to_dict(self):
        return _thaw(self._data)


class ReportDefinitionLoader:
    def __init__(self, schema_path=SCHEMA_PATH):
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def load(self, source):
        path = Path(source)
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as error:
            raise ReportDefinitionError(f"Cannot read report definition: {path}") from error
        return self.from_dict(data)

    def from_dict(self, data):
        errors = sorted(self.validator.iter_errors(data), key=lambda error: list(error.path))
        if errors:
            error = errors[0]
            location = ".".join(str(part) for part in error.absolute_path) or "definition"
            raise ReportDefinitionError(f"Invalid report definition at {location}: {error.message}")
        self._validate_unique_ids(data)
        return ReportDefinition(_freeze(data))

    @staticmethod
    def _validate_unique_ids(data):
        root_name, root = next(iter(data.items()))
        if root["REPORT"]["name"] != root_name[:-6]:
            raise ReportDefinitionError(
                f"Report name {root['REPORT']['name']} does not match root {root_name}"
            )
        bands = root["REPORT"]["bands"]
        for band_name, band in bands.items():
            if band.get("minimumheight", 0) > band["height"]:
                raise ReportDefinitionError(
                    f"Band {band_name} minimumheight cannot exceed its height"
                )
        for group in root["REPORT"].get("groups", []):
            for key, expected_type in (("headerband", "groupheader"), ("footerband", "groupfooter")):
                band_name = group[key]
                if band_name not in bands or bands[band_name]["type"] != expected_type:
                    raise ReportDefinitionError(
                        f"Group {group['name']} uses invalid {key} {band_name}"
                    )
        for control_name, control in root["CONTROLS"].items():
            if control["band"] not in bands:
                raise ReportDefinitionError(
                    f"Control {control_name} uses unknown band {control['band']}"
                )
            if control["type"] == "aggregate" and control.get("scope") == "group":
                groups = {item["name"] for item in root["REPORT"].get("groups", [])}
                if control.get("group") not in groups:
                    raise ReportDefinitionError(
                        f"Aggregate control {control_name} uses unknown group {control.get('group')}"
                    )


def save_report_definition(definition, path):
    """Atomically save a previously validated definition."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(definition.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if target.exists():
        shutil.copyfile(target, target.with_suffix(target.suffix + ".bak"))
    temporary.replace(target)
