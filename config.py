"""
Configuration management for Traverso Analyzer.

This module handles configuration for data paths, database locations,
and other user-specific settings.
"""

import os
from pathlib import Path
from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)


class Config:
    """Configuration manager for Traverso Analyzer."""

    # Default paths (fallbacks)
    DEFAULT_DATA_DIR = Path.home() / "traverso_data" / "data_json"
    DEFAULT_DB_PATH = Path.home() / ".flute_analysis" / "flute_analysis.db"
    DEFAULT_FINGERING_CHART = "traverso_fingerchart.txt"

    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize configuration.

        Priority order:
        1. Environment variables (highest priority)
        2. config.json file in project root
        3. config.json file in ~/.traverso/
        4. Default values (lowest priority)

        Args:
            config_file: Optional path to custom config file
        """
        self.config_file = config_file
        self._config = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from file and environment variables."""
        # Try to load from config file
        if self.config_file and self.config_file.exists():
            self._load_from_file(self.config_file)
        else:
            # Try standard locations
            locations = [
                Path.cwd() / "config.json",
                Path.home() / ".traverso" / "config.json"
            ]
            for loc in locations:
                if loc.exists():
                    self._load_from_file(loc)
                    break

        # Override with environment variables (highest priority)
        self._load_from_env()

    def _load_from_file(self, path: Path):
        """Load configuration from JSON file."""
        try:
            with open(path, 'r') as f:
                self._config = json.load(f)
            logger.info(f"Loaded configuration from {path}")
        except Exception as e:
            logger.warning(f"Could not load config from {path}: {e}")

    def _load_from_env(self):
        """Load configuration from environment variables."""
        env_mappings = {
            'TRAVERSO_DATA_DIR': 'data_dir',
            'TRAVERSO_DB_PATH': 'db_path',
            'TRAVERSO_FINGERING_CHART': 'fingering_chart'
        }

        for env_var, config_key in env_mappings.items():
            value = os.environ.get(env_var)
            if value:
                self._config[config_key] = value
                logger.info(f"Using {env_var} from environment: {value}")

    @property
    def data_dir(self) -> Path:
        """Get data_json directory path."""
        path_str = self._config.get('data_dir')

        if path_str:
            path = Path(path_str).expanduser().resolve()
            if path.exists():
                return path
            else:
                logger.warning(f"Configured data_dir does not exist: {path}")

        # Try to find data_json in common locations
        search_locations = [
            Path.cwd() / "data_json",
            Path.home() / "traverso_data" / "data_json",
            Path.home() / ".flute_analysis" / "data_json",
        ]

        for loc in search_locations:
            if loc.exists() and loc.is_dir():
                logger.info(f"Found data_json at: {loc}")
                return loc

        # If nothing found, return default (may not exist)
        logger.warning(f"data_json not found. Using default: {self.DEFAULT_DATA_DIR}")
        return self.DEFAULT_DATA_DIR

    @property
    def db_path(self) -> Path:
        """Get database file path."""
        path_str = self._config.get('db_path')

        if path_str:
            path = Path(path_str).expanduser().resolve()
            # Create parent directory if it doesn't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            return path

        # Check if database exists in current directory (local project)
        local_db = Path.cwd() / "flute_analysis.db"
        if local_db.exists():
            logger.info(f"Using local database: {local_db}")
            return local_db

        # Otherwise use default location
        self.DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        return self.DEFAULT_DB_PATH

    @property
    def fingering_chart_path(self) -> Path:
        """Get fingering chart file path."""
        # First check if custom fingering chart specified
        custom_chart = self._config.get('fingering_chart')
        if custom_chart:
            path = Path(custom_chart).expanduser().resolve()
            if path.exists():
                return path

        # Otherwise look in data_dir
        chart_path = self.data_dir / self.DEFAULT_FINGERING_CHART
        return chart_path

    def create_default_config(self, output_path: Optional[Path] = None) -> Path:
        """
        Create a default config.json file as template.

        Args:
            output_path: Where to save the config file (default: ./config.json)

        Returns:
            Path to created config file
        """
        if output_path is None:
            output_path = Path.cwd() / "config.json"

        default_config = {
            "data_dir": str(self.DEFAULT_DATA_DIR),
            "db_path": str(self.DEFAULT_DB_PATH),
            "fingering_chart": str(self.DEFAULT_DATA_DIR / self.DEFAULT_FINGERING_CHART),
            "# INSTRUCTIONS": [
                "Customize these paths to match your system",
                "You can use ~ for home directory (e.g., ~/traverso_data/data_json)",
                "Alternatively, set environment variables:",
                "  - TRAVERSO_DATA_DIR",
                "  - TRAVERSO_DB_PATH",
                "  - TRAVERSO_FINGERING_CHART"
            ]
        }

        with open(output_path, 'w') as f:
            json.dump(default_config, f, indent=2)

        logger.info(f"Created default config at: {output_path}")
        return output_path

    def validate(self) -> bool:
        """
        Validate that all required paths exist and are accessible.

        Returns:
            True if all paths are valid, False otherwise
        """
        issues = []

        # Check data_dir
        if not self.data_dir.exists():
            issues.append(f"data_dir does not exist: {self.data_dir}")
        elif not self.data_dir.is_dir():
            issues.append(f"data_dir is not a directory: {self.data_dir}")

        # Check fingering chart
        if not self.fingering_chart_path.exists():
            issues.append(f"Fingering chart not found: {self.fingering_chart_path}")

        # Check database (just that parent dir exists/can be created)
        if not self.db_path.parent.exists():
            try:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                issues.append(f"Cannot create database directory: {e}")

        if issues:
            logger.error("Configuration validation failed:")
            for issue in issues:
                logger.error(f"  - {issue}")
            return False

        logger.info("Configuration validation passed")
        return True

    def print_config(self):
        """Print current configuration (for debugging)."""
        print("\n=== Traverso Analyzer Configuration ===")
        print(f"Data directory:    {self.data_dir}")
        print(f"  Exists: {self.data_dir.exists()}")
        print(f"Database path:     {self.db_path}")
        print(f"  Exists: {self.db_path.exists()}")
        print(f"Fingering chart:   {self.fingering_chart_path}")
        print(f"  Exists: {self.fingering_chart_path.exists()}")
        print("=" * 40 + "\n")


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reset_config():
    """Reset global configuration (useful for testing)."""
    global _config
    _config = None


if __name__ == "__main__":
    # CLI utility for configuration management
    import argparse

    parser = argparse.ArgumentParser(description="Traverso Analyzer Configuration")
    parser.add_argument('--create-config', action='store_true',
                        help='Create default config.json file')
    parser.add_argument('--validate', action='store_true',
                        help='Validate current configuration')
    parser.add_argument('--print', action='store_true',
                        help='Print current configuration')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    config = get_config()

    if args.create_config:
        path = config.create_default_config()
        print(f"Created config template at: {path}")
        print("Edit this file to customize your data paths.")

    if args.validate:
        valid = config.validate()
        if valid:
            print("✓ Configuration is valid")
        else:
            print("✗ Configuration has errors (see above)")
            exit(1)

    if args.print:
        config.print_config()

    # Default: print config
    if not (args.create_config or args.validate or args.print):
        config.print_config()
