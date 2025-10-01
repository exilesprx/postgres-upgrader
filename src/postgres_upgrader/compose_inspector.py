import yaml
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class VolumeMount:
    """Information about a Docker volume mount."""
    name: Optional[str]  # e.g., "database"
    path: Optional[str]  # e.g., "/var/lib/postgresql/data"
    raw: str   # e.g., "database:/var/lib/postgresql/data"
    
    @classmethod
    def from_string(cls, volume_string: str) -> "VolumeMount":
        """Parse a Docker Compose volume string into a VolumeMount object."""
        if ":" in volume_string:
            parts = volume_string.split(":", 1)  # Split on first colon only
            return cls(name=parts[0], path=parts[1], raw=volume_string)
        else:
            # Invalid format or named volume without host path
            return cls(name=None, path=None, raw=volume_string)


@dataclass
class ServiceConfig:
    """Configuration for a Docker Compose service."""
    name: str
    environment: Dict[str, str] = field(default_factory=dict)
    volumes: List[VolumeMount] = field(default_factory=list)
    # Add other service properties as needed


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


def parse_docker_compose(file_path: str) -> DockerComposeConfig:
    """Parse a Docker Compose YAML file into structured data."""
    with open(file_path, "r") as f:
        raw_data = yaml.safe_load(f)

    services = {}
    raw_services = raw_data.get("services", {})

    for service_name, service_data in raw_services.items():
        # Parse volumes into structured data at parse time
        volume_mounts = []
        for volume_string in service_data.get("volumes", []):
            volume_mounts.append(VolumeMount.from_string(volume_string))
        
        services[service_name] = ServiceConfig(
            name=service_name,
            environment=service_data.get("environment", {}),
            volumes=volume_mounts,
        )

    return DockerComposeConfig(services=services)
