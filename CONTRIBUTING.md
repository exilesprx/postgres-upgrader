# Contributing to PostgreSQL Upgrader

We welcome contributions to the PostgreSQL Upgrader project! This document provides guidelines for contributing.

## Development Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/exilesprx/postgres-upgrader
   cd postgres-upgrader
   ```

2. **Install development dependencies:**

   ```bash
   uv sync --dev
   ```

3. **Set up pre-commit hooks (optional but recommended):**
   ```bash
   uv run pre-commit install
   ```

## Development Workflow

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/postgres_upgrader --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_docker.py

# Run tests with short output
uv run pytest --tb=short -q
```

### Code Quality Checks

```bash
# Lint code
uv run ruff check .

# Format code
uv run ruff format .

# Type checking
uv run mypy src/postgres_upgrader
```

### Running the CLI in Development

```bash
# Console script entry point (recommended)
uv run postgres-upgrader upgrade

# Primary development entry point
uv run main.py upgrade

# Alternative package entry point
uv run python -m postgres_upgrader upgrade
```

## Code Style Guidelines

- Follow PEP 8 style guidelines
- Use type hints for all function parameters and return values
- Write comprehensive docstrings for all public functions and classes
- Maintain test coverage above 95%
- Use meaningful variable and function names

### Docstring Format

We use Google-style docstrings:

```python
def example_function(param1: str, param2: int) -> bool:
    """
    Brief description of the function.

    Longer description if needed, explaining the purpose and behavior
    of the function in more detail.

    Args:
        param1: Description of the first parameter
        param2: Description of the second parameter

    Returns:
        Description of the return value

    Raises:
        SpecificException: When this exception is raised and why
    """
```

## Testing Guidelines

### Test Organization

- Place tests in the `tests/` directory
- Use descriptive test names that explain what is being tested
- Group related tests in classes
- Use meaningful assertions with descriptive error messages

### Test Categories

- **Unit tests**: Test individual functions and methods in isolation
- **Slow tests**: Mark tests that take significant time with `@pytest.mark.slow`

### Mock Usage

- Mock external dependencies (Docker API, file system, user input)
- Use meaningful mock data that represents realistic scenarios
- Verify both successful and error conditions

## Pull Request Process

1. **Create a feature branch:**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes:**
   - Write code following our style guidelines
   - Add or update tests for your changes
   - Update documentation if needed

3. **Run quality checks:**

   ```bash
   uv run ruff check .
   uv run ruff format .
   uv run mypy src/postgres_upgrader
   uv run pytest --cov=postgres_upgrader
   ```

4. **Commit your changes:**

   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

5. **Push and create pull request:**
   ```bash
   git push origin feature/your-feature-name
   ```

### Commit Message Convention

We follow conventional commits:

- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `test:` for test changes
- `refactor:` for code refactoring
- `chore:` for maintenance tasks

## Project Structure

```
postgres-upgrader/
├── src/postgres_upgrader/     # Main package
│   ├── __init__.py           # Package initialization and exports
│   ├── __main__.py           # CLI entry point
│   ├── compose_inspector.py  # Docker Compose parsing
│   ├── docker.py            # Docker operations
│   ├── postgres.py          # Business logic orchestration
│   └── prompt.py            # User interaction
├── tests/                    # Test suite
├── .github/                  # GitHub workflows and configs
├── pyproject.toml           # Project configuration
└── README.md                # User documentation
```

## Architectural Principles

1. **Separation of Concerns**: CLI, business logic, and infrastructure are separate
2. **Dependency Injection**: Pass dependencies explicitly rather than using globals
3. **Error Handling**: Provide clear, actionable error messages
4. **Type Safety**: Use type hints throughout the codebase
5. **Testability**: Write code that can be easily tested in isolation

## Getting Help

- Open an issue for bug reports or feature requests
- Start a discussion for questions about architecture or design decisions
- Check existing issues and pull requests before creating new ones

Thank you for contributing to PostgreSQL Upgrader!

