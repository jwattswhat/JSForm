"""Read and write application options exposed through the JSForm runtime."""

import mysql
import mysql.connector

import JSForm
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
        self.DBConnection = DB.DBConnection
        self.JSConnection = DB.JSConnection

    def get_Option_Value(self, optionfor, optiontype):
        if self.DBConnection == None:
            return None
        SQL = 'SELECT OptionValue FROM tblOptions WHERE OptionFor = "{optionfor}" AND OptionType = "{optiontype}";'.format(
            optionfor=optionfor, optiontype=optiontype
        )
        try:
            cursor = self.DBConnection.cursor()
            cursor.execute(SQL)
            row = cursor.fetchone()
        except:
            row = None
        cursor.close()
        if not row:
            SQL = 'SELECT OptionValue FROM jsOptions WHERE OptionFor = "{optionfor}" AND OptionType = "{optiontype}";'.format(
            optionfor=optionfor, optiontype=optiontype
            )

            cursor = self.JSConnection.cursor()
            cursor.execute(SQL)
            row = cursor.fetchall()
            cursor.close()
        return row[0]

    def set_Option_Value(self, optionfor, optiontype, optionvalue):
        if self.DBConnection == None:
            return None
        SQL = "UPDATE tblOptions SET OptionValue ='{OptionValue}' WHERE OptionFor = '{OptionFor}' AND OptionType='{OptionType}';".format(
            OptionFor=optionfor, OptionType=optiontype, OptionValue=optionvalue
        )
        cursor = self.DBConnection.cursor()
        cursor.execute(SQL)
        cursor.close()

OPTION = clsOption()
