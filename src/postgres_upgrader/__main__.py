#!/usr/bin/env python3
"""
PostgreSQL Docker Compose Upgrader CLI Entry Point.

This module provides the entry point for the installed package.
It delegates to the main CLI implementation in the project root.
"""

import sys
from pathlib import Path


def main() -> None:
    """Entry point that delegates to the main CLI application."""
    # Add project root to path so we can import main
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    # Import and run the main CLI
    from main import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
