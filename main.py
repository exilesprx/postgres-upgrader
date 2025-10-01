#!/usr/bin/env python3
"""
PostgreSQL Docker Compose backup location extractor.
"""

import sys
import os
from typing import Tuple, Optional, TYPE_CHECKING
from postgres_upgrader import (
    identify_service_volumes,
    DockerManager,
    parse_docker_compose,
)
from postgres_upgrader.env import get_database_user, get_database_name

if TYPE_CHECKING:
    from postgres_upgrader.compose_inspector import DockerComposeConfig


def get_credentials(
    compose_data: "DockerComposeConfig", service_name: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    Get PostgreSQL credentials with .env fallback to Docker Compose.

    Returns:
        tuple: (user, database) or (None, None) if not found
    """
    try:
        user = get_database_user()
    except Exception:
        user = compose_data.get_postgres_user(service_name)

    try:
        database = get_database_name()
    except Exception:
        database = compose_data.get_postgres_db(service_name)

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
    service_volume_config = identify_service_volumes(compose)

    if not service_volume_config:
        print("No volumes found or selection cancelled")
        sys.exit(1)

    print(f"Backup location: {service_volume_config.backup_volume.dir}")

    service_name = service_volume_config.name
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
        with DockerManager() as docker_mgr:
            docker_mgr.create_postgres_backup(user, database, service_volume_config)
            docker_mgr.stop_service_container(service_name)
            docker_mgr.update_service_container(service_name)
            docker_mgr.build_service_container(service_name)
            docker_mgr.replace_service_main_volume(service_volume_config)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
