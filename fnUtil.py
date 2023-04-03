"""
    clsUtils

    useful utility Functions

"""
import datetime

import JSForm

def hexdump(str):
    asc = "AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz"
    width = 20
    h = ""
    w = 0
    while w < len(str):
        s = str[w : w + width]
        for c in s:
            if c in asc:
                h = h + c
            else:
                h = h + "."

        h = h + " | "
        for c in s:
            h = h + "{:02x} ".format(ord(c))

        h = h + chr(10) + chr(13)
        w = w + width
        if w > len(str):
            w = len(str)
    return h


def stripcrlf(str):
    rem = chr(10) + chr(13)
    s = ""
    for c in str:
        if c in rem:
            continue
        s = s + c
    return s


# convert character positioning to point positioning


def charactertopoint(formdescription, controldescription):
    formdescription = desccharactertopoint(formdescription)

    for control in controldescription:
        controldescription[control] = desccharactertopoint(controldescription[control])

    return formdescription, controldescription


def desccharactertopoint(description):

    newdesc = description
    if "pos" in description:  # if "pos" exists it is not overridden by "posch"
        return newdesc
    newdesc["pos"] = [
        JSForm.FONT.chtopt(description["posch"][0]),
        JSForm.FONT.lntopt(description["posch"][1]),
    ]

    if "size" in description:  # if size exists it is not overridden by "sizech"
        return newdesc
    if "sizech" in description:  # size in not a required entry
        newdesc["size"] = [
            JSForm.FONT.chtopt(description["sizech"][0]),
            JSForm.FONT.lntopt(description["sizech"][1]),
        ]
    return newdesc


def convertNavButtons(NavControls):
    for section in NavControls:
        for control in NavControls[section]:
            NavControls[section][control] = desccharactertopoint(
                NavControls[section][control]
            )
    return NavControls


from datetime import datetime, timedelta, date, time


def next_weekday(d, weekday):
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return date_to_datetime(d + timedelta(days_ahead))


def date_to_datetime(dt):
    return datetime.combine(dt, datetime.min.time())


# print("{:02x}".format(ord("\r")))
# print("{:02x}".format(ord("\n")))
# str = "AaBbCc\r\nDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz"
# print(hexdump(str))
# print()
# print(hexdump(stripcrlf(str)))
