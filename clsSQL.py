"""
    clsSQL - classes for handling SQL 
    Rev. Jonathan C. Watt
    August 1, 2022
"""


from mysql.connector import FieldType
import datetime

import JSForm
from JSForm.sql_statements import WriteStatements


class ConditionCompilationError(ValueError):
    """Raised when a dynamic SELECT condition cannot be compiled safely."""


class clsSQL:
    """
    clsSQL - Manages SQL Statements

    dbConnection - SQL Database connection
    table - python dictionary describing the SQL Table
    parentrecord - calling parent record

    table {
        "name":"{tablename}"
        "fields:["fieldname","fieldname"] - ex.  ["lastname","FirstName"]
        "condition":"{valid sql condition}" - ex, "ID = {parentrecord[ID]}
        "orderby":"{valid sql orderby statement}" - ex. "lastname, firstname DESC"
    }

    data may be incorporated in "condition" statment which includes values from tblOptions
        format is {OPTION:{optionfor}:{optiontype}}  ex. "condition":"Lectionary = {OPTION:Lectionary:Current}"

    """
    class clsAsPairs:
        def __init__(self, sqlcolumns):
            self.find(sqlcolumns)

        def find(self, sqlcolumns):
            self._aspairs = {}
            for i in range(len(sqlcolumns)):
                s = sqlcolumns[i].find(" as ")
                if s != -1:
                    e = s + 4
                    first = sqlcolumns[i][:s]
                    last = sqlcolumns[i][e:]
                    self._aspairs.update({last: first})

        def getall(self, fieldlist):
            returnlist = []
            for i in range(len(fieldlist)):
                returnlist.append(self.get(fieldlist[i]))
            return returnlist

        def get(self, field):
            if field in self._aspairs:
                return self._aspairs[field]
            return field

    def __init__(self, dbconnection, table, parentrecord=None):
        self.dbconnection = dbconnection
        self.table = table
        self.parentrecord = parentrecord
        self.aspairs = self.clsAsPairs(self.table["fields"])
        self.sqldescription = self._build_sql_record_description()
        self.select_parameters = ()

    def select(self, tbl=None):
        """Return parameterized SELECT text; use ``select_statement`` to execute it."""
        sql, parameters = self.select_statement(tbl)
        self.select_parameters = parameters
        return sql

    def select_statement(self, tbl=None):
        """Return ``(sql_text, parameters)`` for safe connector execution."""
        if tbl == None:
            table = self.table.copy()
        else:
            table = tbl.copy()
        sql = ""
        if "name" in table:
            if table["fields"] == ["*"]:
                sql = "SELECT {fields} FROM {table} ".format(
                    fields=", ".join(table["fields"]),
                    table=table["name"],
                )
            else:
                sql = "SELECT {fields} FROM {table} ".format(
                    fields=", ".join(table["fields"]),
                    table=table["name"],
                )
        if "condition" in table:
            condition, parameters = self.compile_condition(table["condition"])
            sql = sql + "WHERE {condition} ".format(condition=condition)
        else:
            parameters = ()
        if "orderby" in table:
            sql = sql + "ORDER BY {orderby}".format(orderby=table["orderby"])
        self.select_parameters = parameters
        return sql, parameters

    def compile_condition(self, condition, parentrecord=None):
        """Compile runtime placeholders to connector parameters from left to right."""
        if not isinstance(condition, str):
            raise ConditionCompilationError("SELECT condition must be a string.")
        record = self.parentrecord if parentrecord is None else parentrecord
        parameters = []
        output = []
        position = 0
        while position < len(condition):
            start = condition.find("{", position)
            closing_before_start = condition.find("}", position)
            if closing_before_start != -1 and (start == -1 or closing_before_start < start):
                raise ConditionCompilationError("Malformed SELECT condition placeholder.")
            if start == -1:
                output.append(condition[position:])
                break
            output.append(condition[position:start])
            end = condition.find("}", start + 1)
            if end == -1 or condition.find("{", start + 1, end) != -1:
                raise ConditionCompilationError("Malformed SELECT condition placeholder.")
            token = condition[start + 1:end]
            if token.startswith("OPTION:"):
                components = token.split(":")
                if len(components) != 3 or not components[1] or not components[2]:
                    raise ConditionCompilationError("Malformed OPTION condition placeholder.")
                # Preserve the historical, externally visible component mapping.
                optionvalue, optionfor = components[1], components[2]
                value = JSForm.OPTION.get_Option_Value(optionfor, optionvalue)
            else:
                if not token or ":" in token:
                    raise ConditionCompilationError("Unknown SELECT condition placeholder.")
                if record is None:
                    raise ConditionCompilationError(
                        "Parent record is required for placeholder {{{}}}.".format(token)
                    )
                if token not in record:
                    raise ConditionCompilationError(
                        "Parent record has no field named {}.".format(token)
                    )
                value = record[token]
            output.append("%s")
            parameters.append(value)
            position = end + 1
        return "".join(output), tuple(parameters)

    def conditionCONFIG(self, condition):
        """Compatibility wrapper returning safely parameterized condition text."""
        compiled, parameters = self.compile_condition(condition)
        self.select_parameters = parameters
        return compiled

    def condition(self, condition, parentrecord=None):
        """Compatibility wrapper returning safely parameterized condition text."""
        compiled, parameters = self.compile_condition(condition, parentrecord)
        self.select_parameters = parameters
        return compiled

    def insert(self, record):
        ky, va = self._prepare_keys_values(record)

        keys = []
        values = []
        for k in range(len(va)):  # remove all fields with None.
            if va[k] != "Null":
                keys.append(ky[k])
                val = va[k].replace(
                    "\\", "\\\\"
                )  # replace all \\ with \\\\ for SQL Execute Statement.
                values.append(val)
        sql = "INSERT INTO {table} ({keys}) VALUES ({values});".format(
            table=self.table["name"], keys=", ".join(keys), values=", ".join(values)
        )
        return sql

    def insert_statement(self, record):
        return WriteStatements(self.table["name"], self.aspairs.get).insert(record)

    def update(self, record):
        keys, values = self._prepare_keys_values(record)
        valuestrings = []
        for k in range(len(keys)):
            if type(values[k])==str:
                value = values[k].replace(
                    "\\", "\\\\"
                )  # replace all \\ with \\\\ for SQL Execute Statement.
            else:
                value = values[k]
            valuestrings.append("{key}={value}".format(key=keys[k], value=value))

        sql = "UPDATE {table} SET {values} WHERE ID={id};".format(
            table=self.table["name"],
            values=", ".join(valuestrings),
            id=record["ID"],
        )

        return sql

    def update_statement(self, record):
        return WriteStatements(self.table["name"], self.aspairs.get).update(record)

    def delete(self, recordID):
        return "DELETE FROM {tablename} WHERE ID = {ID};".format(
            tablename=self.table["name"], ID=recordID
        )

    def delete_statement(self, recordID):
        return WriteStatements(self.table["name"], self.aspairs.get).delete(recordID)

    def get_sql_field_description(self, field):
        return self.sqldescription[field]

    def get_sql_record_description(self):
        return self.sqldescription

    def format_by_sql_description(self, field, value):
        global CONFIG

        if (value == None) or (value == ""):
            return "NULL"
        match self.sqldescription[field]["type"]:
            case "TINY":
                return value == 1
            case "LONG"|"FLOAT":
                return value
            case "TIME"|"DATE"|"DATETIME":
                return value
            case other:
                return value

    def format_sql_records(self, sqlrows):
        returnrecords = []
        for row in range(len(sqlrows)):
            record = {}
            for column, columnname in enumerate(list(self.sqldescription.keys())):
                field = sqlrows[row][column]
                if field == "":
                    field = None
                record.update({columnname: self._format_for_record(columnname, field)})
            returnrecords.append(record)
        return returnrecords

    def get_blank_record(self):

        record = {}
        for key in self.sqldescription:
            match self.sqldescription[key]["type"]:
                case "TINY":  # Check for Boolean
                    record.update({key: False})
                case _:
                    record.update({key: None})
        if record != {}:
            return record
        return None

    #   internal methods

    def _build_sql_record_description(self):
        sql = "SELECT {fields} FROM {table} LIMIT 1;".format(
            fields=",".join(self.table["fields"]), table=self.table["name"]
        )

        cursor = self.dbconnection.cursor()
        cursor.execute(sql)
        row = cursor.fetchone()

        recorddescription = {}
        for column in cursor.description:
            recorddescription.update(
                {
                    column[0]: {
                        "type": FieldType.get_info(column[1]),
                        "null_ok": (column[6] == 1),
                        "flags": column[7],
                    }
                }
            )
        cursor.close()
        return recorddescription

    def _prepare_keys_values(self, record):
        rec = record.copy()
        for d in rec.copy():
            if d == "ID":
                rec.pop("ID")
                continue
            rec[d] = self._format_with_description(d, rec[d])
        values = list(rec.values())

        keys = list(rec.keys())
        keys = self.aspairs.getall(keys)

        return keys, values

    def _string_to_list(self, st):
        stripit = ["[", "]", ","]
        if st[:1] != "[":
            return str(st)
        for s in stripit:
            st = st.replace(s, "")
        return st.splitlines()

    def _format_for_record(self, field, value):
        # print(self, field, value)
        if value == None:
            return None

        match self.sqldescription[field]["type"]:

            #   string types

            case "VAR_STRING"|"STRING":
                value = self._string_to_list(value)

            case "BLOB":
                # Binary BLOB values such as images must remain connector-native
                # bytes. Historical text BLOBs retain the legacy list parsing.
                if not isinstance(value, (bytes, bytearray, memoryview)):
                    value = self._string_to_list(value)

            #   Boolean types

            case "TINY":
                if value:
                    value = True
                else:
                    value = False

            #   Numeric

            case "SHORT"|"LONG"|"LONGLONG"|"INT24"|"YEAR"|"FLOAT"|"DOUBLE":
                value = value

            case "NEWDECIMAL":
                value = str(value)

            #   Date and Time Types

            case "DATETIME"|"DATE"|"TIME":
                # Keep connector-native temporal values in the record. Controls
                # own presentation formatting; parameterized writes send these
                # values back to MariaDB without a locale-dependent round-trip.
                value = value

            #   Default to string type

            case other:
                value = '"' + str(value) + '"'

        # print (field," : ",self.sqldescription[field]["type"]," : ",value)
        return value

    def _list_to_string(self, li):
        if type(li) != list:
            return "'" + li + "'"
        for l in range(len(li)):
            li[l] = li[l].replace("'", "'")
            li[l] = li[l].replace('"', '"')
            li[l] = li[l].replace("'", "'")
            li[l] = li[l].replace('"', '"')
        return "'[" + "\r".join(li) + "]'"

    def _format_with_description(self, field, value):
        if value == None:
            return "Null"

        # print (field,value,self.sqldescription[field]["type"])
        match self.sqldescription[field]["type"]:
            #   String types
            case "VAR_STRING":
                value = self._list_to_string(value)

            case "STRING":
                value = self._list_to_string(value)

            case "BLOB":
                value = self._list_to_string(value)

            #   Boolean types

            case "TINY":
                if value:
                    value = "True"
                else:
                    value = "False"

            #   Numeric Types

            case "LONG":
                value = str(value)

            case "FLOAT":
                value = str(value)
            case "NEWDECIMAL":
                value = str(value)

            #   Date and Time Types

            case "DATETIME":
                value = "STR_TO_DATE('{date}','{dateformat}')".format(
                    date=value,
                    dateformat=JSForm.CONFIG.get_Config_Value("SQLFormat", "DateTime"),
                )
            case "DATE":
                value = "STR_TO_DATE('{date}','{dateformat}')".format(
                    date=value, dateformat=JSForm.CONFIG.get_Config_Value("SQLFormat", "Date")
                )

            case "TIME":
                value = "STR_TO_DATE('{time}','{dateformat}')".format(
                    time=value, dateformat=JSForm.CONFIG.get_Config_Value("SQLFormat", "Time")
                )

            #   Default to string type

            case other:
                value = "'" + +str(value) + "'"

        return value
