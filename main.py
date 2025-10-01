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
    service_volume_config = identify_service_volumes(compose_config)

    if not service_volume_config:
        print("No volumes found or selection cancelled")
        sys.exit(1)

    print(f"Backup location: {service_volume_config.backup_volume.dir}")

    service_name = service_volume_config.name
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
        with DockerManager() as docker_mgr:
            docker_mgr.create_postgres_backup(user, database, service_volume_config)
            docker_mgr.stop_service_container(service_name)
            docker_mgr.update_service_container(service_name)
            docker_mgr.build_service_container(service_name)
            docker_mgr.remove_service_main_volume(compose_config, service_volume_config)
            docker_mgr.start_service_container(service_name)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
