"""Framework-neutral contracts and immutable data for visual reports."""

from dataclasses import dataclass
from types import MappingProxyType


class ReportDatasetError(ValueError):
    """Raised when report data or bindings violate their declared contract."""

    pass


@dataclass(frozen=True)
class ReportField:
    """Declare one approved report field and its sensitivity classification."""

    name: str
    label: str
    data_type: str = "text"
    sensitivity: str = "ordinary"


@dataclass(frozen=True)
class ReportCollection:
    """Declare a named group of report rows and its optional parent relation."""

    name: str
    label: str
    fields: tuple[ReportField, ...]
    parent: str | None = None
    parent_key: str | None = None

    def field(self, name):
        return next((field for field in self.fields if field.name == name), None)


@dataclass(frozen=True)
class ReportDatasetContract:
    """Versioned allow-list against which a report definition is validated."""

    name: str
    version: int
    required_permission: str
    collections: tuple[ReportCollection, ...]

    def collection(self, name):
        return next((collection for collection in self.collections if collection.name == name), None)

    def validate_definition(self, definition):
        if definition.dataset_name != self.name or definition.dataset_version != self.version:
            raise ReportDatasetError(
                f"Report requires {definition.dataset_name}.v{definition.dataset_version}; "
                f"provider supplies {self.name}.v{self.version}."
            )
        for control in definition.controls.values():
            if control.get("visiblewhen"):
                self._validate_binding(control["visiblewhen"])
            if control.get("collection") and control.get("field"):
                self._validate_binding(control)
            if control["type"] == "table":
                collection = self.collection(control["repeatcollection"])
                if collection is None:
                    raise ReportDatasetError(
                        f"Unknown report collection: {control['repeatcollection']}"
                    )
                for column in control["columns"]:
                    self._validate_binding(column)
                if control.get("colorfield"):
                    self._validate_binding({
                        "collection": control["repeatcollection"],
                        "field": control["colorfield"],
                    })
            if control["type"] == "repeater":
                collection = self.collection(control["repeatcollection"])
                if collection is None:
                    raise ReportDatasetError(
                        f"Unknown report collection: {control['repeatcollection']}"
                    )
                for item in control["items"]:
                    self._validate_binding({
                        "collection": control["repeatcollection"], "field": item["field"]
                    })
            if control["type"] == "matrix":
                collection = self.collection(control["repeatcollection"])
                if collection is None:
                    raise ReportDatasetError(
                        f"Unknown report collection: {control['repeatcollection']}"
                    )
                for key in ("rowfield", "columnfield", "valuefield"):
                    self._validate_binding({
                        "collection": control["repeatcollection"], "field": control[key]
                    })
        for sort in definition.settings.get("sort", ()):
            self._validate_binding(sort)
        for group in definition.settings.get("groups", ()):
            self._validate_binding(group)

    def _validate_binding(self, binding):
        collection = self.collection(binding["collection"])
        if collection is None:
            raise ReportDatasetError(f"Unknown report collection: {binding['collection']}")
        if collection.field(binding["field"]) is None:
            raise ReportDatasetError(
                f"Unknown report field: {binding['collection']}.{binding['field']}"
            )


@dataclass(frozen=True)
class ReportDataset:
    """Immutable report data that has passed a dataset contract."""

    contract: ReportDatasetContract
    collections: MappingProxyType

    @classmethod
    def create(cls, contract, collections):
        expected = {collection.name for collection in contract.collections}
        supplied = set(collections)
        if supplied != expected:
            missing = sorted(expected - supplied)
            unknown = sorted(supplied - expected)
            raise ReportDatasetError(
                f"Dataset collections do not match contract; missing={missing}, unknown={unknown}"
            )
        frozen = MappingProxyType({
            name: tuple(MappingProxyType(dict(row)) for row in rows)
            for name, rows in collections.items()
        })
        for collection in contract.collections:
            allowed = {field.name for field in collection.fields}
            for row in frozen[collection.name]:
                unknown = set(row) - allowed
                if unknown:
                    raise ReportDatasetError(
                        f"Unexpected fields in {collection.name}: {sorted(unknown)}"
                    )
        return cls(contract, frozen)
