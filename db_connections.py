"""Explicit database settings and paired JSForm connections."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DatabaseSettings:
    """Connection values that can be translated for a DB-API connector."""

    host: str
    database: str
    username: str
    password: str | None = field(repr=False)
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

    def without_password(self):
        """Return the same non-secret connection description."""
        return DatabaseSettings(
            self.host, self.database, self.username, None, self.port,
        )


class DatabaseConnections:
    """Open, retain, and close one application database connection."""

    def __init__(self, application_settings, connector):
        self.application_settings = application_settings.without_password()
        arguments = application_settings.connector_arguments()
        try:
            try:
                self.application = connector(**arguments)
            except Exception as error:
                raise RuntimeError(
                    "The database connection could not be established."
                ) from error
        finally:
            arguments["password"] = None
    def close(self):
        try:
            self.application.close()
        except (AttributeError, RuntimeError):
            pass
