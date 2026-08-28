"""Application-neutral commands shared by menus and other UI presentations."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import re
from types import MappingProxyType
from typing import Any, Callable, Mapping

try:  # Support both installed-package and repository-level pure test imports.
    from .security import AuthorizationDenied
except ImportError:  # pragma: no cover - exercised by repository test imports
    from security import AuthorizationDenied


COMMAND_NAME = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


def _default_error_reporter(error, **context):
    try:
        from .error_reporting import report_exception
    except ImportError:  # pragma: no cover - repository-level fallback
        from error_reporting import report_exception
    return report_exception(error, **context)


@dataclass(frozen=True)
class CommandState:
    """Current presentation state for one application command."""

    enabled: bool = True
    visible: bool = True
    checked: bool = False

    def __post_init__(self):
        for name in ("enabled", "visible", "checked"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError("{} must be a boolean".format(name))


@dataclass(frozen=True)
class CommandContext:
    """Controlled runtime references supplied to command handlers and state."""

    frame: Any = None
    current_form: Any = None
    command_name: str = ""
    source: str = "application"
    event: Any = None
    authorization_policy: Any = None
    services: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.command_name and not COMMAND_NAME.fullmatch(self.command_name):
            raise ValueError("Invalid command name: {}".format(self.command_name))
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("Command source must be a nonempty string")
        if not isinstance(self.services, Mapping):
            raise TypeError("services must be a mapping")
        object.__setattr__(self, "services", MappingProxyType(dict(self.services)))

    def for_command(self, command_name, *, event=None, source=None):
        """Return a context specialized for one invocation or state request."""
        return replace(
            self,
            command_name=command_name,
            event=event,
            source=self.source if source is None else source,
        )


@dataclass(frozen=True)
class ApplicationCommand:
    """Describe one registered operation independently of its presentation."""

    name: str
    label: str
    handler: Callable[[CommandContext], Any]
    help_text: str = ""
    wx_id: int | None = None
    permission: str | None = None
    state_provider: Callable[[CommandContext], CommandState] | None = None
    destructive: bool = False

    def __post_init__(self):
        if not isinstance(self.name, str) or not COMMAND_NAME.fullmatch(self.name):
            raise ValueError("Invalid command name: {}".format(self.name))
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("Command label must be a nonempty string")
        if len(self.label) > 100:
            raise ValueError("Command label cannot exceed 100 characters")
        if not callable(self.handler):
            raise TypeError("Command handler must be callable")
        if not isinstance(self.help_text, str) or len(self.help_text) > 500:
            raise ValueError("Command help text must be a string of at most 500 characters")
        if self.wx_id is not None and (
            not isinstance(self.wx_id, int) or isinstance(self.wx_id, bool)
        ):
            raise TypeError("wx_id must be an integer or None")
        if self.permission is not None and (
            not isinstance(self.permission, str)
            or not COMMAND_NAME.fullmatch(self.permission)
        ):
            raise ValueError("Invalid command permission: {}".format(self.permission))
        if self.state_provider is not None and not callable(self.state_provider):
            raise TypeError("Command state_provider must be callable or None")
        if not isinstance(self.destructive, bool):
            raise TypeError("destructive must be a boolean")


class CommandRegistry:
    """Register, evaluate, and dispatch application commands by stable name."""

    def __init__(self, *, error_reporter=None):
        self._commands = {}
        self._wx_ids = {}
        self._error_reporter = error_reporter or _default_error_reporter

    def __len__(self):
        return len(self._commands)

    def __contains__(self, name):
        return name in self._commands

    @property
    def names(self):
        """Return registered names in deterministic insertion order."""
        return tuple(self._commands)

    def register(self, command):
        """Register one unique command and return it for convenient composition."""
        if not isinstance(command, ApplicationCommand):
            raise TypeError("command must be an ApplicationCommand")
        if command.name in self._commands:
            raise ValueError("Command is already registered: {}".format(command.name))
        if command.wx_id is not None and command.wx_id in self._wx_ids:
            raise ValueError(
                "wx_id {} is already registered by {}".format(
                    command.wx_id, self._wx_ids[command.wx_id]
                )
            )
        self._commands[command.name] = command
        if command.wx_id is not None:
            self._wx_ids[command.wx_id] = command.name
        return command

    def register_many(self, commands):
        """Register commands transactionally; no partial batch is retained."""
        commands = tuple(commands)
        pending_names = set()
        pending_ids = set()
        for command in commands:
            if not isinstance(command, ApplicationCommand):
                raise TypeError("command must be an ApplicationCommand")
            if command.name in self._commands or command.name in pending_names:
                raise ValueError("Command is already registered: {}".format(command.name))
            if command.wx_id is not None and (
                command.wx_id in self._wx_ids or command.wx_id in pending_ids
            ):
                raise ValueError("wx_id is already registered: {}".format(command.wx_id))
            pending_names.add(command.name)
            if command.wx_id is not None:
                pending_ids.add(command.wx_id)
        for command in commands:
            self.register(command)
        return commands

    def get(self, name):
        """Return a registered command or fail with its stable missing name."""
        try:
            return self._commands[name]
        except KeyError as error:
            raise KeyError("Command is not registered: {}".format(name)) from error

    def get_by_wx_id(self, wx_id):
        """Resolve a command that supplied an explicit standard wx identifier."""
        try:
            return self.get(self._wx_ids[wx_id])
        except KeyError as error:
            raise KeyError("wx_id is not registered: {}".format(wx_id)) from error

    def state(self, name, context=None):
        """Return current state, disabling and reporting failed evaluations."""
        command = self.get(name)
        context = self._context(context, name)
        try:
            state = (
                command.state_provider(context)
                if command.state_provider is not None
                else CommandState()
            )
            if not isinstance(state, CommandState):
                raise TypeError("state_provider must return CommandState")
            authorized = self._authorized(command, context)
        except Exception as error:
            self._report(error, command, context, "command.state")
            return CommandState(enabled=False)
        if not authorized:
            return replace(state, enabled=False)
        return state

    def dispatch(self, name, context=None, *, event=None, source=None):
        """Authorize and invoke a command through its single registered handler."""
        command = self.get(name)
        context = self._context(context, name, event=event, source=source)
        state = self.state(name, context)
        try:
            authorized = self._authorized(command, context)
        except Exception as error:
            self._report(error, command, context, "command.authorization")
            raise AuthorizationDenied(
                "Access denied for command {}.".format(name)
            ) from error
        if not authorized:
            raise AuthorizationDenied("Access denied for command {}.".format(name))
        if not state.visible or not state.enabled:
            raise AuthorizationDenied("Command is not currently available: {}.".format(name))
        try:
            return command.handler(context)
        except AuthorizationDenied:
            raise
        except Exception as error:
            self._report(error, command, context, "command.dispatch")
            raise

    @staticmethod
    def _context(context, name, *, event=None, source=None):
        if context is None:
            context = CommandContext()
        if not isinstance(context, CommandContext):
            raise TypeError("context must be a CommandContext or None")
        return context.for_command(name, event=event, source=source)

    @staticmethod
    def _authorized(command, context):
        if command.permission is None:
            return True
        policy = context.authorization_policy
        if policy is None or not callable(getattr(policy, "has_permission", None)):
            return False
        return bool(policy.has_permission(command.permission))

    def _report(self, error, command, context, operation):
        try:
            self._error_reporter(
                error,
                operation=operation,
                command_name=command.name,
                command_source=context.source,
            )
        except Exception:
            # Error reporting is a secondary boundary and may not break command
            # state evaluation or replace the original handler exception.
            return None
        return None
