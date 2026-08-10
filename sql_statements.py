"""Parameterized write-statement construction for JSForm."""

import re


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_identifier(identifier):
    parts = identifier.split(".")
    if not parts or any(not _IDENTIFIER.fullmatch(part) for part in parts):
        raise ValueError("Unsafe SQL identifier: {}".format(identifier))
    return ".".join("`{}`".format(part) for part in parts)


def database_value(value):
    if isinstance(value, list):
        return "[{}]".format("\r".join(str(item) for item in value))
    return None if value == "" else value


class WriteStatements:
    def __init__(self, table, field_mapper=None):
        self.table = quote_identifier(table)
        self.field_mapper = field_mapper or (lambda field: field)

    def _fields(self, record, omit_none=False):
        fields = []
        values = []
        for field, value in record.items():
            if field == "ID" or (omit_none and value is None):
                continue
            fields.append(quote_identifier(self.field_mapper(field)))
            values.append(database_value(value))
        if not fields:
            raise ValueError("No writable fields were supplied.")
        return fields, values

    def insert(self, record):
        fields, values = self._fields(record, omit_none=True)
        placeholders = ", ".join(["%s"] * len(fields))
        sql = "INSERT INTO {} ({}) VALUES ({});".format(
            self.table, ", ".join(fields), placeholders
        )
        return sql, tuple(values)

    def update(self, record):
        if record.get("ID") is None:
            raise ValueError("An ID is required for an update.")
        fields, values = self._fields(record)
        assignments = ", ".join("{}=%s".format(field) for field in fields)
        return (
            "UPDATE {} SET {} WHERE `ID`=%s;".format(self.table, assignments),
            tuple(values + [record["ID"]]),
        )

    def delete(self, record_id):
        if record_id is None:
            raise ValueError("An ID is required for a delete.")
        return "DELETE FROM {} WHERE `ID`=%s;".format(self.table), (record_id,)

