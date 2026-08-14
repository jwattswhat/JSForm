"""Create the isolated database/account and reset fictional sample tables."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

import mariadb
import mysql.connector

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PACKAGE_ROOT.parent))

from JSForm.windows_credentials import read_credential, write_credential


SAMPLE_CREDENTIAL_TARGET = "JSFormSample/Database"


def statements(text):
    return [part.strip() for part in text.split(";") if part.strip()]


def main():
    parser = argparse.ArgumentParser(description="Install the isolated JSForm School Bus Sample")
    parser.add_argument("--server", default="localhost")
    parser.add_argument("--admin-user", default="root")
    parser.add_argument("--database", default="JSFormSample")
    parser.add_argument("--sample-user", default="jsform_sample")
    parser.add_argument(
        "--admin-credential-target",
        help="read the MariaDB administrator login from a named Windows credential",
    )
    parser.add_argument(
        "--password-only", action="store_true",
        help="reset only the sample database login password; preserve all data",
    )
    parser.add_argument(
        "--store-sample-credential", action="store_true",
        help="securely store the applied sample login in Windows Credential Manager",
    )
    args = parser.parse_args()
    if args.database != "JSFormSample" or args.sample_user != "jsform_sample":
        raise SystemExit("The sample installer uses the fixed isolated database and account names.")
    if args.admin_credential_target:
        stored_user, admin_password = read_credential(args.admin_credential_target)
        if stored_user != args.admin_user:
            raise SystemExit("The stored administrative username does not match --admin-user.")
    else:
        admin_password = getpass.getpass("MariaDB administrative password for {}: ".format(args.admin_user))
    try:
        admin = mariadb.connect(
            host=args.server, user=args.admin_user, password=admin_password,
        )
    except mariadb.Error as error:
        if getattr(error, "errno", None) == 1045:
            raise SystemExit(
                "The MariaDB administrative password was not accepted. "
                "No sample password or data was changed."
            ) from None
        raise
    sample_password = getpass.getpass("Choose a password for jsform_sample: ")
    confirmation = getpass.getpass("Confirm the jsform_sample password: ")
    if not sample_password or sample_password != confirmation:
        admin.close()
        raise SystemExit("The sample passwords did not match.")
    try:
        cursor = admin.cursor()
        try:
            cursor.execute("CREATE DATABASE IF NOT EXISTS JSFormSample CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            for host in ("localhost", "127.0.0.1"):
                cursor.execute(
                    "CREATE USER IF NOT EXISTS 'jsform_sample'@'{}' IDENTIFIED BY ?".format(host),
                    (sample_password,),
                )
                cursor.execute(
                    "ALTER USER 'jsform_sample'@'{}' IDENTIFIED BY ?".format(host),
                    (sample_password,),
                )
                cursor.execute("GRANT ALL PRIVILEGES ON JSFormSample.* TO 'jsform_sample'@'{}'".format(host))
            admin.commit()
        finally:
            cursor.close()
    finally:
        admin.close()
    if args.store_sample_credential:
        write_credential(SAMPLE_CREDENTIAL_TARGET, args.sample_user, sample_password)
    if args.password_only:
        print("JSFormSample password reset complete. Sample data was not changed.")
        if args.store_sample_credential:
            print("The sample login was stored securely in Windows Credential Manager.")
        return
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
