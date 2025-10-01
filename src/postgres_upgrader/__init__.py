"""
PostgreSQL Docker Compose updater package.
"""

from .compose_inspector import (
    get_services,
    get_volumes,
    extract_location,
    extract_name,
    parse_docker_compose,
)
from .prompt import prompt_user_choice, identify_service_volumes, create_volume_info
from .docker import DockerManager
from .env import get_database_name, get_database_user

__all__ = [
    # Compose inspector functions
    "parse_docker_compose",
    "get_services",
    "get_volumes",
    "extract_location",
    "extract_name",
    # User interaction functions
    "prompt_user_choice",
    "identify_service_volumes",
    "create_volume_info",
    # Docker operations
    "DockerManager",
    # Environment functions
    "get_database_name",
    "get_database_user",
]
