import glob
import logging
import os
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import dotenv_values, load_dotenv

logger = logging.getLogger(__name__)


class EnvNotInitializedError(Exception):
    """Raised when trying to access env store before initialization."""
    pass


class EnvKeyNotFoundError(Exception):
    """Raised when a required environment key is not found."""
    pass


@dataclass
class LoadResult:
    """Result of loading environment files."""
    files_loaded: List[str] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    total_vars_loaded: int = 0


@dataclass
class OnStartupOptions:
    """Options for on_startup function."""
    location: str
    pattern: str = ".env*"
    override: bool = False


def _redact_value(value: str) -> str:
    """Return first 5 characters followed by redacted marker."""
    if len(value) <= 5:
        return value[:len(value)] + "**(redacted)"
    return value[:5] + "**(redacted)"


class EnvStore:
    """
    Singleton store for environment variables loaded from .env files.
    """
    _instance: Optional["EnvStore"] = None
    _initialized: bool = False

    def __new__(cls) -> "EnvStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data: Dict[str, str] = {}
            cls._instance._load_result: Optional[LoadResult] = None
            cls._instance._initialized = False
        return cls._instance

    def _load_file(self, file_path: Path, override: bool) -> Dict[str, str]:
        """Load a single env file and return its parsed values."""
        env_content = file_path.read_text().strip()
        stream = StringIO(env_content)

        parsed = dotenv_values(stream=stream)
        loaded_vars: Dict[str, str] = {}

        for key, value in parsed.items():
            if value is not None:
                logger.debug(f"  {key}: {_redact_value(value)}")
                loaded_vars[key] = value

        stream.seek(0)
        load_dotenv(stream=stream, override=override)

        return loaded_vars

    def load(self, location: str, pattern: str = ".env*", override: bool = False) -> LoadResult:
        """
        Load environment variables from files at the given location.

        Args:
            location: Path to a file or directory
            pattern: Glob pattern for matching files (default: .env*)
            override: Whether to override existing env vars (default: False)

        Returns:
            LoadResult with information about loaded files and any errors
        """
        result = LoadResult()
        path = Path(location)

        if not path.exists():
            result.errors.append({
                "path": str(path),
                "error": f"Path does not exist: {path}"
            })
            self._load_result = result
            self._initialized = True
            return result

        files_to_load: List[Path] = []

        if path.is_file():
            files_to_load.append(path)
        elif path.is_dir():
            glob_pattern = str(path / pattern)
            matched_files = glob.glob(glob_pattern)
            files_to_load.extend(Path(f) for f in sorted(matched_files))

        for file_path in files_to_load:
            try:
                logger.info(f"Loading env file: {file_path}")
                loaded_vars = self._load_file(file_path, override)

                for key, value in loaded_vars.items():
                    if override or key not in self._data:
                        self._data[key] = value

                result.files_loaded.append(str(file_path))
                result.total_vars_loaded += len(loaded_vars)

            except Exception as e:
                logger.error(f"Failed to load env file {file_path}: {e}")
                result.errors.append({
                    "path": str(file_path),
                    "error": str(e)
                })

        self._load_result = result
        self._initialized = True
        return result

    def get(self, key: str) -> Optional[str]:
        """
        Get an environment variable value.

        Args:
            key: The environment variable key

        Returns:
            The value or None if not found
        """
        return self._data.get(key) or os.environ.get(key)

    def get_or_throw(self, key: str) -> str:
        """
        Get an environment variable value or raise an error.

        Args:
            key: The environment variable key

        Returns:
            The value

        Raises:
            EnvKeyNotFoundError: If the key is not found
        """
        value = self.get(key)
        if value is None:
            raise EnvKeyNotFoundError(f"Environment variable '{key}' not found")
        return value

    def get_all(self) -> Dict[str, str]:
        """
        Get all loaded environment variables.

        Returns:
            Dictionary of all loaded env vars
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
        self._load_result = None
        self._initialized = False


# Singleton instance
env = EnvStore()


async def on_startup(
    location: str,
    pattern: str = ".env*",
    override: bool = False
) -> EnvStore:
    """
    Async function that loads env files from a location and returns the singleton EnvStore.

    Args:
        location: Path to file or directory
        pattern: Glob pattern (default: .env*)
        override: Whether to override existing env vars (default: False)

    Returns:
        The singleton EnvStore instance
    """
    env.load(location=location, pattern=pattern, override=override)
    return env
