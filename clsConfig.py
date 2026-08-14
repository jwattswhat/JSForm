"""Read and write framework configuration values stored by an application."""

import mysql
import mysql.connector
from JSForm import clsDB
class clsConfig:
    """
    clsConfig.py - Configuration Class for getting and setting system configuration data
    Rev. Jonathan C. Watt
    July 2022

    this class gives the tools to manager system configuration.
    it first looks in the application configuration table.
    if config value is not found it looks in the JSForm configuration table.

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
            self.JSConnection = None
        else:
            self.DBConnection = DB.DBConnection
            self.JSConnection = DB.JSConnection

    def set_Config_DBConnection(self, DB):
        self.DBConnection = DB.DBConnection
        self.JSConnection = DB.JSConnection

    def get_Config_Value(self, ConfigFamily, ConfigType):
        if self.DBConnection == None:
            return None
        SQL = "SELECT ConfigValue FROM tblConfig WHERE ConfigFamily = '{ConfigFamily}' AND ConfigType = '{ConfigType}';".format(
            ConfigFamily=ConfigFamily, ConfigType=ConfigType)
        cursor = self.DBConnection.cursor()
        try:
            cursor.execute(SQL)
            row = cursor.fetchone()
        except:
            row = None
        cursor.close()
        if not row:
            SQL = "SELECT ConfigValue FROM jsConfig WHERE ConfigFamily = '{ConfigFamily}' AND ConfigType = '{ConfigType}';".format(
                ConfigFamily=ConfigFamily, ConfigType=ConfigType)
            cursor = self.JSConnection.cursor()
            cursor.execute(SQL)
            row = cursor.fetchone()
            cursor.close()
        return row[0]

    def set_Config_Value(self, ConfigFamily, ConfigType, ConfigValue):
        if self.DBConnection == None:
            return None
        SQL = "UPDATE tblConfig SET ConfigFamily = '{ConfigFamily}', ConfigValue = '{ConfigValue}' WHERE ConfigType = '{ConfigType}';".format(
            ConfigFamily=ConfigFamily, ConfigValue=ConfigValue, ConfigType=ConfigType
        )
        cursor = self.DBConnection.cursor()
        cursor.execute(SQL)
        cursor.close()

    def get_Config_Family(self, configfamily):
        if self.DBConnection == None:
            return None
        SQL = "SELECT ConfigType, ConfigValue FROM tblConfig WHERE ConfigFamily = '{configfamily}';".format(
            configfamily=configfamily
                )
        cursor = self.DBConnection.cursor()
        try:
            cursor.execute(SQL)
            rows = cursor.fetchall()
        except:
            rows = None
        cursor.close()
        if not rows:
            SQL = "SELECT ConfigType, ConfigValue FROM jsConfig WHERE ConfigFamily = '{configfamily}';".format(
                configfamily=configfamily
                    )
            cursor = self.JSConnection.cursor()
            cursor.execute(SQL)
            rows = cursor.fetchall()
            cursor.close()
        return rows

CONFIG = clsConfig()            #   Application Configuration
