#!/usr/bin/env python3
"""
PostgreSQL Docker Compose Upgrader CLI.

This is a convenience wrapper for running the package directly from the project root.
For installed packages, use the postgres-upgrader command instead.
"""

from postgres_upgrader.__main__ import main

if __name__ == "__main__":
    main()
