from typing import List, Optional, Dict, Any
import inquirer
from .compose_inspector import extract_location, extract_name, get_services, get_volumes


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
) -> Dict[str, Any]:
    """
    Create structured volume information for a service.

    Args:
        service_name: Name of the Docker service
        main_volume: Main volume string (e.g., "database:/var/lib/postgresql/data")
        backup_volume: Backup volume string (e.g., "backups:/var/lib/postgresql/backups")
        all_volumes: List of all volumes for the service

    Returns:
        Dictionary with structured volume information
    """
    return {
        "service": {
            "name": service_name,
            "volumes": {
                "backup": {
                    "dir": extract_location(backup_volume, all_volumes),
                    "name": extract_name(backup_volume, all_volumes),
                },
                "main": {
                    "dir": extract_location(main_volume, all_volumes),
                    "name": extract_name(main_volume, all_volumes),
                },
            },
        }
    }


def identify_service_volumes(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Interactive service and volume identification with user prompts.

    Args:
        data: Parsed Docker Compose data (from parse_docker_compose)

    Returns:
        Dictionary with structured volume information, or None if cancelled
    """
    # Get available services
    services = get_services(data)
    if not services:
        print("No services found in the compose file.")
        return None

    # Let user choose service
    service = prompt_user_choice(services, "Select a service to inspect:")
    if not service:
        return None

    # Get volumes for chosen service
    volumes = get_volumes(services, service)
    if not volumes:
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
    return create_volume_info(service, main, backup, volumes)
