"""Explicit migration of legacy SMTP passwords to a protected credential store."""

from __future__ import annotations

from dataclasses import dataclass


class SMTPCredentialMigrationError(RuntimeError):
    """Raised when legacy SMTP credential migration cannot finish safely."""


@dataclass(frozen=True)
class SMTPCredentialMigrationResult:
    """Non-secret result of one explicit legacy SMTP migration attempt."""

    migrated: bool
    legacy_password_removed: bool


def _marker(connection):
    module = connection.__class__.__module__
    return "%s" if module.startswith(("mysql.connector", "mariadb")) else "?"


def _credential(store, target):
    try:
        value = store.read(target)
    except KeyError:
        return None
    except Exception:
        raise SMTPCredentialMigrationError(
            "The protected SMTP credential could not be inspected."
        ) from None
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise SMTPCredentialMigrationError(
            "The protected SMTP credential has an invalid format."
        )
    username, secret = str(value[0] or ""), str(value[1] or "")
    if not username.strip() or not secret:
        raise SMTPCredentialMigrationError(
            "The protected SMTP credential is incomplete."
        )
    return username, secret


def migrate_legacy_smtp_credential(connection, credential_store, target):
    """Move application `SMTP/Password` to ``target`` without committing.

    Only the application ``tblConfig`` table is read. The password row is
    deleted after exact protected-store readback. The caller owns commit or
    rollback because the database and Windows vault are separate stores.
    """
    selected_target = str(target or "").strip()
    if not selected_target:
        raise SMTPCredentialMigrationError("A protected SMTP credential target is required.")
    marker = _marker(connection)
    placeholders = ",".join((marker, marker, marker))
    cursor = connection.cursor()
    created_credential = False
    original_error = None
    try:
        cursor.execute(
            "SELECT ConfigType,ConfigValue FROM tblConfig "
            f"WHERE ConfigFamily={marker} AND ConfigType IN ({placeholders}) FOR UPDATE",
            ("SMTP", "UserName", "Password", "CredentialTarget"),
        )
        rows = cursor.fetchall()
        values = {}
        for config_type, config_value in rows:
            values.setdefault(str(config_type), []).append(config_value)
        for key in ("UserName", "Password", "CredentialTarget"):
            if len(values.get(key, ())) > 1:
                raise SMTPCredentialMigrationError(
                    "Legacy SMTP configuration is ambiguous and was not changed."
                )
        configured_target = str((values.get("CredentialTarget") or [""])[0] or "").strip()
        if configured_target and configured_target != selected_target:
            raise SMTPCredentialMigrationError(
                "A different protected SMTP credential target is already configured."
            )
        password_rows = values.get("Password", ())
        if not password_rows:
            if configured_target == selected_target:
                return SMTPCredentialMigrationResult(False, False)
            raise SMTPCredentialMigrationError("No legacy SMTP password is available to migrate.")
        username = str((values.get("UserName") or [""])[0] or "")
        password = str(password_rows[0] or "")
        if not username.strip() or not password:
            raise SMTPCredentialMigrationError(
                "The legacy SMTP username and password must both be present."
            )

        existing = _credential(credential_store, selected_target)
        if existing is None:
            try:
                credential_store.write(selected_target, username, password)
            except Exception:
                raise SMTPCredentialMigrationError(
                    "The protected SMTP credential could not be stored."
                ) from None
            created_credential = True
        elif existing != (username, password):
            raise SMTPCredentialMigrationError(
                "The protected SMTP credential target already contains different credentials."
            )
        if _credential(credential_store, selected_target) != (username, password):
            raise SMTPCredentialMigrationError(
                "The protected SMTP credential could not be verified."
            )

        if not configured_target:
            cursor.execute(
                "INSERT INTO tblConfig (ConfigFamily,ConfigType,ConfigValue) "
                f"VALUES ({marker},{marker},{marker})",
                ("SMTP", "CredentialTarget", selected_target),
            )
        cursor.execute(
            f"DELETE FROM tblConfig WHERE ConfigFamily={marker} AND ConfigType={marker}",
            ("SMTP", "Password"),
        )
        if cursor.rowcount != 1:
            raise SMTPCredentialMigrationError(
                "The legacy SMTP password changed before migration completed."
            )
        return SMTPCredentialMigrationResult(True, True)
    except Exception as error:
        original_error = error
        if created_credential:
            try:
                credential_store.delete(selected_target)
            except Exception:
                pass
        if isinstance(error, SMTPCredentialMigrationError):
            raise
        raise SMTPCredentialMigrationError(
            "Legacy SMTP credential migration failed without changing the database."
        ) from error
    finally:
        try:
            cursor.close()
        except Exception:
            if original_error is None:
                if created_credential:
                    try:
                        credential_store.delete(selected_target)
                    except Exception:
                        pass
                raise SMTPCredentialMigrationError(
                    "Legacy SMTP credential migration could not finish safely."
                ) from None
