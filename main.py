#!/usr/bin/env python3
"""
PostgreSQL Docker Compose backup location extractor.
"""

import sys
from postgres_updater import identity_volumes


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: ./main.py <docker-compose.yml>")
        sys.exit(1)

    compose_file = sys.argv[1]
    selections = identity_volumes(compose_file)

    if selections:
        print(f"Location: {selections}")
    else:
        print("No volumes found or selection cancelled")
        sys.exit(1)

    # TODO: pass selections to the updater tool


if __name__ == "__main__":
    main()
