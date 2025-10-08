# PostgreSQL Upgrader

A specialized tool for managing PostgreSQL upgrades in Docker Compose environments. This tool uses Docker Compose's own resolution engine to analyze your project configuration and help you identify and select services and their associated volumes for PostgreSQL upgrade operations.

## Features

- 🔍 **Smart Configuration Parsing**: Uses `docker compose config` for accurate, resolved configuration analysis
- 🎯 **Upgrade-Focused**: Specifically designed for PostgreSQL upgrade workflows with dedicated commands
- 🖥️ **No File Path Dependencies**: Works from any Docker Compose project directory
- 📝 **Intuitive Interface**: Interactive prompts with arrow-key navigation
- 🚀 **Automated Workflow**: Single command performs complete upgrade sequence
- 🛡️ **Data Verification**: Pre-backup validation, post-upgrade verification for complete workflows, and import statistics for standalone imports
- 🔧 **Volume Verification**: Two-tier backup volume mounting verification with lightweight Docker API reconnection and container restart fallback
- 🛡️ **Enhanced Volume Validation**: Strict validation ensures only proper Docker volumes are used, rejecting bind mounts and requiring complete volume definitions for production safety
- ⚡ **Flexible Commands**: Separate commands for export, import, and full upgrade workflows
- 🏗️ **Clean Architecture**: Separation of CLI concerns from business logic for better maintainability and testability
- 🔄 **Automated Backup Creation**: With integrity verification before upgrades
- 🐳 **Docker Image Management**: For new PostgreSQL versions (pull and build)
- ⚡ **Service Orchestration**: Complete stop/start PostgreSQL container lifecycle
- 📥 **Backup Import and Restoration**: With comprehensive verification for upgrades and statistics display for imports
- 📊 **Database Statistics Collection**: For upgrade verification and import monitoring
- 🎨 **Rich Terminal Output**: With colored progress indicators and status messages
- ✅ **Well-Tested**: Comprehensive test suite covering error handling, edge cases, integration scenarios, and volume verification

## Installation

### With uv (recommended)

```bash
git clone https://github.com/exilesprx/postgres-upgrader
cd postgres-upgrader
uv sync
```

### With pip

```bash
git clone https://github.com/exilesprx/postgres-upgrader
cd postgres-upgrader
pip install -e .
```

### With poetry

```bash
git clone https://github.com/exilesprx/postgres-upgrader
cd postgres-upgrader
poetry install
```

## Usage

### Prerequisites

The tool requires:

1. **Docker Compose**: Must be installed and accessible via `docker compose config`
2. **Docker Compose Project**: Run the tool from a directory containing a `docker-compose.yml` file
3. **PostgreSQL Credentials**: Can be provided via:
   - **`.env` file** (recommended):
     ```bash
     POSTGRES_USER=your_postgres_user
     POSTGRES_DB=your_database_name
     ```
   - **Docker Compose environment variables**: The tool automatically reads resolved credentials from your Docker Compose configuration

### Command Line Tool

The tool provides three main commands for different workflow needs:

#### Full PostgreSQL Upgrade Workflow

```bash
# Navigate to your Docker Compose project directory
cd /path/to/your/docker-compose-project

# Run complete upgrade workflow
uv run main.py upgrade

# Or after installation with pip/poetry
python -m postgres_upgrader upgrade
```

#### Export Database Backup Only

```bash
# Create backup without performing upgrade
uv run main.py export

# Or after installation
python -m postgres_upgrader export
```

#### Import from Existing Backup

```bash
# Import data from existing backup
uv run main.py import

# Or after installation
python -m postgres_upgrader import
```

#### Help and Available Commands

```bash
# Show all available commands
uv run main.py --help

# Show help for specific command
uv run main.py upgrade --help
```

### Workflow Details

Each command follows these patterns:

**Export Command:**

1. Analyze Docker Compose configuration
2. Prompt for service and volume selection
3. Collect baseline database statistics
4. Create backup and verify integrity
5. Display backup statistics and location

**Import Command:**

1. Analyze Docker Compose configuration
2. Prompt for service and volume selection
3. Start PostgreSQL service container
4. Verify backup file integrity
5. Verify backup volume mounting
6. Import data from backup
7. Update collation version
8. Display import statistics

**Upgrade Command (Complete Workflow):**

1. Analyze Docker Compose configuration
2. Prompt for service and volume selection
3. Collect baseline database statistics
4. Create backup and verify integrity
5. Stop and remove PostgreSQL service container
6. Update image and rebuild service container
7. Remove old data volume
8. Start service with new PostgreSQL version
9. Verify backup volume mounting
10. Import data and verify upgrade restoration success
11. Update collation version

### Example Interactive Output

```
[?] Select a service to inspect::
   nginx
 > postgres

[?] Select the main volume::
 > database:/var/lib/postgresql/data
   backups:/tmp/postgresql/backups

📊 Collecting database statistics...
   Current database: 5 tables, 25 MB
💾 Creating backup...
Backup created successfully: /tmp/postgresql/backups/backup-20251001_165130.sql
🔍 Verifying backup integrity...
   Backup verified: 12345 bytes, ~5 tables

# Import command output:
   Import statistics:
      Tables imported: 5
      Estimated rows: 1000
      Database size: 25 MB

# Upgrade command output:
✅ Upgrade verification successful:
      Tables: 5 (original: 5)
      Estimated rows: 1000
      Database size: 25 MB
🎉 PostgreSQL upgrade completed successfully!
```

## How It Works

This tool uses **Docker Compose's own configuration resolution** via the `docker compose config` command to get the exact same configuration that Docker Compose would use, including:

- **Environment Variables**: Automatically resolves all variable substitutions
- **Volume Prefixes**: Gets actual volume names with project prefixes (e.g., `postgres-upgrader_database`)
- **Network Resolution**: Handles complex networking configurations
- **Real-time Configuration**: Always reflects current project state
- **Error Prevention**: Eliminates manual parsing inconsistencies

### Architecture

The project follows a clean architecture with separation of concerns:

- **Separation of Concerns**: CLI logic separated from business logic through dedicated `Postgres` orchestration class
- **Context Manager**: Automatic Docker client lifecycle management with proper resource cleanup
- **Instance Variables**: Methods use stored credentials rather than requiring parameters, reducing errors and improving consistency
- **Command-Based Interface**: Dedicated commands for export, import, and upgrade workflows allowing flexible usage patterns

#### Component Responsibilities

- **`main.py`**: CLI entry point handling argument parsing and command routing
- **`postgres.py`**: Business logic orchestration class managing upgrade workflows
- **`docker.py`**: Docker infrastructure operations and PostgreSQL database interactions
- **`compose_inspector.py`**: Docker Compose configuration parsing and resolution with enhanced volume validation
- **`prompt.py`**: User interaction and service/volume selection interfaces

#### Volume Validation and Safety

The tool implements strict volume validation to ensure production safety:

- **Volume Type Enforcement**: Only Docker volumes are supported; bind mounts are rejected to prevent accidental host filesystem access
- **Complete Volume Definitions**: All volume configurations must have resolved names and proper definitions in the Docker Compose volumes section
- **Early Error Detection**: Configuration validation happens before any Docker operations begin, providing clear error messages for misconfigurations
- **Production-Safe Defaults**: The validation ensures all volume operations are container-safe and don't accidentally access host directories

### As a Library

#### Basic Configuration Analysis

```python
# Analyze Docker Compose configuration
from postgres_upgrader import parse_docker_compose

# Parse Docker Compose configuration
compose_data = parse_docker_compose()

# Get services and volumes
services = compose_data.services
print("Available services:", list(services.keys()))

volumes = compose_data.get_volumes("postgres")
print("Postgres volumes:", [v.raw for v in volumes])

# Access volume information
backup_volume = next((v for v in volumes if v.name == "backups"), None)
data_volume = next((v for v in volumes if v.name == "database"), None)

if backup_volume:
    print(f"Backup volume path: {backup_volume.path}")
    print(f"Resolved volume name: {backup_volume.resolved_name}")  # e.g., "postgres-upgrader_backups"
if data_volume:
    print(f"Data volume path: {data_volume.path}")
    print(f"Resolved volume name: {data_volume.resolved_name}")  # e.g., "postgres-upgrader_database"
```

#### Interactive Volume Selection

```python
from postgres_upgrader import parse_docker_compose, identify_service_volumes

compose_data = parse_docker_compose()
volume_config = identify_service_volumes(compose_data)

if volume_config:
    service_name = volume_config.name
    if volume_config.selected_backup_volume:
        backup_path = volume_config.selected_backup_volume.path
        print(f"Selected service: {service_name}")
        print(f"Backup directory: {backup_path}")
```

#### Using the Postgres Orchestration Class

```python
# Use the new Postgres orchestration class for programmatic workflows
from postgres_upgrader.postgres import Postgres
from rich.console import Console

console = Console()
postgres = Postgres(console)

# Run individual workflows
try:
    # Create backup only
    postgres.handle_export_command(args=None)

    # Import from backup
    postgres.handle_import_command(args=None)

    # Complete upgrade workflow
    postgres.handle_upgrade_command(args=None)

except Exception as e:
    console.print(f"❌ Error: {e}", style="bold red")
```

#### Direct Docker Operations

```python
# Direct backup workflow using DockerManager
from postgres_upgrader import (
    parse_docker_compose,
    identify_service_volumes,
    DockerManager,
    prompt_container_user,
)

compose_data = parse_docker_compose()
selected_service = identify_service_volumes(compose_data)

if selected_service:
    service_name = selected_service.name

    # Get credentials from Docker Compose environment
    user = compose_data.get_postgres_user(service_name)
    database = compose_data.get_postgres_db(service_name)

    # Get container user (typically "postgres")
    container_user = prompt_container_user()

    # Create backup using DockerManager with all required parameters
    with DockerManager(compose_data.name, selected_service, container_user, user, database) as docker_mgr:
        backup_path = docker_mgr.create_postgres_backup()
        print(f"Backup created: {backup_path}")
```

## Development

### Testing and Code Quality

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_parse_docker_compose.py

# Run with coverage
uv run pytest --cov=src/postgres_upgrader
```

#### Development Tools

The project includes development dependencies for code quality:

```bash
# Install with dev dependencies (includes ruff)
uv sync --group dev

# Code linting and formatting (ruff is included as dev dependency)
uv run ruff check          # Linting
uv run ruff format         # Code formatting

# Optional: Install additional tools
uv add --dev mypy coverage

# With additional tools:
uv run mypy src/           # Type checking
uv run pytest --cov=src/postgres_upgrader  # Coverage reporting
```

### Project Structure

```
postgres-upgrader/
├── src/postgres_upgrader/          # Main package
│   ├── __init__.py                 # Package exports
│   ├── compose_inspector.py       # Docker Compose config parsing via subprocess
│   ├── prompt.py                  # User interaction and volume selection
│   ├── docker.py                  # Docker operations and PostgreSQL infrastructure
│   └── postgres.py                # Business logic orchestration and workflow management
├── tests/                         # Test suite
│   ├── test_docker.py              # Docker infrastructure tests (including volume verification)
│   ├── test_parse_docker_compose.py  # Config resolution tests
│   ├── test_postgres.py            # Business logic orchestration tests
│   ├── test_subprocess_integration.py # Docker Compose subprocess integration tests
│   └── test_user_interaction.py    # User interaction tests
├── main.py                        # CLI entry point with command parsing
├── pyproject.toml                 # Project configuration
├── uv.lock                        # Dependency lock file (uv)
└── README.md                      # This file
```

## Requirements

- Python 3.13+
- Docker Compose v2+ (accessible via `docker compose config` command)
- PostgreSQL credentials either in `.env` file or Docker Compose environment variables
- A Docker Compose project with `docker-compose.yml` file
- Dependencies: `pyyaml`, `inquirer`, `docker`, `rich`
- Dev Dependencies: `pytest`, `ruff`

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`uv run pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
