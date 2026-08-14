"""Search-and-select proof for the JSForm sample application."""

import wx
import JSForm


def students(connection):
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT s.ID,s.FirstName,s.LastName,s.Grade,"
            "COALESCE(rs.StopName,'No stop assigned') "
            "FROM sb_student s LEFT JOIN sb_route_stop rs ON rs.ID=s.RouteStopID "
            "WHERE s.Active=1 ORDER BY s.LastName,s.FirstName"
        )
        return [
            {"id": row[0], "first": row[1], "last": row[2], "grade": row[3], "stop": row[4]}
            for row in cursor.fetchall()
        ]
    finally:
        cursor.close()


def show_student_finder(parent, connection):
    rows = students(connection)
    grades = tuple(sorted({row["grade"] for row in rows if row["grade"]}))
    dialog = JSForm.SearchSelectDialog(
        parent, title="Find Student", rows=rows,
        columns=(
            JSForm.SearchSelectColumn("Last name", "last", 180),
            JSForm.SearchSelectColumn("First name", "first", 180),
            JSForm.SearchSelectColumn("Grade", "grade", 80),
            JSForm.SearchSelectColumn("Assigned stop", "stop", 270),
        ),
        search_fields=("first", "last", "stop"),
        filters=(JSForm.SearchSelectFilter("Grade", "grade", grades),),
        instructions="Type any part of a name or stop, optionally choose a grade, then select a student.",
    )
    try:
        if dialog.ShowModal() == wx.ID_OK:
            selected = next((row for row in rows if row["id"] == dialog.selected_id()), None)
            if selected:
                wx.MessageBox(
                    "{} {}\nGrade {}\n{}".format(
                        selected["first"], selected["last"], selected["grade"], selected["stop"],
                    ),
                    "Selected Student", parent=parent,
                )
    finally:
        dialog.Destroy()
