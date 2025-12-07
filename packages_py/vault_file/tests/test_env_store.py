import os
import tempfile
from pathlib import Path

import pytest

from vault_file.env_store import (
    EnvStore,
    EnvKeyNotFoundError,
    LoadResult,
    env,
    on_startup,
)


@pytest.fixture
def fresh_env_store():
    """Create a fresh EnvStore instance for each test."""
    # Reset the singleton
    EnvStore._instance = None
    store = EnvStore()
    yield store
    # Clean up
    store.reset()
    EnvStore._instance = None


@pytest.fixture
def temp_env_dir():
    """Create a temporary directory with .env files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create .env file
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("DB_HOST=localhost\nDB_PORT=5432\n")

        # Create .env.local file
        env_local = Path(tmpdir) / ".env.local"
        env_local.write_text("API_KEY=secret123\nDEBUG=true\n")

        yield tmpdir


@pytest.fixture
def temp_single_env_file():
    """Create a temporary single .env file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("SINGLE_VAR=single_value\nANOTHER_VAR=another\n")
        f.flush()
        yield f.name
        os.unlink(f.name)


class TestEnvStore:
    def test_singleton_pattern(self, fresh_env_store):
        """EnvStore should be a singleton."""
        store1 = EnvStore()
        store2 = EnvStore()
        assert store1 is store2

    def test_initial_state(self, fresh_env_store):
        """EnvStore should start uninitialized."""
        assert not fresh_env_store.is_initialized()
        assert fresh_env_store.get_load_result() is None

    def test_load_single_file(self, fresh_env_store, temp_single_env_file):
        """Should load a single env file."""
        result = fresh_env_store.load(temp_single_env_file)

        assert fresh_env_store.is_initialized()
        assert len(result.files_loaded) == 1
        assert result.total_vars_loaded == 2
        assert len(result.errors) == 0

        assert fresh_env_store.get("SINGLE_VAR") == "single_value"
        assert fresh_env_store.get("ANOTHER_VAR") == "another"

    def test_load_directory(self, fresh_env_store, temp_env_dir):
        """Should load all matching files from a directory."""
        result = fresh_env_store.load(temp_env_dir)

        assert fresh_env_store.is_initialized()
        assert len(result.files_loaded) == 2
        assert result.total_vars_loaded == 4
        assert len(result.errors) == 0

        assert fresh_env_store.get("DB_HOST") == "localhost"
        assert fresh_env_store.get("API_KEY") == "secret123"

    def test_load_nonexistent_path(self, fresh_env_store):
        """Should handle nonexistent paths gracefully."""
        result = fresh_env_store.load("/nonexistent/path")

        assert fresh_env_store.is_initialized()
        assert len(result.files_loaded) == 0
        assert len(result.errors) == 1

    def test_get_returns_none_for_missing_key(self, fresh_env_store, temp_single_env_file):
        """get() should return None for missing keys."""
        fresh_env_store.load(temp_single_env_file)
        assert fresh_env_store.get("NONEXISTENT_KEY") is None

    def test_get_or_throw_raises_for_missing_key(self, fresh_env_store, temp_single_env_file):
        """get_or_throw() should raise for missing keys."""
        fresh_env_store.load(temp_single_env_file)

        with pytest.raises(EnvKeyNotFoundError) as exc_info:
            fresh_env_store.get_or_throw("NONEXISTENT_KEY")

        assert "NONEXISTENT_KEY" in str(exc_info.value)

    def test_get_or_throw_returns_value(self, fresh_env_store, temp_single_env_file):
        """get_or_throw() should return value when key exists."""
        fresh_env_store.load(temp_single_env_file)
        assert fresh_env_store.get_or_throw("SINGLE_VAR") == "single_value"

    def test_get_all(self, fresh_env_store, temp_single_env_file):
        """get_all() should return all loaded values."""
        fresh_env_store.load(temp_single_env_file)
        all_vars = fresh_env_store.get_all()

        assert "SINGLE_VAR" in all_vars
        assert all_vars["SINGLE_VAR"] == "single_value"

    def test_reset(self, fresh_env_store, temp_single_env_file):
        """reset() should clear the store."""
        fresh_env_store.load(temp_single_env_file)
        assert fresh_env_store.is_initialized()

        fresh_env_store.reset()

        assert not fresh_env_store.is_initialized()
        assert fresh_env_store.get_load_result() is None
        assert fresh_env_store.get_all() == {}

    def test_custom_pattern(self, fresh_env_store):
        """Should respect custom glob patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with different extensions
            Path(tmpdir, ".env").write_text("VAR1=val1\n")
            Path(tmpdir, ".env.prod").write_text("VAR2=val2\n")
            Path(tmpdir, "config.txt").write_text("VAR3=val3\n")

            result = fresh_env_store.load(tmpdir, pattern=".env.prod")

            assert len(result.files_loaded) == 1
            assert fresh_env_store.get("VAR2") == "val2"
            assert fresh_env_store.get("VAR1") is None


class TestOnStartup:
    @pytest.mark.asyncio
    async def test_on_startup_returns_env_store(self, fresh_env_store, temp_single_env_file):
        """on_startup should return the EnvStore instance."""
        # Reset global singleton to use fresh one
        from vault_file import env_store
        env_store.env = fresh_env_store

        result = await on_startup(temp_single_env_file)

        assert result is fresh_env_store
        assert fresh_env_store.is_initialized()

    @pytest.mark.asyncio
    async def test_on_startup_with_options(self, fresh_env_store, temp_env_dir):
        """on_startup should accept all options."""
        from vault_file import env_store
        env_store.env = fresh_env_store

        result = await on_startup(
            location=temp_env_dir,
            pattern=".env",
            override=True
        )

        assert result.is_initialized()


class TestGlobalEnv:
    def test_global_env_is_env_store(self):
        """Global env should be an EnvStore instance."""
        assert isinstance(env, EnvStore)
