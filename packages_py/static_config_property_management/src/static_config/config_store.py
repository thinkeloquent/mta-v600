"""Configuration store singleton for static YAML config management.

Provides a singleton pattern similar to vault_file.EnvStore for
loading and accessing YAML configuration files.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .types import ServerConfig

logger = logging.getLogger(__name__)


class ConfigNotInitializedError(Exception):
    """Raised when trying to access config store before initialization."""
    pass


class ConfigKeyNotFoundError(Exception):
    """Raised when a required configuration key is not found."""
    pass


@dataclass
class LoadResult:
    """Result of loading configuration files."""
    files_loaded: List[str] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    config_file: Optional[str] = None
    app_env: Optional[str] = None


class ConfigStore:
    """
    Singleton store for configuration loaded from YAML files.
    """
    _instance: Optional["ConfigStore"] = None
    _initialized: bool = False

    def __new__(cls) -> "ConfigStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data: Dict[str, Any] = {}
            cls._instance._config: Optional[ServerConfig] = None
            cls._instance._load_result: Optional[LoadResult] = None
            cls._instance._initialized = False
        return cls._instance

    def _find_config_path(self, base_path: Path, app_env: str) -> Path:
        """Find the configuration file path based on APP_ENV."""
        env_specific = base_path / f"server.{app_env}.yaml"
        if env_specific.exists():
            logger.debug(f"Using environment-specific config: {env_specific}")
            return env_specific

        default = base_path / "server.yaml"
        if default.exists():
            logger.debug(f"Using default config: {default}")
            return default

        raise FileNotFoundError(
            f"No config file found. Tried: {env_specific}, {default}"
        )

    def _parse_yaml(self, file_path: Path) -> Dict[str, Any]:
        """Parse a YAML file and return its contents."""
        logger.debug(f"Parsing YAML file: {file_path}")
        content = file_path.read_text()
        return yaml.safe_load(content) or {}

    def _validate_config(self, data: Dict[str, Any]) -> ServerConfig:
        """Validate and parse configuration data into ServerConfig model."""
        logger.debug("Validating configuration against ServerConfig model")
        return ServerConfig.model_validate(data)

    def load(
        self,
        config_dir: str,
        app_env: Optional[str] = None,
    ) -> LoadResult:
        """
        Load configuration from a YAML file.

        Args:
            config_dir: Path to the configuration directory
            app_env: Environment name (default: from APP_ENV env var or 'dev')

        Returns:
            LoadResult with information about loaded config and any errors
        """
        result = LoadResult()

        # Get APP_ENV from environment or parameter
        env = app_env or os.environ.get("APP_ENV", "dev")
        result.app_env = env
        logger.info(f"Loading static config for APP_ENV={env}")

        path = Path(config_dir)
        if not path.exists():
            error_msg = f"Config directory does not exist: {path}"
            logger.error(error_msg)
            result.errors.append({"path": str(path), "error": error_msg})
            self._load_result = result
            self._initialized = True
            return result

        try:
            config_path = self._find_config_path(path, env)
            result.config_file = str(config_path)

            raw_data = self._parse_yaml(config_path)
            self._data = raw_data
            self._config = self._validate_config(raw_data)

            result.files_loaded.append(str(config_path))
            logger.info(f"Successfully loaded config from: {config_path}")

        except FileNotFoundError as e:
            error_msg = str(e)
            logger.error(error_msg)
            result.errors.append({"path": str(path), "error": error_msg})

        except yaml.YAMLError as e:
            error_msg = f"YAML parsing error: {e}"
            logger.error(error_msg)
            result.errors.append({"path": str(path), "error": error_msg})

        except Exception as e:
            error_msg = f"Failed to load config: {e}"
            logger.error(error_msg)
            result.errors.append({"path": str(path), "error": error_msg})

        self._load_result = result
        self._initialized = True
        return result

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a top-level configuration value.

        Args:
            key: The configuration key (e.g., 'providers', 'client')
            default: Default value if not found

        Returns:
            The value or default if not found
        """
        return self._data.get(key, default)

    def get_nested(self, *keys: str, default: Any = None) -> Any:
        """
        Get a nested configuration value.

        Args:
            *keys: Path of keys to traverse (e.g., 'providers', 'gemini', 'base_url')
            default: Default value if not found

        Returns:
            The value or default if not found
        """
        current = self._data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return default
            else:
                return default
        return current

    def get_config(self) -> Optional[ServerConfig]:
        """
        Get the validated ServerConfig object.

        Returns:
            ServerConfig or None if not loaded
        """
        return self._config

    def get_all(self) -> Dict[str, Any]:
        """
        Get all loaded configuration data.

        Returns:
            Dictionary of all loaded config
        """
        return dict(self._data)

    def is_initialized(self) -> bool:
        """
        Check if the store has been initialized.

        Returns:
            True if load() has been called
        """
        return self._initialized

    def get_load_result(self) -> Optional[LoadResult]:
        """
        Get the result from the last load operation.

        Returns:
            LoadResult or None if not loaded yet
        """
        return self._load_result

    def reset(self) -> None:
        """
        Clear the store and reset to uninitialized state.
        """
        self._data.clear()
        self._config = None
        self._load_result = None
        self._initialized = False


# Singleton instance
config = ConfigStore()


async def on_startup(
    config_dir: str,
    app_env: Optional[str] = None,
) -> ConfigStore:
    """
    Async function that loads config from a YAML file and returns the singleton ConfigStore.

    Args:
        config_dir: Path to the configuration directory
        app_env: Environment name (default: from APP_ENV env var or 'dev')

    Returns:
        The singleton ConfigStore instance
    """
    config.load(config_dir=config_dir, app_env=app_env)
    return config
