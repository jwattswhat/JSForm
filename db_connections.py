"""Explicit database settings and paired JSForm connections."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseSettings:
    """Connection values that can be translated for a DB-API connector."""

    host: str
    database: str
    username: str
    password: str
    port: int | None = None

    def connector_arguments(self):
        arguments = {
            "host": self.host,
            "database": self.database,
            "user": self.username,
            "password": self.password,
        }
        if self.port is not None:
            arguments["port"] = self.port
        return arguments


class DatabaseConnections:
    """Own one application database connection.

    ``framework_settings`` remains accepted temporarily for source compatibility,
    but JSForm no longer opens or owns a separate framework database.
    """

    def __init__(self, application_settings, framework_settings, connector):
        self.application_settings = application_settings
        self.framework_settings = application_settings
        self.application = connector(**application_settings.connector_arguments())
        self.framework = self.application

    def close(self):
        try:
            self.application.close()
        except (AttributeError, RuntimeError):
            pass
