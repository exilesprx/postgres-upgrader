#!/usr/bin/env python3
"""
PostgreSQL Docker Compose backup location extractor.
"""

import sys
from postgres_updater import backup_location


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: ./main.py <docker-compose.yml>")
        sys.exit(1)

    compose_file = sys.argv[1]
    location = backup_location(compose_file)

    if location:
        print(f"Backup location: {location}")
    else:
        print("No backup location found in compose file")
        sys.exit(1)


if __name__ == "__main__":
    main()
