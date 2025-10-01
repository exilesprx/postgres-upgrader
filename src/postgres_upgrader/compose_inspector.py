import yaml
import subprocess
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class VolumeMount:
    """Information about a Docker volume mount."""

    name: Optional[str]  # e.g., "database"
    path: Optional[str]  # e.g., "/var/lib/postgresql/data"
    raw: str  # e.g., "database:/var/lib/postgresql/data"
    resolved_name: Optional[str] = None  # e.g., "postgres-updater_database"

    @classmethod
    def from_string(
        cls, volume_config: dict, volume_mappings: Optional[Dict[str, dict]] = None
    ) -> "VolumeMount":
        """Parse a Docker Compose config dict into a VolumeMount object."""

        if volume_config.get("type") == "volume":
            # This is a named volume with resolved names
            source = volume_config.get("source")
            target_path = volume_config.get("target", "")
            raw = f"{source}:{target_path}" if source else target_path

            # Get the resolved name from the volumes section
            resolved_name = None
            if source and volume_mappings and source in volume_mappings:
                resolved_name = volume_mappings[source].get("name", source)

            return cls(
                name=source, path=target_path, raw=raw, resolved_name=resolved_name
            )
        else:
            # Handle other volume types
            target_path = volume_config.get("target", "")
            raw = f"unknown:{target_path}"
            return cls(name=None, path=target_path, raw=raw)


@dataclass
class ServiceConfig:
    """Configuration for a Docker Compose service."""

    name: str
    environment: Dict[str, str] = field(default_factory=dict)
    volumes: List[VolumeMount] = field(default_factory=list)
    # User-selected volumes for PostgreSQL operations
    selected_main_volume: Optional[VolumeMount] = None
    selected_backup_volume: Optional[VolumeMount] = None

    def select_volumes(
        self, main_volume: VolumeMount, backup_volume: VolumeMount
    ) -> None:
        """Set the user-selected main and backup volumes."""
        self.selected_main_volume = main_volume
        self.selected_backup_volume = backup_volume

    def get_main_volume_resolved_name(self) -> Optional[str]:
        """Get the resolved name of the selected main volume."""
        return (
            self.selected_main_volume.resolved_name
            if self.selected_main_volume
            else None
        )

    def get_backup_volume_path(self) -> Optional[str]:
        """Get the path of the selected backup volume."""
        return self.selected_backup_volume.path if self.selected_backup_volume else None

    def is_configured_for_postgres_upgrade(self) -> bool:
        """Check if volumes are selected for PostgreSQL upgrade."""
        return (
            self.selected_main_volume is not None
            and self.selected_backup_volume is not None
        )


@dataclass
class DockerComposeConfig:
    """Parsed Docker Compose configuration."""

    services: Dict[str, ServiceConfig] = field(default_factory=dict)

    def get_service(self, name: str) -> Optional[ServiceConfig]:
        """Get a service by name."""
        return self.services.get(name)

    def get_volumes(self, service_name: str) -> List[VolumeMount]:
        """Get list of volume mounts for a specific service."""
        service = self.get_service(service_name)
        return service.volumes if service else []

    def get_postgres_user(self, service_name: str) -> Optional[str]:
        """Get PostgreSQL user from service environment."""
        service = self.get_service(service_name)
        return service.environment.get("POSTGRES_USER") if service else None

    def get_postgres_db(self, service_name: str) -> Optional[str]:
        """Get PostgreSQL database from service environment."""
        service = self.get_service(service_name)
        return service.environment.get("POSTGRES_DB") if service else None


def parse_docker_compose() -> DockerComposeConfig:
    """
    Parse Docker Compose configuration using 'docker compose config'.

    This approach gets the fully resolved configuration with:
    - Environment variables substituted
    - Actual volume names (with prefixes)
    - Real network names
    - All computed values

    Args:
        file_path: Ignored. Kept for API compatibility only.

    Returns:
        DockerComposeConfig with resolved values

    Raises:
        RuntimeError: If docker compose config fails or Docker Compose not available
    """
    try:
        result = subprocess.run(
            ["docker", "compose", "config"], capture_output=True, text=True, check=True
        )
        raw_data = yaml.safe_load(result.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to get docker compose config: {e.stderr}") from e
    except FileNotFoundError as e:
        raise RuntimeError(
            "Docker Compose not found. Please ensure docker compose is installed."
        ) from e

    services = {}
    raw_services = raw_data.get("services", {})
    volume_mappings = raw_data.get("volumes", {})

    for service_name, service_data in raw_services.items():
        # Parse volumes from resolved config format
        volume_mounts = []
        for volume_config in service_data.get("volumes", []):
            if isinstance(volume_config, dict):
                volume_mount = VolumeMount.from_string(
                    volume_config, volume_mappings=volume_mappings
                )
                volume_mounts.append(volume_mount)

        services[service_name] = ServiceConfig(
            name=service_name,
            environment=service_data.get("environment", {}),
            volumes=volume_mounts,
        )

    return DockerComposeConfig(services=services)
