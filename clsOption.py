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


    def __init__(self, DBConnection=None):
        self.DBConnection = DBConnection

    def set_Option_DBConnection(self, DBConnection):
        self.DBConnection = DBConnection

    def get_Option_Value(self, optionfor, optiontype):
        if self.DBConnection == None:
            return None
        SQL = 'SELECT OptionValue FROM tblOptions WHERE OptionFor = "{optionfor}" AND OptionType = "{optiontype}";'.format(
            optionfor=optionfor, optiontype=optiontype
        )
        cursor = self.DBConnection.cursor()
        try:
            cursor.execute(SQL)
            row = cursor.fetchone()
        except:
            row = None
        cursor.close()
        if not row:
            cursor = JSFORMOPTION.DBConnection.cursor()
            cursor.execute(SQL)
            row = cursor.fetchall()
            cursor.close()
        return row[0]

    def set_Option_Value(self, optionfor, optiontype, optionvalue):
        if self.DBConnection == None:
            return None
        SQL = "UPDATE tblOption SET OptionValue ='{OptionValue}' WHERE OptionFor = '{OptionFor}' AND OptionValue='{OptionValue}';".format(
            OptionFor=optionfor, OptionType=optiontype, OptionValue=optionvalue
        )
        cursor = self.DBConnection.cursor()
        cursor.execute(SQL)
        cursor.close()

JSFORMOPTION = clsOption()
OPTION = clsOption()
