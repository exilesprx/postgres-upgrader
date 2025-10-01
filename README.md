# PostgreSQL Upgrader

A specialized tool for managing PostgreSQL upgrades in Docker Compose environments. This tool uses Docker Compose's own resolution engine to analyze your project configuration and help you identify and select services and their associated volumes for PostgreSQL upgrade operations.

## Features

- 🔍 **Smart Configuration Parsing**: Uses `docker compose config` for accurate, resolved configuration analysis
- 🎯 **Upgrade-Focused**: Specifically designed for PostgreSQL upgrade workflows
- 🖥️ **No File Path Dependencies**: Works from any Docker Compose project directory
- 📝 **Intuitive Interface**: Interactive prompts with arrow-key navigation
- 🚀 **Automated Workflow**: Single method performs complete upgrade sequence
- ✅ **Well-Tested**: Comprehensive test suite with 15+ tests

## Installation

### With uv (recommended)

```bash
git clone https://github.com/exilesprx/postgres-upgrader
cd postgres-upgrader
uv sync

# For development (includes ruff for code formatting/linting)
uv sync --group dev
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

```bash
# Navigate to your Docker Compose project directory
cd /path/to/your/docker-compose-project

# With uv (from the postgres-updater directory)
uv run main.py

# After installation with pip/poetry
python -m postgres_upgrader
# or if installed globally:
postgres-updater
```

The tool will:

1. Analyze your Docker Compose configuration using `docker compose config`
2. Interactively prompt you to select a service and volumes
3. Access resolved environment variables for credentials
4. Perform complete PostgreSQL upgrade workflow (backup, stop, update, rebuild, restart)

### Example Output

```
[?] Select a service to inspect::
   nginx
 > postgres

[?] Select the main volume::
 > database:/var/lib/postgresql/data
   backups:/var/lib/postgresql/backups

[?] Select the backup volume::
 > backups:/var/lib/postgresql/backups

Backup location: /var/lib/postgresql/backups
Creating backup of database 'testing' for user 'tester'...
Backup created successfully: /var/lib/postgresql/backups/backup-20251001_165130.sql
[+] Stopping 1/1
 ✔ Container postgres-updater-postgres-1  Stopped                                                                           0.4s
? Going to remove postgres-updater-postgres-1 Yes
[+] Removing 1/0
 ✔ Container postgres-updater-postgres-1  Removed                                                                           0.0s
[+] Pulling 1/1
 ✔ postgres Pulled                                                                                                          0.6s
[+] Building 0.0s (0/0)                                                                                           docker:default
postgres-updater_database
Restarting service container...
[+] Running 2/2
 ✔ Volume "postgres-updater_database"     Created                                                                           0.0s
 ✔ Container postgres-updater-postgres-1  Started                                                                           0.2s
```

## How It Works

This tool uses **Docker Compose's own configuration resolution** via the `docker compose config` command to get the exact same configuration that Docker Compose would use, including:

- **Environment Variables**: Automatically resolves all variable substitutions
- **Volume Prefixes**: Gets actual volume names with project prefixes (e.g., `postgres-updater_database`)
- **Network Resolution**: Handles complex networking configurations
- **Real-time Configuration**: Always reflects current project state
- **Error Prevention**: Eliminates manual parsing inconsistencies

### As a Library

```python
# Basic usage - analyze Docker Compose configuration
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
    print(f"Resolved volume name: {backup_volume.resolved_name}")  # e.g., "postgres-updater_backups"
if data_volume:
    print(f"Data volume path: {data_volume.path}")
    print(f"Resolved volume name: {data_volume.resolved_name}")  # e.g., "postgres-updater_database"
```

```python
# Interactive volume selection
from postgres_upgrader import parse_docker_compose, identify_service_volumes

compose_data = parse_docker_compose()
volume_config = identify_service_volumes(compose_data)

if volume_config:
    service_name = volume_config.name
    backup_dir = volume_config.backup_volume.dir
    print(f"Selected service: {service_name}")
    print(f"Backup directory: {backup_dir}")
```

```python
# Full backup workflow
from postgres_upgrader import (
    parse_docker_compose,
    identify_service_volumes,
    DockerManager,
)

compose_data = parse_docker_compose()
selected_service = identify_service_volumes(compose_data)

if selected_service:
    service_name = selected_service.name

    # Get credentials from Docker Compose environment
    user = compose_data.get_postgres_user(service_name)
    database = compose_data.get_postgres_db(service_name)

    # Create backup using DockerManager with selected service
    with DockerManager(selected_service) as docker_mgr:
        backup_path = docker_mgr.create_postgres_backup(user, database)
        print(f"Backup created: {backup_path}")
```

```python
# Complete PostgreSQL upgrade workflow
from postgres_upgrader import (
    parse_docker_compose,
    identify_service_volumes,
    DockerManager,
)

compose_data = parse_docker_compose()
selected_service = identify_service_volumes(compose_data)

if selected_service:
    service_name = selected_service.name

    # Get credentials from Docker Compose environment
    user = compose_data.get_postgres_user(service_name)
    database = compose_data.get_postgres_db(service_name)

    # Perform complete upgrade workflow
    with DockerManager(selected_service) as docker_mgr:
        backup_path = docker_mgr.perform_postgres_upgrade(user, database)
        print(f"Upgrade completed! Backup: {backup_path}")
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
│   ├── docker.py                  # Docker operations and PostgreSQL backup
│   └── env.py                     # Environment configuration management
├── tests/                         # Test suite
│   ├── test_docker.py              # Docker operations tests
│   ├── test_parse_docker_compose.py  # Config resolution tests
│   └── test_user_choice.py          # User interaction tests
├── main.py                        # CLI entry point
├── pyproject.toml                 # Project configuration
├── uv.lock                        # Dependency lock file (uv)
└── README.md                      # This file
```

## Requirements

- Python 3.13+
- Docker Compose v2+ (accessible via `docker compose config` command)
- PostgreSQL credentials either in `.env` file or Docker Compose environment variables
- A Docker Compose project with `docker-compose.yml` file
- Dependencies: `pyyaml`, `inquirer`, `docker`, `python-dotenv`, `pytest`

## Future Enhancements

This tool is designed as the foundation for a complete PostgreSQL upgrade solution that will include:

- 🔄 Automated backup creation before upgrades
- 🐳 Docker image building for new PostgreSQL versions
- ⚡ Service orchestration (stop/start PostgreSQL containers)
- 📥 Backup import and restoration
- 🔧 Complete upgrade workflow automation

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`uv run pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

[Add your license here]
