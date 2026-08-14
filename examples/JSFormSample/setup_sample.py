"""Reset only the fictional JSForm School Bus Sample tables."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

import mysql.connector


def statements(text):
    return [part.strip() for part in text.split(";") if part.strip()]


def main():
    parser = argparse.ArgumentParser(description="Reset JSForm School Bus Sample data")
    parser.add_argument("--server", default="127.0.0.1")
    parser.add_argument("--database", default="JSFormTest")
    parser.add_argument("--user", default="church")
    args = parser.parse_args()
    password = getpass.getpass("MariaDB password for {}: ".format(args.user))
    connection = mysql.connector.connect(
        host=args.server, database=args.database, user=args.user, password=password,
    )
    try:
        cursor = connection.cursor()
        try:
            sql = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
            for statement in statements(sql): cursor.execute(statement)
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally:
            cursor.close()
    finally:
        connection.close()
    print("JSFormSample reset complete: {} / {}".format(args.server, args.database))


if __name__ == "__main__":
    main()
