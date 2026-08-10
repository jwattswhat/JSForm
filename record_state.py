"""Database-independent record navigation and dirty-state tracking."""

import datetime
from decimal import Decimal


def comparable_value(value):
    """Normalize equivalent database/control values without display formatting."""
    if value == "":
        return None
    if isinstance(value, datetime.datetime):
        return ("datetime", value.replace(tzinfo=None))
    if isinstance(value, datetime.date):
        return ("date", value)
    if isinstance(value, datetime.time):
        return (
            "time",
            datetime.timedelta(
                hours=value.hour,
                minutes=value.minute,
                seconds=value.second,
                microseconds=value.microsecond,
            ),
        )
    if isinstance(value, datetime.timedelta):
        return ("time", value)
    if isinstance(value, Decimal):
        return ("number", value.normalize())
    return value


class OriginalRecord:
    def __init__(self):
        self.record = {}

    def save(self, record):
        self.record = {
            field: None if value == "" else value for field, value in record.items()
        }

    # Compatibility with the historical API.
    saverecord = save

    def savefield(self, field, value):
        self.record[field] = None if value == "" else value

    def getsavedfield(self, field):
        return self.record[field]

    def restore(self):
        return self.record

    def comparefield(self, field, value):
        return comparable_value(value) == comparable_value(self.record[field])


class RecordState:
    """Own a navigable record collection without any database dependency."""

    def __init__(self):
        self.original = OriginalRecord()
        self._record = None
        self._position = 0

    def add(self, record):
        if self.isempty():
            self._record = []
        self._record.append(record)
        return self.last()

    def delete(self):
        if self.isempty():
            return None
        self._record.pop(self._position)
        if not self._record:
            self._position = 0
            return None
        self._position = min(self._position, len(self._record) - 1)
        return self.current()

    def current(self):
        if not self.isempty() and self._record:
            return self._record[self._position]
        return None

    def currentfield(self, field):
        return self.current()[field]

    def currentnum(self):
        return self._position

    def _select(self, position):
        if self.isempty() or not self._record:
            return None
        self._position = position
        self.original.save(self.current())
        return self.current()

    def first(self):
        return self._select(0)

    def prev(self, loop=False):
        if self.isempty() or not self._record:
            return None
        if self._position > 0:
            return self._select(self._position - 1)
        return self.last() if loop else self._select(0)

    def next(self, loop=False):
        if self.isempty() or not self._record:
            return None
        if self._position < len(self._record) - 1:
            return self._select(self._position + 1)
        return self.first() if loop else self._select(self._position)

    def last(self):
        if self.isempty() or not self._record:
            return None
        return self._select(len(self._record) - 1)

    def setfieldvalue(self, field, value):
        self.current()[field] = value

    def updatecurrentrec(self, record):
        self._record[self._position] = record

    def getcurrentID(self):
        current = self.current()
        return current.get("ID") if current else None

    def getfield(self, name):
        return self.current()[name]

    def setControlID(self, name, ID):
        self.current()[name].update({"ControlID": ID})

    def ControlID(self):
        return self.current()["ControlID"]

    def get_field_by_name(self, fieldname):
        current = self.current()
        return current.get(fieldname) if current else None

    def isempty(self):
        return self._record is None

    def fieldisdirty(self, field):
        return comparable_value(self.original.record.get(field)) != comparable_value(
            self.current()[field]
        )

    def recordisdirty(self):
        current = self.current()
        if not current:
            return []
        return [field for field in current if self.fieldisdirty(field)]
