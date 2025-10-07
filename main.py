#!/usr/bin/env python3
"""
PostgreSQL Docker Compose Upgrader CLI.

A tool for upgrading PostgreSQL versions in Docker Compose environments
with automatic backup and verification.
"""

import argparse
from rich.console import Console
import sys
from postgres_upgrader.postgres import Postgres


def create_parser() -> argparse.ArgumentParser:
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

    _ = subparsers.add_parser(
        "upgrade", help="Run complete PostgreSQL upgrade workflow"
    )

    _ = subparsers.add_parser("export", help="Create PostgreSQL backup only")

    _ = subparsers.add_parser("import", help="Import PostgreSQL data from backup")

    return parser


def main() -> None:
    """
    Main CLI entry point.

    Handles argument parsing, command routing, and top-level exception handling.
    """
    parser = create_parser()
    args = parser.parse_args()

    # If no command specified, show help
    if not args.command:
        parser.print_help()
        sys.exit(1)

    console = Console()
    postgres = Postgres(console)
    try:
        # Route to appropriate command handler
        if args.command == "upgrade":
            postgres.handle_upgrade_command(args)
        elif args.command == "export":
            postgres.handle_export_command(args)
        elif args.command == "import":
            postgres.handle_import_command(args)
        else:
            print(f"❌ Unknown command: {args.command}")
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
