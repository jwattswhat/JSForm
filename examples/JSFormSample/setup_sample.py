"""Create the isolated database/account and reset fictional sample tables."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

import mysql.connector


def statements(text):
    return [part.strip() for part in text.split(";") if part.strip()]


def main():
    parser = argparse.ArgumentParser(description="Install the isolated JSForm School Bus Sample")
    parser.add_argument("--server", default="localhost")
    parser.add_argument("--admin-user", default="root")
    parser.add_argument("--database", default="JSFormSample")
    parser.add_argument("--sample-user", default="jsform_sample")
    args = parser.parse_args()
    if args.database != "JSFormSample" or args.sample_user != "jsform_sample":
        raise SystemExit("The sample installer uses the fixed isolated database and account names.")
    admin_password = getpass.getpass("MariaDB administrative password for {}: ".format(args.admin_user))
    sample_password = getpass.getpass("Choose a password for jsform_sample: ")
    confirmation = getpass.getpass("Confirm the jsform_sample password: ")
    if not sample_password or sample_password != confirmation:
        raise SystemExit("The sample passwords did not match.")
    admin = mysql.connector.connect(host=args.server, user=args.admin_user, password=admin_password)
    try:
        cursor = admin.cursor()
        try:
            cursor.execute("CREATE DATABASE IF NOT EXISTS JSFormSample CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            for host in ("localhost", "127.0.0.1"):
                cursor.execute(
                    "CREATE USER IF NOT EXISTS 'jsform_sample'@'{}' IDENTIFIED BY %s".format(host),
                    (sample_password,),
                )
                cursor.execute(
                    "ALTER USER 'jsform_sample'@'{}' IDENTIFIED BY %s".format(host),
                    (sample_password,),
                )
                cursor.execute("GRANT ALL PRIVILEGES ON JSFormSample.* TO 'jsform_sample'@'{}'".format(host))
            admin.commit()
        finally:
            cursor.close()
    finally:
        admin.close()
    connection = mysql.connector.connect(
        host=args.server, database=args.database, user=args.sample_user, password=sample_password,
    )
    try:
        cursor = connection.cursor()
        try:
            sql = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
            for statement in statements(sql):
                cursor.execute(statement)
            connection.commit()
        finally:
            cursor.close()
    finally:
        connection.close()
    print("JSFormSample install complete: {} / {} / {}".format(
        args.server, args.database, args.sample_user,
    ))


if __name__ == "__main__":
    main()
