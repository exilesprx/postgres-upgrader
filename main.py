#!/usr/bin/env python3
"""
PostgreSQL Docker Compose backup location extractor.
"""

import sys
from postgres_upgrader import identify_service_volumes


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: ./main.py <docker-compose.yml>")
        sys.exit(1)

    compose_file = sys.argv[1]
    selections = identify_service_volumes(compose_file)

    if selections:
        print(f"Location: {selections}")
    else:
        print("No volumes found or selection cancelled")
        sys.exit(1)

    # TODO: pass selections to the updater tool


if __name__ == "__main__":
    main()
