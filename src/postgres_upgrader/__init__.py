"""
PostgreSQL Docker Compose upgrader package with enhanced volume validation.

This package provides tools for safely upgrading PostgreSQL databases in Docker Compose
environments with strict validation to ensure production safety. Key safety features:

- Only supports proper Docker volumes (bind mounts are rejected)
- Validates complete volume definitions and resolved names
- Performs early error detection before any Docker operations
- Ensures all volume operations are container-safe

Main components:
- compose_inspector: Configuration parsing with enhanced volume validation
- docker: Infrastructure operations and PostgreSQL database management
- prompt: Interactive user interfaces for service and volume selection
- postgres: Business logic orchestration for upgrade workflows
"""

from .compose_inspector import (
    DockerComposeConfig,
    ServiceConfig,
    VolumeMount,
    parse_docker_compose,
)
from .docker import DockerManager
from .prompt import identify_service_volumes, prompt_container_user, prompt_user_choice

__all__ = [
    "DockerComposeConfig",
    "DockerManager",
    "ServiceConfig",
    "VolumeMount",
    "identify_service_volumes",
    "parse_docker_compose",
    "prompt_container_user",
    "prompt_user_choice",
]
