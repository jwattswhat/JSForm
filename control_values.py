"""Value normalization shared by JSForm's wxPython controls."""

import datetime
import json
from decimal import Decimal


def multiline_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return "\r\n".join(str(item) for item in value)


def number_value(value, kind="number"):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1].strip()
    if kind == "currency":
        text = text.replace("$", "")
    if not text:
        return None
    if kind == "float":
        return float(text)
    if kind == "currency" or "." in text or "e" in text.lower():
        return Decimal(text)
    return int(text)


def normalized_json(value):
    if value in (None, ""):
        return None
    parsed = json.loads(value) if isinstance(value, str) else value
    return json.dumps(parsed, separators=(",", ":"))


def checked_value(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return value is True or value == 1


def value_sequence(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def datetime_value(value, value_format, kind):
    if isinstance(value, datetime.datetime):
        return value
    if kind == "date" and isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.time())
    if kind == "time" and isinstance(value, datetime.time):
        return datetime.datetime.combine(datetime.date.today(), value)
    if kind == "time" and isinstance(value, datetime.timedelta):
        return datetime.datetime.combine(datetime.date.today(), datetime.time()) + value
    return datetime.datetime.strptime(str(value), value_format)


def native_date(value, value_format=None):
    """Return a database-ready ``date`` while accepting legacy display text."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if not value_format:
        raise ValueError("A format is required to parse a text date.")
    return datetime.datetime.strptime(str(value), value_format).date()


def native_time(value, value_format=None):
    """Return MariaDB TIME as ``timedelta`` while accepting UI time values."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime.timedelta):
        return value
    if isinstance(value, datetime.datetime):
        value = value.time()
    if isinstance(value, datetime.time):
        return datetime.timedelta(
            hours=value.hour,
            minutes=value.minute,
            seconds=value.second,
            microseconds=value.microsecond,
        )
    if not value_format:
        raise ValueError("A format is required to parse a text time.")
    parsed = datetime.datetime.strptime(str(value), value_format).time()
    return native_time(parsed)


def native_datetime(value, value_format=None):
    """Return a database-ready ``datetime`` while accepting legacy display text."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.time())
    if not value_format:
        raise ValueError("A format is required to parse text date and time.")
    return datetime.datetime.strptime(str(value), value_format)
