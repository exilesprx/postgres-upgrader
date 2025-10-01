#!/usr/bin/env python3
"""
PostgreSQL Docker Compose backup location extractor.
"""

import sys
import os
from typing import Tuple, Optional, Dict, Any
from postgres_upgrader import (
    identify_service_volumes,
    create_postgres_backup,
    parse_docker_compose,
)
from postgres_upgrader.compose_inspector import get_services
from postgres_upgrader.env import get_database_user, get_database_name


def get_credentials(
    compose_data: Dict[str, Any], service_name: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    Get PostgreSQL credentials with .env fallback to Docker Compose.

    Returns:
        tuple: (user, database) or (None, None) if not found
    """
    try:
        user = get_database_user()
    except Exception:
        user = (
            get_services(compose_data)
            .get(service_name, {})
            .get("environment", {})
            .get("POSTGRES_USER")
        )

    try:
        database = get_database_name()
    except Exception:
        database = (
            get_services(compose_data)
            .get(service_name, {})
            .get("environment", {})
            .get("POSTGRES_DB")
        )

    return user, database


def main() -> None:
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: ./main.py <docker-compose.yml>")
        sys.exit(1)

    compose_file = sys.argv[1]

    # Validate input file exists
    if not os.path.exists(compose_file):
        print(f"Error: File '{compose_file}' not found")
        sys.exit(1)

    try:
        compose = parse_docker_compose(compose_file)
    except Exception as e:
        print(f"Error parsing Docker Compose file: {e}")
        sys.exit(1)
    selections = identify_service_volumes(compose)

    if not selections:
        print("No volumes found or selection cancelled")
        sys.exit(1)

    print(f"Location: {selections}")

    service_name = selections.get("service", {}).get("name")
    if not service_name:
        print("Error: Service name not found in selection")
        sys.exit(1)

    # TODO: prompt for postgres container user. Default is postgres

    # Get credentials with fallback logic
    user, database = get_credentials(compose, service_name)

    if not user or not database:
        print(
            "Error: Could not find PostgreSQL credentials in .env file or Docker Compose environment"
        )
        sys.exit(1)

    try:
        create_postgres_backup(user, database, selections)
    except Exception as e:
        print(f"Error creating backup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
