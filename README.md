# PostgreSQL Updater

A tool to extract backup locations from Docker Compose files.

## Installation

### With uv (recommended)
```bash
git clone <your-repo>
cd postgres-updater
uv sync
```

### With pip
```bash
git clone <your-repo>
cd postgres-updater
pip install -e .
```

### With poetry
```bash
git clone <your-repo>
cd postgres-updater
poetry install
```

## Usage

### Command Line Tool
```bash
# With uv
uv run ./main.py docker-compose.yml

# After installation with any package manager
./main.py docker-compose.yml
```

### As a Library
```python
from postgres_updater import backup_location

location = backup_location("docker-compose.yml")
print(location)
```

## Development

```bash
# Run tests
uv run pytest

# Run with different Python versions
python -m pytest
```
