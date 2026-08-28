"""Read and write framework configuration values stored by an application."""

import mysql
import mysql.connector
from JSForm import clsDB


def _close_cursor(cursor, operation_failed=False):
    """Close ``cursor`` without masking an active database-operation failure."""
    try:
        cursor.close()
    except Exception:
        if not operation_failed:
            raise


class clsConfig:
    """
    clsConfig.py - Configuration Class for getting and setting system configuration data
    Rev. Jonathan C. Watt
    July 2022

    this class gives the tools to manager system configuration.
    Configuration belongs exclusively to the application database.

    ConfigFamily - Group for the configuration value (all may be read at once)
    ConfigType - Individual configuration key

    CREATE TABLE IF NOT EXISTS `tblconfig` (
        `ID` int(11) NOT NULL AUTO_INCREMENT,
        `ConfigFamily` varchar(255) NOT NULL,
        `ConfigType` varchar(100) NOT NULL,
        `ConfigValue` varchar(255) NOT NULL,
        `Note` longtext DEFAULT NULL,
    PRIMARY KEY (`ID`),
    )

    """

    def __init__(self, DB=None):
        if not DB:
            self.DBConnection = None
        else:
            self.DBConnection = DB.DBConnection

    def set_Config_DBConnection(self, DB):
        """Use an application's database connection."""
        self.DBConnection = DB.DBConnection

    def get_Config_Value(self, ConfigFamily, ConfigType):
        """Return one application configuration value, or ``None``."""
        if self.DBConnection == None:
            return None
        SQL = "SELECT ConfigValue FROM tblConfig WHERE ConfigFamily = %s AND ConfigType = %s;"
        cursor = self.DBConnection.cursor()
        operation_failed = False
        try:
            cursor.execute(SQL, (ConfigFamily, ConfigType))
            row = cursor.fetchone()
        except:
            operation_failed = True
            row = None
        finally:
            _close_cursor(cursor, operation_failed)
        return row[0] if row else None

    def set_Config_Value(self, ConfigFamily, ConfigType, ConfigValue):
        """Update an application value without committing the caller's transaction."""
        if self.DBConnection == None:
            return None
        SQL = "UPDATE tblConfig SET ConfigFamily = %s, ConfigValue = %s WHERE ConfigType = %s;"
        cursor = self.DBConnection.cursor()
        operation_failed = False
        try:
            cursor.execute(SQL, (ConfigFamily, ConfigValue, ConfigType))
        except:
            operation_failed = True
            raise
        finally:
            _close_cursor(cursor, operation_failed)

    def get_Config_Family(self, configfamily):
        """Return application configuration rows for one family."""
        if self.DBConnection == None:
            return None
        SQL = "SELECT ConfigType, ConfigValue FROM tblConfig WHERE ConfigFamily = %s;"
        cursor = self.DBConnection.cursor()
        operation_failed = False
        try:
            cursor.execute(SQL, (configfamily,))
            rows = cursor.fetchall()
        except:
            operation_failed = True
            rows = None
        finally:
            _close_cursor(cursor, operation_failed)
        return rows or []

CONFIG = clsConfig()            #   Application Configuration
