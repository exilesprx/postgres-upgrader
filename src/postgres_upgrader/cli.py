"""
CLI infrastructure for the PostgreSQL upgrader.

Contains command definitions, registry, and protocols for handling CLI commands.
"""

import argparse
from typing import NamedTuple, Protocol


class CommandHandler(Protocol):
    """Protocol for command handler functions."""

    def __call__(self, _args: argparse.Namespace) -> None: ...


class CommandDefinition(NamedTuple):
    """Definition of a CLI command."""

    name: str
    help_text: str
    handler: CommandHandler


class CommandRegistry:
    """Registry for CLI command handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, CommandHandler] = {}

    def register(self, command: str, handler: CommandHandler) -> None:
        """Register a command handler."""
        if command in self._handlers:
            raise ValueError(f"Command '{command}' is already registered")
        self._handlers[command] = handler

    def get_handler(self, command: str) -> CommandHandler:
        """Get a handler for the given command."""
        if command not in self._handlers:
            raise ValueError(f"Unknown command {command}")
        return self._handlers[command]

    def get_available_commands(self) -> list[str]:
        """Get list of available commands."""
        return sorted(self._handlers.keys())

    def is_registered(self, command: str) -> bool:
        """Check if a command is registered."""
        return command in self._handlers
