"""
Path Resolver Utility
Centralized path management for cross-platform compatibility
"""

import os
from pathlib import Path
from typing import Optional


class PathResolver:
    """
    Centralized path resolution for the project.
    Handles absolute paths to ensure compatibility across different environments
    (Windows, Linux, Docker, Airflow).
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize PathResolver

        Args:
            base_dir: Base directory of the project. If None, uses PROJECT_ROOT env var
                     or determines it from the current file location.
        """
        if base_dir:
            self.base_dir = Path(base_dir).resolve()
        elif os.getenv('PROJECT_ROOT'):
            self.base_dir = Path(os.getenv('PROJECT_ROOT')).resolve()
        else:
            # Assume this file is in src/utils/, so go up two levels
            self.base_dir = Path(__file__).parent.parent.parent.resolve()

    def get_data_path(self, subdir: str = '', filename: str = '') -> Path:
        """
        Get path to data directory or file

        Args:
            subdir: Subdirectory within data/ (e.g., 'raw', 'processed')
            filename: Optional filename

        Returns:
            Absolute path to data location
        """
        data_dir = os.getenv('DATA_DIR', str(self.base_dir / 'data'))
        path = Path(data_dir) / subdir

        if filename:
            path = path / filename

        return path.resolve()

    def get_log_path(self, filename: str = '') -> Path:
        """
        Get path to logs directory or file

        Args:
            filename: Optional log filename

        Returns:
            Absolute path to log location
        """
        logs_dir = os.getenv('LOGS_DIR', str(self.base_dir / 'logs'))
        path = Path(logs_dir)

        if filename:
            path = path / filename

        return path.resolve()

    def get_config_path(self, filename: str = 'config.yaml') -> Path:
        """
        Get path to configuration file

        Args:
            filename: Config filename (default: config.yaml)

        Returns:
            Absolute path to config file
        """
        config_dir = self.base_dir / 'config'
        return (config_dir / filename).resolve()

    def get_db_path(self) -> Path:
        """
        Get path to database file

        Returns:
            Absolute path to database file
        """
        db_path = os.getenv('DB_PATH', 'data/company_data.db')

        # If relative path, make it relative to base_dir
        if not Path(db_path).is_absolute():
            return (self.base_dir / db_path).resolve()

        return Path(db_path).resolve()

    def ensure_dir_exists(self, path: Path) -> Path:
        """
        Ensure directory exists, create if it doesn't

        Args:
            path: Directory path

        Returns:
            The directory path
        """
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_project_root(self) -> Path:
        """Get the project root directory"""
        return self.base_dir


# Global instance for convenience
_default_resolver = None


def get_resolver() -> PathResolver:
    """
    Get the default PathResolver instance (singleton pattern)

    Returns:
        PathResolver instance
    """
    global _default_resolver
    if _default_resolver is None:
        _default_resolver = PathResolver()
    return _default_resolver


# Convenience functions
def get_data_path(subdir: str = '', filename: str = '') -> Path:
    """Convenience function to get data path"""
    return get_resolver().get_data_path(subdir, filename)


def get_log_path(filename: str = '') -> Path:
    """Convenience function to get log path"""
    return get_resolver().get_log_path(filename)


def get_config_path(filename: str = 'config.yaml') -> Path:
    """Convenience function to get config path"""
    return get_resolver().get_config_path(filename)


def get_db_path() -> Path:
    """Convenience function to get database path"""
    return get_resolver().get_db_path()
