"""
Pytest configuration file that ensures the project root is in the Python path.
This allows imports like 'from src.module import ...' to work.
"""
import sys
from pathlib import Path

# Add the project root directory to Python path so we can import src modules
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))