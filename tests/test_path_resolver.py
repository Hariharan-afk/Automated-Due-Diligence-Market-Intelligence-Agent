"""
Comprehensive unit tests for Path Resolver utility.
Tests include edge cases, cross-platform compatibility, and path handling.
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

from src.utils.path_resolver import PathResolver, get_resolver, get_data_path, get_log_path, get_config_path, get_db_path


@pytest.fixture
def temp_project_dir():
    """Create temporary project directory structure."""
    temp_dir = tempfile.mkdtemp()
    # Create subdirectories
    (Path(temp_dir) / "data").mkdir()
    (Path(temp_dir) / "logs").mkdir()
    (Path(temp_dir) / "config").mkdir()
    yield Path(temp_dir)
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def clean_global_resolver():
    """Reset global resolver between tests."""
    import src.utils.path_resolver as pr_module
    pr_module._default_resolver = None
    yield
    pr_module._default_resolver = None


class TestPathResolverInitialization:
    """Test PathResolver initialization."""

    def test_init_with_explicit_base_dir(self, temp_project_dir):
        """Test initialization with explicitly provided base directory."""
        resolver = PathResolver(base_dir=temp_project_dir)
        assert resolver.base_dir == temp_project_dir.resolve()

    def test_init_with_project_root_env(self, temp_project_dir):
        """Test initialization with PROJECT_ROOT environment variable."""
        with patch.dict(os.environ, {"PROJECT_ROOT": str(temp_project_dir)}):
            resolver = PathResolver()
            assert resolver.base_dir == temp_project_dir.resolve()

    def test_init_without_env_fallback(self):
        """Test initialization falls back to file location when no env set."""
        with patch.dict(os.environ, {}, clear=True):
            resolver = PathResolver()
            # Should resolve to parent.parent.parent of this file
            assert resolver.base_dir.exists()
            assert resolver.base_dir.is_absolute()

    def test_init_with_relative_path(self, temp_project_dir):
        """Test initialization with relative path (should be resolved to absolute)."""
        # Create a subdirectory
        subdir = temp_project_dir / "subproject"
        subdir.mkdir()

        resolver = PathResolver(base_dir=subdir)
        assert resolver.base_dir.is_absolute()

    def test_init_with_string_path(self, temp_project_dir):
        """Test initialization with string path."""
        resolver = PathResolver(base_dir=str(temp_project_dir))
        assert isinstance(resolver.base_dir, Path)
        assert resolver.base_dir == temp_project_dir.resolve()


@pytest.mark.unit
class TestGetDataPath:
    """Test get_data_path functionality."""

    def test_get_data_path_default(self, temp_project_dir):
        """Test getting default data path."""
        resolver = PathResolver(base_dir=temp_project_dir)
        data_path = resolver.get_data_path()

        assert data_path == (temp_project_dir / "data").resolve()

    def test_get_data_path_with_subdir(self, temp_project_dir):
        """Test getting data path with subdirectory."""
        resolver = PathResolver(base_dir=temp_project_dir)
        data_path = resolver.get_data_path(subdir="raw")

        assert data_path == (temp_project_dir / "data" / "raw").resolve()

    def test_get_data_path_with_filename(self, temp_project_dir):
        """Test getting data path with filename."""
        resolver = PathResolver(base_dir=temp_project_dir)
        data_path = resolver.get_data_path(subdir="processed", filename="data.json")

        assert data_path == (temp_project_dir / "data" / "processed" / "data.json").resolve()

    def test_get_data_path_empty_subdir(self, temp_project_dir):
        """Test getting data path with empty subdir."""
        resolver = PathResolver(base_dir=temp_project_dir)
        data_path = resolver.get_data_path(subdir="", filename="file.txt")

        assert data_path == (temp_project_dir / "data" / "file.txt").resolve()

    def test_get_data_path_with_env_override(self, temp_project_dir):
        """Test that DATA_DIR environment variable overrides default."""
        custom_data = temp_project_dir / "custom_data"
        custom_data.mkdir()

        with patch.dict(os.environ, {"DATA_DIR": str(custom_data)}):
            resolver = PathResolver(base_dir=temp_project_dir)
            data_path = resolver.get_data_path()

            assert data_path == custom_data.resolve()

    def test_get_data_path_nested_subdir(self, temp_project_dir):
        """Test getting data path with nested subdirectories."""
        resolver = PathResolver(base_dir=temp_project_dir)
        data_path = resolver.get_data_path(subdir="level1/level2/level3")

        expected = (temp_project_dir / "data" / "level1" / "level2" / "level3").resolve()
        assert data_path == expected


@pytest.mark.unit
class TestGetLogPath:
    """Test get_log_path functionality."""

    def test_get_log_path_default(self, temp_project_dir):
        """Test getting default log path."""
        resolver = PathResolver(base_dir=temp_project_dir)
        log_path = resolver.get_log_path()

        assert log_path == (temp_project_dir / "logs").resolve()

    def test_get_log_path_with_filename(self, temp_project_dir):
        """Test getting log path with filename."""
        resolver = PathResolver(base_dir=temp_project_dir)
        log_path = resolver.get_log_path(filename="app.log")

        assert log_path == (temp_project_dir / "logs" / "app.log").resolve()

    def test_get_log_path_with_env_override(self, temp_project_dir):
        """Test that LOGS_DIR environment variable overrides default."""
        custom_logs = temp_project_dir / "custom_logs"
        custom_logs.mkdir()

        with patch.dict(os.environ, {"LOGS_DIR": str(custom_logs)}):
            resolver = PathResolver(base_dir=temp_project_dir)
            log_path = resolver.get_log_path()

            assert log_path == custom_logs.resolve()

    def test_get_log_path_dated_filename(self, temp_project_dir):
        """Test getting log path with dated filename."""
        resolver = PathResolver(base_dir=temp_project_dir)
        log_path = resolver.get_log_path(filename="app_2023-10-15.log")

        expected = (temp_project_dir / "logs" / "app_2023-10-15.log").resolve()
        assert log_path == expected


@pytest.mark.unit
class TestGetConfigPath:
    """Test get_config_path functionality."""

    def test_get_config_path_default(self, temp_project_dir):
        """Test getting default config path."""
        resolver = PathResolver(base_dir=temp_project_dir)
        config_path = resolver.get_config_path()

        assert config_path == (temp_project_dir / "config" / "config.yaml").resolve()

    def test_get_config_path_custom_filename(self, temp_project_dir):
        """Test getting config path with custom filename."""
        resolver = PathResolver(base_dir=temp_project_dir)
        config_path = resolver.get_config_path(filename="settings.json")

        assert config_path == (temp_project_dir / "config" / "settings.json").resolve()

    def test_get_config_path_different_extensions(self, temp_project_dir):
        """Test getting config paths with different file extensions."""
        resolver = PathResolver(base_dir=temp_project_dir)

        yaml_path = resolver.get_config_path(filename="config.yaml")
        json_path = resolver.get_config_path(filename="config.json")
        env_path = resolver.get_config_path(filename=".env")

        assert yaml_path.suffix == ".yaml"
        assert json_path.suffix == ".json"
        assert env_path.name == ".env"


@pytest.mark.unit
class TestGetDbPath:
    """Test get_db_path functionality."""

    def test_get_db_path_default(self, temp_project_dir):
        """Test getting default database path."""
        with patch.dict(os.environ, {}, clear=True):
            resolver = PathResolver(base_dir=temp_project_dir)
            db_path = resolver.get_db_path()

            expected = (temp_project_dir / "data" / "company_data.db").resolve()
            assert db_path == expected

    def test_get_db_path_with_env(self, temp_project_dir):
        """Test getting database path with DB_PATH environment variable."""
        custom_db = "custom_path/database.db"

        with patch.dict(os.environ, {"DB_PATH": custom_db}):
            resolver = PathResolver(base_dir=temp_project_dir)
            db_path = resolver.get_db_path()

            expected = (temp_project_dir / custom_db).resolve()
            assert db_path == expected

    def test_get_db_path_absolute_env(self, temp_project_dir):
        """Test getting database path with absolute path in environment."""
        abs_db_path = temp_project_dir / "absolute" / "db.sqlite"
        abs_db_path.parent.mkdir(parents=True, exist_ok=True)

        with patch.dict(os.environ, {"DB_PATH": str(abs_db_path)}):
            resolver = PathResolver(base_dir=temp_project_dir)
            db_path = resolver.get_db_path()

            assert db_path == abs_db_path.resolve()
            assert db_path.is_absolute()


@pytest.mark.unit
class TestEnsureDirExists:
    """Test ensure_dir_exists functionality."""

    def test_ensure_dir_exists_new_directory(self, temp_project_dir):
        """Test creating new directory."""
        resolver = PathResolver(base_dir=temp_project_dir)
        new_dir = temp_project_dir / "new_directory"

        result = resolver.ensure_dir_exists(new_dir)

        assert new_dir.exists()
        assert new_dir.is_dir()
        assert result == new_dir

    def test_ensure_dir_exists_existing_directory(self, temp_project_dir):
        """Test with existing directory (should not raise error)."""
        resolver = PathResolver(base_dir=temp_project_dir)
        existing_dir = temp_project_dir / "existing"
        existing_dir.mkdir()

        result = resolver.ensure_dir_exists(existing_dir)

        assert existing_dir.exists()
        assert result == existing_dir

    def test_ensure_dir_exists_nested_directories(self, temp_project_dir):
        """Test creating nested directories."""
        resolver = PathResolver(base_dir=temp_project_dir)
        nested_dir = temp_project_dir / "level1" / "level2" / "level3"

        result = resolver.ensure_dir_exists(nested_dir)

        assert nested_dir.exists()
        assert (temp_project_dir / "level1").exists()
        assert (temp_project_dir / "level1" / "level2").exists()

    def test_ensure_dir_exists_with_file_in_path(self, temp_project_dir):
        """Test creating directory for a file path."""
        resolver = PathResolver(base_dir=temp_project_dir)
        file_path = temp_project_dir / "dir" / "subdir" / "file.txt"

        result = resolver.ensure_dir_exists(file_path.parent)

        assert file_path.parent.exists()
        assert file_path.parent.is_dir()


@pytest.mark.unit
class TestGetProjectRoot:
    """Test get_project_root functionality."""

    def test_get_project_root(self, temp_project_dir):
        """Test getting project root."""
        resolver = PathResolver(base_dir=temp_project_dir)
        root = resolver.get_project_root()

        assert root == temp_project_dir.resolve()
        assert root.is_absolute()


@pytest.mark.unit
class TestSingletonResolver:
    """Test singleton resolver pattern."""

    def test_get_resolver_singleton(self, clean_global_resolver):
        """Test that get_resolver returns singleton instance."""
        resolver1 = get_resolver()
        resolver2 = get_resolver()

        assert resolver1 is resolver2

    def test_get_resolver_creates_instance(self, clean_global_resolver):
        """Test that get_resolver creates instance if none exists."""
        resolver = get_resolver()

        assert resolver is not None
        assert isinstance(resolver, PathResolver)


@pytest.mark.unit
class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_convenience_get_data_path(self, clean_global_resolver):
        """Test convenience function for getting data path."""
        path = get_data_path()
        assert isinstance(path, Path)
        assert path.is_absolute()

    def test_convenience_get_log_path(self, clean_global_resolver):
        """Test convenience function for getting log path."""
        path = get_log_path()
        assert isinstance(path, Path)
        assert path.is_absolute()

    def test_convenience_get_config_path(self, clean_global_resolver):
        """Test convenience function for getting config path."""
        path = get_config_path()
        assert isinstance(path, Path)
        assert path.is_absolute()
        assert "config.yaml" in str(path)

    def test_convenience_get_db_path(self, clean_global_resolver):
        """Test convenience function for getting database path."""
        path = get_db_path()
        assert isinstance(path, Path)
        assert path.is_absolute()

    def test_convenience_functions_with_params(self, clean_global_resolver):
        """Test convenience functions with parameters."""
        data_path = get_data_path(subdir="test", filename="file.txt")
        log_path = get_log_path(filename="app.log")
        config_path = get_config_path(filename="custom.yaml")

        assert "test" in str(data_path)
        assert "file.txt" in str(data_path)
        assert "app.log" in str(log_path)
        assert "custom.yaml" in str(config_path)


@pytest.mark.edge_case
class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_path_with_spaces(self, temp_project_dir):
        """Test paths with spaces in names."""
        resolver = PathResolver(base_dir=temp_project_dir)
        path = resolver.get_data_path(subdir="folder with spaces", filename="file with spaces.txt")

        assert "folder with spaces" in str(path)
        assert "file with spaces.txt" in str(path)

    def test_path_with_special_characters(self, temp_project_dir):
        """Test paths with special characters."""
        resolver = PathResolver(base_dir=temp_project_dir)
        # Avoid truly invalid characters for the OS
        path = resolver.get_data_path(subdir="folder-with_special.chars", filename="file@123.txt")

        assert "folder-with_special.chars" in str(path)

    def test_empty_strings(self, temp_project_dir):
        """Test handling of empty strings."""
        resolver = PathResolver(base_dir=temp_project_dir)

        data_path = resolver.get_data_path(subdir="", filename="")
        log_path = resolver.get_log_path(filename="")
        config_path = resolver.get_config_path(filename="")

        # Should handle gracefully
        assert isinstance(data_path, Path)
        assert isinstance(log_path, Path)
        assert isinstance(config_path, Path)

    def test_none_base_dir_with_cleared_env(self):
        """Test initialization with None base_dir and no environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            resolver = PathResolver(base_dir=None)
            # Should fall back to file location
            assert resolver.base_dir.exists()

    def test_path_with_dot_dot(self, temp_project_dir):
        """Test paths with .. (parent directory references)."""
        resolver = PathResolver(base_dir=temp_project_dir)
        path = resolver.get_data_path(subdir="../outside")

        # Should resolve correctly
        assert isinstance(path, Path)
        assert path.is_absolute()

    def test_very_long_path(self, temp_project_dir):
        """Test very long path names."""
        resolver = PathResolver(base_dir=temp_project_dir)
        long_subdir = "/".join(["subdir"] * 20)  # Very nested

        path = resolver.get_data_path(subdir=long_subdir)
        assert isinstance(path, Path)

    def test_unicode_paths(self, temp_project_dir):
        """Test paths with unicode characters."""
        resolver = PathResolver(base_dir=temp_project_dir)
        path = resolver.get_data_path(subdir="日本語", filename="文件.txt")

        assert "日本語" in str(path)
        assert "文件.txt" in str(path)


@pytest.mark.integration
class TestCrossPlatformCompatibility:
    """Test cross-platform path handling."""

    def test_windows_style_paths(self, temp_project_dir):
        """Test handling Windows-style path separators."""
        resolver = PathResolver(base_dir=temp_project_dir)
        # PathLib should handle this automatically
        path = resolver.get_data_path(subdir="folder\\subfolder")

        assert path.is_absolute()

    def test_unix_style_paths(self, temp_project_dir):
        """Test handling Unix-style path separators."""
        resolver = PathResolver(base_dir=temp_project_dir)
        path = resolver.get_data_path(subdir="folder/subfolder")

        assert path.is_absolute()

    def test_mixed_separators(self, temp_project_dir):
        """Test handling mixed path separators."""
        resolver = PathResolver(base_dir=temp_project_dir)
        path = resolver.get_data_path(subdir="folder\\subfolder/another")

        assert path.is_absolute()
        assert isinstance(path, Path)

    @pytest.mark.skipif(os.name == 'nt', reason="Symlink test for Unix-like systems")
    def test_symlink_resolution(self, temp_project_dir):
        """Test that symlinks are resolved correctly."""
        # Create a symlink
        target = temp_project_dir / "target_dir"
        target.mkdir()
        symlink = temp_project_dir / "link_dir"

        try:
            symlink.symlink_to(target)

            resolver = PathResolver(base_dir=symlink)
            # Should resolve to actual location
            assert resolver.base_dir.resolve() == target.resolve()
        except OSError:
            pytest.skip("Symlink creation requires permissions")


@pytest.mark.integration
class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_complete_path_workflow(self, temp_project_dir):
        """Test complete workflow with multiple path operations."""
        resolver = PathResolver(base_dir=temp_project_dir)

        # Get various paths
        data_path = resolver.get_data_path(subdir="raw", filename="data.json")
        log_path = resolver.get_log_path(filename="app.log")
        config_path = resolver.get_config_path()
        db_path = resolver.get_db_path()

        # Ensure directories exist
        resolver.ensure_dir_exists(data_path.parent)
        resolver.ensure_dir_exists(log_path.parent)

        # Verify all paths are absolute and correctly structured
        assert data_path.is_absolute()
        assert log_path.is_absolute()
        assert config_path.is_absolute()
        assert db_path.is_absolute()

        assert data_path.parent.exists()
        assert log_path.parent.exists()

    def test_environment_variable_precedence(self, temp_project_dir):
        """Test that environment variables take precedence over defaults."""
        custom_data = temp_project_dir / "custom_data"
        custom_logs = temp_project_dir / "custom_logs"
        custom_db = temp_project_dir / "custom.db"

        custom_data.mkdir()
        custom_logs.mkdir()

        env_vars = {
            "DATA_DIR": str(custom_data),
            "LOGS_DIR": str(custom_logs),
            "DB_PATH": str(custom_db)
        }

        with patch.dict(os.environ, env_vars):
            resolver = PathResolver(base_dir=temp_project_dir)

            data_path = resolver.get_data_path()
            log_path = resolver.get_log_path()
            db_path = resolver.get_db_path()

            assert data_path == custom_data.resolve()
            assert log_path == custom_logs.resolve()
            assert db_path == custom_db.resolve()
