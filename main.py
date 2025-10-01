#!/usr/bin/env python3
"""
PostgreSQL Docker Compose backup location extractor.
"""

import sys
from typing import Tuple, Optional, TYPE_CHECKING
from postgres_upgrader import (
    identify_service_volumes,
    DockerManager,
    parse_docker_compose,
)

if TYPE_CHECKING:
    from postgres_upgrader.compose_inspector import DockerComposeConfig


def get_credentials(
    compose_config: "DockerComposeConfig", service_name: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    Get PostgreSQL credentials from resolved Docker Compose configuration.

    Returns:
        tuple: (user, database) or (None, None) if not found
    """
    user = compose_config.get_postgres_user(service_name)
    database = compose_config.get_postgres_db(service_name)
    return user, database


def main() -> None:
    """Main CLI entry point."""

    try:
        compose_config = parse_docker_compose()
    except Exception as e:
        print(f"Error getting Docker Compose configuration: {e}")
        print(
            "Make sure you're in a directory with a docker-compose.yml file and Docker Compose is installed."
        )
        sys.exit(1)

    selected_service = identify_service_volumes(compose_config)

    if not selected_service:
        print("No volumes found or selection cancelled")
        sys.exit(1)

    print(f"Backup location: {selected_service.get_backup_volume_path()}")

    service_name = selected_service.name
    if not service_name:
        print("Error: Service name not found in selection")
        sys.exit(1)

    # Get credentials from resolved Docker Compose configuration
    user, database = get_credentials(compose_config, service_name)

    if not user or not database:
        print(
            "Error: Could not find PostgreSQL credentials in Docker Compose configuration"
        )
        sys.exit(1)

    try:
        with DockerManager(selected_service) as docker_mgr:
            docker_mgr.perform_postgres_upgrade(user, database)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
