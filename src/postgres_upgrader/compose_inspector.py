import subprocess
from dataclasses import dataclass, field

import yaml


@dataclass
class VolumeMount:
    """
    Information about a Docker volume mount with strict validation.

    This class ensures production safety by:
    - Only supporting proper Docker volumes (no bind mounts)
    - Requiring all fields to be non-None and properly defined
    - Validating that volumes have resolved names from Docker Compose

    Attributes:
        name: Volume source name from Docker Compose (e.g., "database")
        path: Container mount path (e.g., "/var/lib/postgresql/data")
        raw: Complete volume specification (e.g., "database:/var/lib/postgresql/data")
        resolved_name: Full Docker volume name with project prefix (e.g., "postgres-updater_database")
    """

    name: str  # e.g., "database"
    path: str  # e.g., "/var/lib/postgresql/data"
    raw: str  # e.g., "database:/var/lib/postgresql/data"
    resolved_name: str  # e.g., "postgres-updater_database"

    @classmethod
    def from_string(
        cls, volume_config: dict, volume_mappings: dict[str, dict] | None = None
    ) -> "VolumeMount":
        """
        Parse a Docker Compose config dict into a VolumeMount object.

        Enforces strict validation for production safety:
        - Only accepts volume type mounts (rejects bind mounts)
        - Requires complete volume definitions with resolved names
        - Validates that all required fields are present and non-empty

        Args:
            volume_config: Docker Compose volume configuration dict
            volume_mappings: Optional volume name mappings from Docker Compose volumes section

        Returns:
            VolumeMount: Validated volume mount object

        Raises:
            ValueError: If volume config is invalid or volume name cannot be resolved
            Exception: If non-volume mount types are attempted (bind mounts, etc.)
        """

        if volume_config.get("type") == "volume":
            source = volume_config.get("source")
            target_path = volume_config.get("target")
            if not source or not target_path:
                raise ValueError(f"Invalid volume config: {volume_config}")

            raw = f"{source}:{target_path}"

            # Get the resolved name from the volumes section
            resolved_name = None
            if volume_mappings and source in volume_mappings:
                resolved_name = volume_mappings[source].get("name", source)

            if resolved_name is None:
                raise ValueError(f"Could not resolve volume name for source: {source}")

            return cls(
                name=source, path=target_path, raw=raw, resolved_name=resolved_name
            )
        else:
            raise Exception("Non-volume mounts are not supported.")


@dataclass
class ServiceConfig:
    """Configuration for a Docker Compose service."""

    name: str
    environment: dict[str, str] = field(default_factory=dict)
    volumes: list[VolumeMount] = field(default_factory=list)
    # User-selected volumes for PostgreSQL operations
    selected_main_volume: VolumeMount | None = None
    selected_backup_volume: VolumeMount | None = None

    def select_volumes(
        self, main_volume: VolumeMount, backup_volume: VolumeMount
    ) -> None:
        """Set the user-selected main and backup volumes."""
        self.selected_main_volume = main_volume
        self.selected_backup_volume = backup_volume

    def get_main_volume_resolved_name(self) -> str | None:
        """Get the resolved name of the selected main volume."""
        return (
            self.selected_main_volume.resolved_name
            if self.selected_main_volume
            else None
        )

    def get_main_volume(self) -> VolumeMount | None:
        """Get the selected main volume."""
        return self.selected_main_volume

    def get_backup_volume(self) -> VolumeMount | None:
        """Get the selected backup volume."""
        return self.selected_backup_volume

    def is_configured_for_postgres_upgrade(self) -> bool:
        """
        Check if volumes are selected and valid for PostgreSQL upgrade operations.

        Validates that:
        - Both main and backup volumes are selected
        - Backup volume is not the same as the main volume
        - Backup volume path is not nested inside the main volume path

        Returns:
            bool: True if configuration is valid for upgrade, False otherwise
        """
        # Check if both volumes are selected
        if not self.selected_main_volume or not self.selected_backup_volume:
            return False

        # Check for same volume
        if self.selected_main_volume.name == self.selected_backup_volume.name:
            return False

        # Check for nested paths
        main_path = self.selected_main_volume.path or ""
        backup_path = self.selected_backup_volume.path or ""

        main_path = main_path.rstrip("/")
        backup_path = backup_path.rstrip("/")

        # Docker standard PostgreSQL data directory check
        if backup_path == "/var/lib/postgresql/data":
            raise Exception(
                "You cannot use the default PostgreSQL data directory as a backup location. It will remove all existing data!"
            )

        if backup_path.startswith(main_path + "/") or backup_path == main_path:
            return False

        return True


@dataclass
class DockerComposeConfig:
    """Parsed Docker Compose configuration."""

    name: str | None
    services: dict[str, ServiceConfig] = field(default_factory=dict)

    def get_service(self, name: str) -> ServiceConfig | None:
        """Get a service by name."""
        return self.services.get(name)

    def get_volumes(self, service_name: str) -> list[VolumeMount]:
        """Get list of volume mounts for a specific service."""
        service = self.get_service(service_name)
        return service.volumes if service else []

    def get_postgres_user(self, service_name: str) -> str | None:
        """Get PostgreSQL user from service environment."""
        service = self.get_service(service_name)
        return service.environment.get("POSTGRES_USER") if service else None

    def get_postgres_db(self, service_name: str) -> str | None:
        """Get PostgreSQL database from service environment."""
        service = self.get_service(service_name)
        return service.environment.get("POSTGRES_DB") if service else None


def parse_docker_compose() -> DockerComposeConfig:
    """
    Parse Docker Compose configuration using 'docker compose config' with enhanced validation.

    This approach gets the fully resolved configuration with:
    - Environment variables substituted
    - Actual volume names (with prefixes)
    - Real network names
    - All computed values
    - Strict volume validation (only Docker volumes, no bind mounts)

    The parser enforces production safety by rejecting:
    - Bind mounts and other non-volume mount types
    - Volumes without proper definitions in the volumes section
    - Incomplete volume configurations

    Args:
        file_path: Ignored. Kept for API compatibility only.

    Returns:
        DockerComposeConfig with resolved and validated values

    Raises:
        RuntimeError: If docker compose config fails or Docker Compose not available
        ValueError: If volume configurations are invalid or missing definitions
        Exception: If non-volume mount types are found in the configuration
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

    if raw_data is None:
        return DockerComposeConfig(name=None, services={})

    services = {}
    project_name = raw_data.get("name")
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

    return DockerComposeConfig(name=project_name, services=services)
