"""Read and write application options exposed through the JSForm runtime."""

import mysql
import mysql.connector

import JSForm


def _close_cursor(cursor, operation_failed=False):
    """Close ``cursor`` without masking an active database-operation failure."""
    try:
        cursor.close()
    except Exception:
        if not operation_failed:
            raise


def _missing_optional_framework_table(error):
    """Return whether a framework-default table is intentionally absent."""
    return getattr(error, "errno", None) == 1146


class clsOption:
    """
    clsOption.py - Option Class for Getting and Setting System Options
    Rev. Jonathan C. Watt
    August 9, 2022

    Manages data for local application.

    CREATE TABLE IF NOT EXISTS `tbloptions` (
        `ID` int(11) NOT NULL AUTO_INCREMENT,
        `OptionFor` varchar(255) NOT NULL,
        `OptionType` varchar(255) NOT NULL,
        `OptionValue` longtext NOT NULL,
        `Note` longtext DEFAULT NULL,
    PRIMARY KEY (`ID`)
    )

    """


    def __init__(self, DB=None):
        if not DB:
            self.DBConnection = None
            self.JSConnection = None
        else:
            self.DBConnection = DB.DBConnection
            self.JSConnection = DB.JSConnection

    def set_Option_DBConnection(self, DB):
        """Use an application's paired application/framework connections."""
        self.DBConnection = DB.DBConnection
        self.JSConnection = DB.JSConnection

    def get_Option_Value(self, optionfor, optiontype):
        """Return one value, preferring application options then framework options."""
        if self.DBConnection == None:
            return None
        SQL = "SELECT OptionValue FROM tblOptions WHERE OptionFor = %s AND OptionType = %s;"
        cursor = None
        operation_failed = False
        try:
            cursor = self.DBConnection.cursor()
            cursor.execute(SQL, (optionfor, optiontype))
            row = cursor.fetchone()
        except:
            operation_failed = True
            row = None
        finally:
            if cursor is not None:
                _close_cursor(cursor, operation_failed)
        if not row:
            SQL = "SELECT OptionValue FROM jsOptions WHERE OptionFor = %s AND OptionType = %s;"
            cursor = self.JSConnection.cursor()
            operation_failed = False
            try:
                cursor.execute(SQL, (optionfor, optiontype))
                row = cursor.fetchall()
            except Exception as error:
                operation_failed = True
                if _missing_optional_framework_table(error):
                    row = None
                else:
                    raise
            finally:
                _close_cursor(cursor, operation_failed)
        return row[0] if row else None

    def set_Option_Value(self, optionfor, optiontype, optionvalue):
        """Update an application option without committing the caller's transaction."""
        if self.DBConnection == None:
            return None
        SQL = "UPDATE tblOptions SET OptionValue = %s WHERE OptionFor = %s AND OptionType = %s;"
        cursor = self.DBConnection.cursor()
        operation_failed = False
        try:
            cursor.execute(SQL, (optionvalue, optionfor, optiontype))
        except:
            operation_failed = True
            raise
        finally:
            _close_cursor(cursor, operation_failed)

OPTION = clsOption()
