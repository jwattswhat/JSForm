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
    """Own the application and framework database connections as one unit."""

    def __init__(self, application_settings, framework_settings, connector):
        self.application_settings = application_settings
        self.framework_settings = framework_settings
        self.application = connector(**application_settings.connector_arguments())
        try:
            self.framework = connector(**framework_settings.connector_arguments())
        except Exception:
            self.application.close()
            raise

    def close(self):
        for connection in (self.framework, self.application):
            try:
                connection.close()
            except (AttributeError, RuntimeError):
                continue
