#!/usr/bin/env python3
"""
PostgreSQL Docker Compose Upgrader CLI.

A tool for upgrading PostgreSQL versions in Docker Compose environments
with automatic backup and verification.
"""

import sys
from postgres_upgrader.postgres import run_postgres_upgrade


def main() -> None:
    """
    Main CLI entry point.

    Handles top-level exception handling, user interruption,
    and exit codes while delegating business logic to other modules.
    """
    try:
        run_postgres_upgrade()
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
