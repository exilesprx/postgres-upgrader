from typing import List, Optional, TYPE_CHECKING
from dataclasses import dataclass
import inquirer
from .compose_inspector import extract_location, extract_name

if TYPE_CHECKING:
    from .compose_inspector import DockerComposeConfig


@dataclass
class VolumeInfo:
    """Information about a Docker volume."""
    name: str
    dir: str


@dataclass
class ServiceVolumeConfig:
    """Configuration for a Docker service's volumes."""
    name: str
    main_volume: VolumeInfo
    backup_volume: VolumeInfo


def prompt_user_choice(
    choices: List[str], prompt_message: str = "Please select an option:"
) -> Optional[str]:
    """
    Prompt user to select from a list of choices using inquirer with text fallback.

    Args:
        choices: List of strings to choose from
        prompt_message: Message to display to user

    Returns:
        Selected choice string, or None if cancelled
    """
    if not choices:
        return None

    try:
        # Use inquirer for better UX
        questions = [
            inquirer.List(
                "choice",
                message=prompt_message,
                choices=choices,
            ),
        ]
        answers = inquirer.prompt(questions)
        return answers["choice"] if answers else None

    except KeyboardInterrupt:
        # User cancelled with Ctrl+C - respect their intention to quit
        print("\nCancelled by user")
        return None


def create_volume_info(
    service_name: str, main_volume: str, backup_volume: str, all_volumes: List[str]
) -> ServiceVolumeConfig:
    """
    Create structured volume information for a service.

    Args:
        service_name: Name of the Docker service
        main_volume: Main volume string (e.g., "database:/var/lib/postgresql/data")
        backup_volume: Backup volume string (e.g., "backups:/var/lib/postgresql/backups")
        all_volumes: List of all volumes for the service

    Returns:
        ServiceVolumeConfig with structured volume information
    """
    return ServiceVolumeConfig(
        name=service_name,
        main_volume=VolumeInfo(
            name=extract_name(main_volume, all_volumes),
            dir=extract_location(main_volume, all_volumes)
        ),
        backup_volume=VolumeInfo(
            name=extract_name(backup_volume, all_volumes),
            dir=extract_location(backup_volume, all_volumes)
        )
    )


def identify_service_volumes(data: "DockerComposeConfig") -> Optional[ServiceVolumeConfig]:
    """
    Interactive service and volume identification with user prompts.

    Args:
        data: Parsed Docker Compose data (from parse_docker_compose)

    Returns:
        ServiceVolumeConfig with structured volume information, or None if cancelled
    """
    # Get available services directly from data class
    if not data.services:
        print("No services found in the compose file.")
        return None

    # Let user choose service
    service_names = list(data.services.keys())
    service_name = prompt_user_choice(service_names, "Select a service to inspect:")
    if not service_name:
        return None

    # Get volumes for chosen service using the data class method
    service = data.get_service(service_name)
    if not service:
        print(f"Service '{service_name}' not found.")
        return None
        
    volumes = service.volumes
    if not volumes:
        print(f"No volumes found for service '{service_name}'.")
        return None

    # Choose the main volume
    main = prompt_user_choice(volumes, "Select the main volume:")
    if not main:
        return None

    # Create a list of remaining volumes for backup selection
    remaining_volumes = [v for v in volumes if v != main]

    # Let user choose backup volume
    backup = prompt_user_choice(remaining_volumes, "Select the backup volume:")
    if not backup:
        return None

    # Create and return structured volume information
    return create_volume_info(service_name, main, backup, volumes)
