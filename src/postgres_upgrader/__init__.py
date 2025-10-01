"""
PostgreSQL Docker Compose updater package.
"""

from .compose_inspector import (
    extract_location,
    extract_name,
    parse_docker_compose,
    DockerComposeConfig,
    ServiceConfig,
)
from .prompt import prompt_user_choice, identify_service_volumes, create_volume_info, ServiceVolumeConfig, VolumeInfo
from .docker import DockerManager
from .env import get_database_name, get_database_user

__all__ = [
    # Compose inspector functions
    "parse_docker_compose",
    "extract_location",
    "extract_name",
    "DockerComposeConfig",
    "ServiceConfig",
    # User interaction functions
    "prompt_user_choice",
    "identify_service_volumes",
    "create_volume_info",
    "ServiceVolumeConfig",
    "VolumeInfo",
    # Docker operations
    "DockerManager",
    # Environment functions
    "get_database_name",
    "get_database_user",
]
