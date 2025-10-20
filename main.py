#!/usr/bin/env python3
"""
PostgreSQL Docker Compose Upgrader CLI.

A tool for upgrading PostgreSQL versions in Docker Compose environments
with automatic backup and verification.
"""

import sys

from rich.console import Console

from postgres_upgrader.cli import (
    CommandDefinition,
    create_command_registry,
    create_parser,
)
from postgres_upgrader.postgres import Postgres


def get_command_definitions(postgres: Postgres) -> list[CommandDefinition]:
    """Get the list of all available command definitions."""
    return [
        CommandDefinition(
            "upgrade",
            "Run complete PostgreSQL upgrade workflow",
            postgres.handle_upgrade_command,
        ),
        CommandDefinition(
            "export", "Create PostgreSQL backup only", postgres.handle_export_command
        ),
        CommandDefinition(
            "import",
            "Import PostgreSQL data from backup",
            postgres.handle_import_command,
        ),
    ]


def main() -> None:
    """
    Main CLI entry point.

    Handles argument parsing, command routing, and top-level exception handling.
    """
    console = Console()
    postgres = Postgres(console)
    commands = get_command_definitions(postgres)
    parser = create_parser(commands)
    registry = create_command_registry(commands)
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        handler = registry.get_handler(args.command)
        handler(args)
    except ValueError:
        console.print(f"❌ Unknown command '{args.command}'", style="bold red")
        available_commands = registry.get_available_commands()
        if available_commands:
            console.print(f"Available commands: {', '.join(available_commands)}")
        parser.print_help()
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n❌ Operation cancelled by user", style="bold red")
        sys.exit(1)
    except Exception as e:
        console.print(f"❌ Error: {e}", style="bold red")
        sys.exit(1)


if __name__ == "__main__":
    main()
