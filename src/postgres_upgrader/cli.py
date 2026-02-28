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


def create_parser(commands: list[CommandDefinition]) -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        prog="postgres-upgrader",
        description="PostgreSQL Docker Compose Upgrader - Manage PostgreSQL upgrades, backups, and imports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s upgrade                    # Run full PostgreSQL upgrade workflow
  %(prog)s export                     # Create backup only
  %(prog)s import                     # Import from existing backup
  %(prog)s upgrade --no-copy          # Upgrade without copying backup to host
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    for command_def in commands:
        subparser = subparsers.add_parser(command_def.name, help=command_def.help_text)

        # Add --no-copy flag to upgrade and export commands
        if command_def.name in ("upgrade", "export"):
            subparser.add_argument(
                "--no-copy",
                action="store_true",
                help="Do not copy backup file to host filesystem (backup remains in Docker volume)",
            )

    return parser


def create_command_registry(commands: list[CommandDefinition]) -> CommandRegistry:
    """Create and populate the command registry with handlers."""
    registry = CommandRegistry()

    for command_def in commands:
        registry.register(command_def.name, command_def.handler)

    return registry
