import yaml
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ServiceConfig:
    """Configuration for a Docker Compose service."""

    name: str
    environment: Dict[str, str] = field(default_factory=dict)
    volumes: List[str] = field(default_factory=list)
    # Add other service properties as needed


@dataclass
class DockerComposeConfig:
    """Parsed Docker Compose configuration."""

    services: Dict[str, ServiceConfig] = field(default_factory=dict)

    def get_service(self, name: str) -> Optional[ServiceConfig]:
        """Get a service by name."""
        return self.services.get(name)

    def get_volumes(self, service_name: str) -> List[str]:
        """Get list of volumes for a specific service."""
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
        services[service_name] = ServiceConfig(
            name=service_name,
            environment=service_data.get("environment", {}),
            volumes=service_data.get("volumes", []),
        )

    return DockerComposeConfig(services=services)


def extract_location(want: str, volumes: List[str]) -> Optional[str]:
    """Extract the host path for a given volume name."""
    for volume in volumes:
        if want in volume:
            return volume.split(":")[1]
    return None


def extract_name(want: str, volumes: List[str]) -> Optional[str]:
    """Extract the volume name for a given volume string."""
    for volume in volumes:
        if want in volume:
            return volume.split(":")[0]
    return None
