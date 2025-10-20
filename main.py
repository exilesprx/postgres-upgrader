#!/usr/bin/env python3
"""
PostgreSQL Docker Compose Upgrader CLI.

A tool for upgrading PostgreSQL versions in Docker Compose environments
with automatic backup and verification.
"""

import argparse
import sys

from rich.console import Console

from postgres_upgrader.cli import CommandDefinition, CommandRegistry
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
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    for command_def in commands:
        _ = subparsers.add_parser(command_def.name, help=command_def.help_text)

    return parser


def create_command_registry(commands: list[CommandDefinition]) -> CommandRegistry:
    """Create and populate the command registry with handlers."""
    registry = CommandRegistry()

    for command_def in commands:
        registry.register(command_def.name, command_def.handler)

    return registry


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
    except ValueError as e:
        console.print(f"❌ {e}", style="bold red")
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
