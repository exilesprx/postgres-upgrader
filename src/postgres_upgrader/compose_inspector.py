import yaml
from typing import Dict, List, Optional, Any


def parse_docker_compose(file_path: str) -> Dict[str, Any]:
    """Parse a Docker Compose YAML file."""
    with open(file_path, "r") as f:
        return yaml.safe_load(f)


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


def get_services(data: Dict[str, Any]) -> Dict[str, Any]:
    """Get services dictionary from parsed Docker Compose data."""
    return data.get("services", {})


def get_volumes(services: Dict[str, Any], service_name: str) -> List[str]:
    """Get list of volumes for a specific service from services dictionary."""
    service_items = services.get(service_name, {})
    return service_items.get("volumes", [])
