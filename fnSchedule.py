"""Provide compatibility scheduling helpers for older JSForm applications."""

import mysql
import datetime

from JSForm import clsDB
from JSForm import clsSQL
from JSForm import clsSMTP
from JSForm import CONFIG

def readonerecord(dbconn, table, parentrecord=None):
    SQL = clsSQL(dbconn, table, parentrecord)
    sql, parameters = SQL.select_statement()
    cursor = dbconn.cursor()
    try:
        cursor.execute(sql, parameters)
        return cursor.fetchone()
    finally:
        cursor.close()


def readallrecords(dbconn, table, parentrecord=None):
    SQL = clsSQL(dbconn, table, parentrecord)
    sql, parameters = SQL.select_statement()
    cursor = dbconn.cursor()
    try:
        cursor.execute(sql, parameters)
        return cursor.fetchall()
    finally:
        cursor.close()


def _insert_service_role(dbconn, service_id, participant_id, role):
    """Insert one scheduled role with every runtime value connector-bound."""
    sql = (
        "INSERT INTO tblServiceRole (ServiceID,ParticipantID,Role) "
        "VALUES (%s,%s,%s);"
    )
    cursor = dbconn.cursor()
    try:
        cursor.execute(sql, (service_id, participant_id, role))
    finally:
        cursor.close()


def strtolist(st):
    if st == None:
        return None
    if "[" in st:
        st = st.replace("[", "")
        st = st.replace("]", "")
        st = st.replace("\n", "")
    else:
        return st
    li = st.split("\r")
    return li


def ScheduleParticipants(ServiceID):

    ChurchDB = clsDB.clsDB("192.168.3.200", "ChurchDB", "church", None)
    ChurchDBConnection = mysql.connector.connect(**ChurchDB.DB)

    # check for previous schedule for this service
    serviceroleTable = {
        "name": "tblServiceRole",
        "fields": ["*"],
        "condition": "ServiceID={ServiceID}",
    }
    servicerolerows = readallrecords(
        ChurchDBConnection, serviceroleTable, {"ServiceID": ServiceID}
    )
    if len(servicerolerows) != 0:
        return None
    servicerolepos = 0

    #   Service Record Constants
    S_ID = 0
    S_Church = 1
    S_DateTime = 2
    S_Propers = 3
    #   Get Service Record
    serviceTable = {
        "name": "tblService",
        "fields": ["*"],
        "condition": "ID = {ServiceID};",
    }
    servicerow = readonerecord(
        ChurchDBConnection, serviceTable, {"ServiceID": ServiceID}
    )

    ServiceDate = servicerow[S_DateTime].strftime("%Y-%m-%d")
    ServiceMonth = servicerow[S_DateTime].strftime("%B")
    ServiceTime = servicerow[S_DateTime].strftime("%I:%M %p")
    ServiceWeek = int(servicerow[S_DateTime].strftime("%U"))
    ServiceDOW = servicerow[S_DateTime].strftime("%A")
    ServiceOddEven = int(servicerow[S_DateTime].strftime("%U")) % 2

    P_Season = 3
    propersTable = {
        "name": "tblPropers",
        "fields": ["*"],
        "condition": "ID = {PropersID};",
    }
    propersrow = readonerecord(
        ChurchDBConnection, propersTable, {"PropersID": servicerow[S_Propers]}
    )
    ServiceSeason = propersrow[P_Season]

    #   participant constants
    P_ID = 0
    P_PersonID = 1
    P_Name = 2
    P_Roles = 3
    P_Schedule = 4
    P_Phone = 5
    P_eMail = 6
    P_Note = 7

    #   participants
    participantTable = {"name": "tblParticipant", "fields": ["*"], "orderby": "ID"}
    participantrows = readallrecords(ChurchDBConnection, participantTable)
    participantpos = 0

    #   Service Schedule Constants
    SS_Desc = 1
    SS_Time = 2
    SS_DOW = 3
    SS_Month = 4
    SS_Season = 5
    SS_Inc = 5

    #   Service Schedule
    scheduleTable = {"name": "tblSchedule", "fields": ["*"], "orderby": "ID"}
    schedulerows = readallrecords(ChurchDBConnection, scheduleTable)
    schedulepos = 0
    scheduleTime = {}
    scheduleMonth = {}
    scheduleDOW = {}
    scheduleSeason = {}
    for s in range(len(schedulerows)):
        dt = datetime.datetime(2022, 1, 1) + schedulerows[s][SS_Time]
        scheduleTime.update({s: dt.strftime("%I:%M %p")})
        scheduleDOW.update({s: strtolist(schedulerows[s][SS_DOW])})
        scheduleMonth.update({s: strtolist(schedulerows[s][SS_Month])})
        scheduleSeason.update({s: strtolist(schedulerows[s][SS_Season])})

    for participant in participantrows:

        prole = strtolist(participant[P_Roles])
        psched = strtolist(participant[P_Schedule])
        if psched == None:
            continue

        for p in range(len(psched)):
            psched[p] = int(psched[p])
        # print(participant[P_Name], "roles", prole, "schedule", psched)
        # print(ServiceTime, ServiceDOW, ServiceMonth, ServiceSeason)
        for s in range(len(schedulerows)):
            # print(scheduleTime[s], scheduleDOW[s], scheduleMonth[s], scheduleSeason[s])
            thisservice = False
            if ServiceTime == scheduleTime[s]:
                if ServiceDOW in scheduleDOW[s]:
                    if scheduleMonth[s] != None:
                        if ServiceMonth in scheduleMonth[s]:
                            thisservice = True
                    elif scheduleSeason[s] != None:
                        if ServiceSeason in scheduleSeason[s]:
                            thisservcie = True
                    else:
                        thisservice = True
            if thisservice:
                for role in prole:
                    _insert_service_role(
                        ChurchDBConnection, servicerow[S_ID], participant[P_ID], role,
                    )

    return


# ScheduleParticipants(5)


def notifyviaeMail(ServiceID):
    global CONFIG

    ChurchDB = clsDB.clsDB("localhost", "ChurchDB", "church", None)
    ChurchDBConnection = mysql.connector.connect(**ChurchDB.DB)
    SMTP = clsSMTP()

    #   Service Record Constants
    S_ID = 0
    S_Church = 1
    S_DateTime = 2
    S_Propers = 3
    #   Get Service Record
    serviceTable = {
        "name": "tblService",
        "fields": ["*"],
        "condition": "ID = {ServiceID};",
    }
    servicerow = readonerecord(
        ChurchDBConnection, serviceTable, {"ServiceID": ServiceID}
    )

    ServiceDate = servicerow[S_DateTime].strftime("%Y-%m-%d")
    ServiceMonth = servicerow[S_DateTime].strftime("%B")
    ServiceTime = servicerow[S_DateTime].strftime("%I:%M %p")
    ServiceWeek = int(servicerow[S_DateTime].strftime("%U"))
    ServiceDOW = servicerow[S_DateTime].strftime("%A")
    ServiceOddEven = int(servicerow[S_DateTime].strftime("%U")) % 2

    SR_ID = 0
    SR_ServiceID = 1
    SR_ParticipantID = 2
    SR_Role = 3
    SR_Note = 4

    # check for previous schedule for this service
    serviceroleTable = {
        "name": "tblServiceRole",
        "fields": ["*"],
        "condition": "ServiceID={ServiceID}",
        "orderby": "ParticipantID",
    }
    servicerolerows = readallrecords(
        ChurchDBConnection, serviceroleTable, {"ServiceID": ServiceID}
    )
    servicerolepos = 0

    #   participant constants
    P_ID = 0
    P_PersonID = 1
    P_Name = 2
    P_Roles = 3
    P_Schedule = 4
    P_Phone = 5
    P_eMail = 6
    P_Note = 7

    #   participants
    participantTable = {
        "name": "tblParticipant",
        "condition": "ID={ParticipantID}",
        "fields": ["*"],
    }
    participantpos = 0

    location = CONFIG.get_Config_Value("Location", "Report")
    filename = location + "WorshipPlanningWorksheet.pdf"

    msg = [
        "Dear Member of Life in Christ\n\nYou have been scheduled to serve in Worship this coming week. Please see the attached file for more infomation.\n\nPastor Watt"
    ]
    reciever = []
    recievername = []
    parttable = participantTable.copy()
    for SR in range(len(servicerolerows)):
        participantrow = readonerecord(
            ChurchDBConnection, parttable,
            {"ParticipantID": servicerolerows[SR][SR_ParticipantID]},
        )
        if participantrow[P_eMail] != None:
            reciever.append(participantrow[P_eMail])
            recievername.append(participantrow[P_Name])
        # print(ServiceDate, participantrow[P_Name],participantrow[P_eMail],servicerolerows[SR][SR_Role])
    SMTP.sendeMail(reciever, recievername, "Worship Planning", msg, filename)

    return
