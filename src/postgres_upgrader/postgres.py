"""
PostgreSQL upgrade workflow implementation.

This module contains the core business logic for PostgreSQL upgrades
using Docker Compose, separated from CLI concerns.
"""

from typing import Tuple, Optional, TYPE_CHECKING
from rich.console import Console

from . import (
    identify_service_volumes,
    DockerManager,
    parse_docker_compose,
    prompt_container_user,
)

if TYPE_CHECKING:
    from .compose_inspector import DockerComposeConfig


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


def run_postgres_upgrade() -> None:
    """
    Execute the complete PostgreSQL upgrade workflow.

    This function orchestrates the entire upgrade process:
    1. Parse Docker Compose configuration
    2. Identify and select services with volumes
    3. Get PostgreSQL credentials
    4. Prompt for container user
    5. Execute the upgrade workflow

    Raises:
        Exception: If any step in the upgrade process fails
    """
    console = Console()

    try:
        compose_config = parse_docker_compose()
    except Exception as e:
        raise Exception(
            f"Error getting Docker Compose configuration: {e}. "
            "Make sure you're in a directory with a docker-compose.yml file and Docker Compose is installed."
        )

    # Identify and select service with volumes
    selected_service = identify_service_volumes(compose_config)
    if not selected_service:
        raise Exception("No volumes found or selection cancelled")

    # Get service name
    service_name = selected_service.name
    if not service_name:
        raise Exception("Service name not found in selection")

    # Get PostgreSQL credentials from Docker Compose configuration
    user, database = get_credentials(compose_config, service_name)
    if not user or not database:
        raise Exception(
            "Could not find PostgreSQL credentials in Docker Compose configuration"
        )

    # Prompt for container user
    container_user = prompt_container_user()
    if not container_user:
        raise Exception("A valid container user is required to proceed")

    # Execute the upgrade workflow
    with DockerManager(selected_service, container_user, user, database) as docker_mgr:
        docker_mgr.perform_postgres_upgrade(console)
