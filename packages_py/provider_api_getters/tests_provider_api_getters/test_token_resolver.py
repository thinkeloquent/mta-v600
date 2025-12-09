"""
Comprehensive tests for token_resolver/registry.py

Coverage targets:
- Decision/Branch coverage: All if/else paths
- Boundary value testing: Edge cases for inputs
- State transition testing: Registry state changes
- Log verification: caplog assertions for every branch
- Loop testing: 0, 1, and multiple iterations
- Error handling: All except blocks

Test Structure follows Defensive Programming:
- Every branch must have a corresponding test
- Every log statement must be verified
- Fail fast validation must be tested
"""
import asyncio
import logging
import pytest
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from provider_api_getters.token_resolver.registry import (
    TokenResolverRegistry,
    token_registry,
    set_api_token,
    clear_api_token,
)
from provider_api_getters.api_token.base import RequestContext


# ========== Test Fixtures ==========


class MockConfigStore:
    """Mock ConfigStore for testing."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}

    def get_nested(self, *keys: str, default: Any = None) -> Any:
        """Get a nested config value."""
        current = self._config
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return default
            else:
                return default
        return current


@pytest.fixture
def registry():
    """Create a fresh registry for each test."""
    reg = TokenResolverRegistry()
    yield reg
    # Cleanup singleton state after test
    token_registry.clear()


@pytest.fixture
def clean_singleton():
    """Ensure singleton is clean before and after test."""
    token_registry.clear()
    yield token_registry
    token_registry.clear()


# ========== Constructor Tests ==========


class TestTokenResolverRegistryConstructor:
    """Tests for TokenResolverRegistry.__init__"""

    def test_init_logs_debug_message(self, caplog, registry):
        """Branch: Constructor should log initialization debug message."""
        with caplog.at_level(logging.DEBUG):
            new_registry = TokenResolverRegistry()
            assert "TokenResolverRegistry.__init__: Initializing registry" in caplog.text


# ========== Option A: set_api_token Tests ==========


class TestSetApiToken:
    """Tests for set_api_token - Option A"""

    class TestDecisionBranchCoverage:
        """Decision/Branch coverage tests."""

        def test_branch_1_valid_provider_and_token_sets_token(self, caplog, registry):
            """Branch 1: Valid providerName and token - should set token."""
            with caplog.at_level(logging.DEBUG):
                registry.set_api_token("github", "ghp_test123")

                assert registry.has_runtime_token("github") is True
                assert "set_api_token: Setting runtime token for 'github'" in caplog.text
                assert "set_api_token: Token set for 'github' (length=11)" in caplog.text

        def test_branch_2_empty_provider_name_raises(self, caplog, registry):
            """Branch 2: Empty providerName - should raise and log error."""
            with caplog.at_level(logging.ERROR):
                with pytest.raises(ValueError, match="provider_name must be a non-empty string"):
                    registry.set_api_token("", "token")
                assert "set_api_token: provider_name must be a non-empty string" in caplog.text

        def test_branch_3_none_provider_name_raises(self, caplog, registry):
            """Branch 3: None providerName - should raise and log error."""
            with caplog.at_level(logging.ERROR):
                with pytest.raises(ValueError, match="provider_name must be a non-empty string"):
                    registry.set_api_token(None, "token")
                assert "set_api_token: provider_name must be a non-empty string" in caplog.text

        def test_branch_4_non_string_provider_name_raises(self, caplog, registry):
            """Branch 4: Non-string providerName - should raise and log error."""
            with pytest.raises(ValueError, match="provider_name must be a non-empty string"):
                registry.set_api_token(123, "token")

        def test_branch_5_empty_token_raises(self, caplog, registry):
            """Branch 5: Empty token - should raise and log error."""
            with caplog.at_level(logging.ERROR):
                with pytest.raises(ValueError, match="token must be a non-empty string"):
                    registry.set_api_token("github", "")
                assert "set_api_token: token must be a non-empty string" in caplog.text

        def test_branch_6_none_token_raises(self, caplog, registry):
            """Branch 6: None token - should raise and log error."""
            with pytest.raises(ValueError, match="token must be a non-empty string"):
                registry.set_api_token("github", None)

        def test_branch_7_non_string_token_raises(self, caplog, registry):
            """Branch 7: Non-string token - should raise and log error."""
            with pytest.raises(ValueError, match="token must be a non-empty string"):
                registry.set_api_token("github", 123)

    class TestBoundaryValueTesting:
        """Boundary value tests."""

        def test_single_char_provider_name(self, registry):
            """Boundary: Single character provider name should work."""
            registry.set_api_token("a", "token")
            assert registry.has_runtime_token("a") is True

        def test_single_char_token(self, registry):
            """Boundary: Single character token should work."""
            registry.set_api_token("github", "x")
            assert registry.has_runtime_token("github") is True

        def test_very_long_token(self, caplog, registry):
            """Boundary: Very long token should work and log length."""
            with caplog.at_level(logging.DEBUG):
                long_token = "a" * 10000
                registry.set_api_token("github", long_token)
                assert registry.has_runtime_token("github") is True
                assert "(length=10000)" in caplog.text

        def test_overwrite_existing_token(self, registry):
            """Boundary: Overwriting existing token should work."""
            registry.set_api_token("github", "token1")
            registry.set_api_token("github", "token2")
            assert registry.has_runtime_token("github") is True

    class TestStateTransitionTesting:
        """State transition tests."""

        def test_transition_empty_to_having_token(self, registry):
            """State: Should transition from empty to having token."""
            assert registry.has_runtime_token("github") is False
            registry.set_api_token("github", "token")
            assert registry.has_runtime_token("github") is True

        def test_separate_tokens_for_different_providers(self, registry):
            """State: Should maintain separate tokens for different providers."""
            registry.set_api_token("github", "gh_token")
            registry.set_api_token("jira", "jira_token")
            assert registry.has_runtime_token("github") is True
            assert registry.has_runtime_token("jira") is True


# ========== clear_api_token Tests ==========


class TestClearApiToken:
    """Tests for clear_api_token"""

    class TestDecisionBranchCoverage:
        """Decision/Branch coverage tests."""

        def test_branch_1_token_exists_clears_and_logs_existed_true(self, caplog, registry):
            """Branch 1: Token exists - should clear and log existed=True."""
            registry.set_api_token("github", "token")

            with caplog.at_level(logging.DEBUG):
                registry.clear_api_token("github")

                assert registry.has_runtime_token("github") is False
                assert "clear_api_token: Clearing runtime token for 'github'" in caplog.text
                assert "clear_api_token: Token existed=True for 'github'" in caplog.text

        def test_branch_2_token_does_not_exist_logs_existed_false(self, caplog, registry):
            """Branch 2: Token does not exist - should log existed=False."""
            with caplog.at_level(logging.DEBUG):
                registry.clear_api_token("nonexistent")
                assert "clear_api_token: Token existed=False for 'nonexistent'" in caplog.text

    class TestStateTransitionTesting:
        """State transition tests."""

        def test_transition_having_token_to_empty(self, registry):
            """State: Should transition from having token to empty."""
            registry.set_api_token("github", "token")
            assert registry.has_runtime_token("github") is True
            registry.clear_api_token("github")
            assert registry.has_runtime_token("github") is False

        def test_multiple_clears_idempotent(self, registry):
            """State: Multiple clears should be idempotent."""
            registry.set_api_token("github", "token")
            registry.clear_api_token("github")
            registry.clear_api_token("github")
            assert registry.has_runtime_token("github") is False


# ========== has_runtime_token Tests ==========


class TestHasRuntimeToken:
    """Tests for has_runtime_token"""

    def test_returns_false_when_no_token_set(self, caplog, registry):
        """Should return False when no token set and log result."""
        with caplog.at_level(logging.DEBUG):
            result = registry.has_runtime_token("github")
            assert result is False
            assert "has_runtime_token: 'github' = False" in caplog.text

    def test_returns_true_when_token_is_set(self, caplog, registry):
        """Should return True when token is set and log result."""
        registry.set_api_token("github", "token")

        with caplog.at_level(logging.DEBUG):
            result = registry.has_runtime_token("github")
            assert result is True
            assert "has_runtime_token: 'github' = True" in caplog.text


# ========== Option C: register_resolver Tests ==========


class TestRegisterResolver:
    """Tests for register_resolver - Option C"""

    class TestDecisionBranchCoverage:
        """Decision/Branch coverage tests."""

        def test_branch_1_valid_provider_and_resolver_registers(self, caplog, registry):
            """Branch 1: Valid providerName and resolver - should register."""
            async def resolver(ctx):
                return "token"

            with caplog.at_level(logging.DEBUG):
                registry.register_resolver("github", resolver)

                assert registry.has_resolver("github") is True
                assert "register_resolver: Registering resolver for 'github'" in caplog.text
                assert "register_resolver: Resolver registered for 'github'" in caplog.text

        def test_branch_2_empty_provider_name_raises(self, caplog, registry):
            """Branch 2: Empty providerName - should raise and log error."""
            with caplog.at_level(logging.ERROR):
                with pytest.raises(ValueError, match="provider_name must be a non-empty string"):
                    registry.register_resolver("", lambda x: "token")
                assert "register_resolver: provider_name must be a non-empty string" in caplog.text

        def test_branch_3_none_provider_name_raises(self, caplog, registry):
            """Branch 3: None providerName - should raise and log error."""
            with pytest.raises(ValueError, match="provider_name must be a non-empty string"):
                registry.register_resolver(None, lambda x: "token")

        def test_branch_4_non_callable_resolver_raises(self, caplog, registry):
            """Branch 4: Non-callable resolver - should raise and log error."""
            with caplog.at_level(logging.ERROR):
                with pytest.raises(ValueError, match="resolver must be a callable"):
                    registry.register_resolver("github", "not-a-function")
                assert "register_resolver: resolver must be a callable" in caplog.text

        def test_branch_5_none_resolver_raises(self, caplog, registry):
            """Branch 5: None resolver - should raise and log error."""
            with pytest.raises(ValueError, match="resolver must be a callable"):
                registry.register_resolver("github", None)

    class TestFunctionTypes:
        """Tests for different function types."""

        def test_accepts_async_function(self, registry):
            """Should accept async function."""
            async def resolver(ctx):
                return "async_token"

            registry.register_resolver("github", resolver)
            assert registry.has_resolver("github") is True

        def test_accepts_sync_function(self, registry):
            """Should accept sync function (will be called with await)."""
            def resolver(ctx):
                return "sync_token"

            registry.register_resolver("github", resolver)
            assert registry.has_resolver("github") is True

        def test_accepts_lambda(self, registry):
            """Should accept lambda function."""
            registry.register_resolver("github", lambda x: "lambda_token")
            assert registry.has_resolver("github") is True


# ========== unregister_resolver Tests ==========


class TestUnregisterResolver:
    """Tests for unregister_resolver"""

    class TestDecisionBranchCoverage:
        """Decision/Branch coverage tests."""

        def test_branch_1_resolver_exists_unregisters_and_logs_existed_true(self, caplog, registry):
            """Branch 1: Resolver exists - should unregister and log existed=True."""
            registry.register_resolver("github", lambda x: "token")

            with caplog.at_level(logging.DEBUG):
                registry.unregister_resolver("github")

                assert registry.has_resolver("github") is False
                assert "unregister_resolver: Unregistering resolver for 'github'" in caplog.text
                assert "unregister_resolver: Resolver existed=True for 'github'" in caplog.text

        def test_branch_2_resolver_does_not_exist_logs_existed_false(self, caplog, registry):
            """Branch 2: Resolver does not exist - should log existed=False."""
            with caplog.at_level(logging.DEBUG):
                registry.unregister_resolver("nonexistent")
                assert "unregister_resolver: Resolver existed=False for 'nonexistent'" in caplog.text


# ========== has_resolver Tests ==========


class TestHasResolver:
    """Tests for has_resolver"""

    def test_returns_false_when_no_resolver_or_runtime_token(self, registry):
        """Should return False when no resolver or runtime token."""
        assert registry.has_resolver("github") is False

    def test_returns_true_when_resolver_is_registered(self, registry):
        """Should return True when resolver is registered."""
        registry.register_resolver("github", lambda x: "token")
        assert registry.has_resolver("github") is True

    def test_returns_true_when_runtime_token_is_set(self, registry):
        """Should return True when runtime token is set."""
        registry.set_api_token("github", "token")
        assert registry.has_resolver("github") is True


# ========== Option B: load_resolvers_from_config Tests ==========


class TestLoadResolversFromConfig:
    """Tests for load_resolvers_from_config - Option B"""

    class TestDecisionBranchCoverage:
        """Decision/Branch coverage tests."""

        @pytest.mark.asyncio
        async def test_branch_1_no_config_store_warns_and_returns(self, caplog, registry):
            """Branch 1: No configStore provided - should warn and return."""
            with caplog.at_level(logging.WARNING):
                await registry.load_resolvers_from_config(None)
                assert "load_resolvers_from_config: No config_store provided" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_2_get_nested_throws_logs_error(self, caplog, registry):
            """Branch 2: config_store.get_nested throws - should log error."""
            mock_store = MagicMock()
            mock_store.get_nested.side_effect = Exception("Config error")

            with caplog.at_level(logging.ERROR):
                await registry.load_resolvers_from_config(mock_store)
                assert "load_resolvers_from_config: Failed to get providers from config" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_3_no_runtime_import_skips_provider(self, caplog, registry):
            """Branch 3: No runtime_import - should skip provider."""
            mock_store = MockConfigStore({
                "providers": {
                    "github": {"base_url": "https://api.github.com"}
                }
            })

            with caplog.at_level(logging.DEBUG):
                await registry.load_resolvers_from_config(mock_store)
                assert registry.has_resolver("github") is False

        @pytest.mark.asyncio
        async def test_branch_4_resolver_already_registered_skips_and_logs(self, caplog, registry):
            """Branch 4: Resolver already registered - should skip and log."""
            registry.register_resolver("github", lambda x: "existing")
            mock_store = MockConfigStore({
                "providers": {
                    "github": {"runtime_import": {"fastapi": "some.module"}}
                }
            })

            with caplog.at_level(logging.DEBUG):
                await registry.load_resolvers_from_config(mock_store)
                assert "load_resolvers_from_config: Skipping 'github' - resolver already registered" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_5_runtime_import_is_dict_with_fastapi_key(self, caplog, registry):
            """Branch 5: runtime_import is object with fastapi key."""
            mock_store = MockConfigStore({
                "providers": {
                    "github": {"runtime_import": {"fastapi": "nonexistent.module"}}
                }
            })

            with caplog.at_level(logging.DEBUG):
                await registry.load_resolvers_from_config(mock_store)
                assert "load_resolvers_from_config: Found fastapi-specific import for 'github'" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_6_runtime_import_is_string(self, caplog, registry):
            """Branch 6: runtime_import is string."""
            mock_store = MockConfigStore({
                "providers": {
                    "github": {"runtime_import": "nonexistent.module"}
                }
            })

            with caplog.at_level(logging.DEBUG):
                await registry.load_resolvers_from_config(mock_store)
                assert "load_resolvers_from_config: Found string import for 'github'" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_7_no_import_path_resolved_skips(self, caplog, registry):
            """Branch 7: No importPath resolved - should skip."""
            mock_store = MockConfigStore({
                "providers": {
                    "github": {"runtime_import": {"fastify": "./resolver.mjs"}}  # No fastapi key
                }
            })

            with caplog.at_level(logging.DEBUG):
                await registry.load_resolvers_from_config(mock_store)
                assert "load_resolvers_from_config: No import_path resolved for 'github'" in caplog.text

    class TestLoopTesting:
        """Loop testing for provider iteration."""

        @pytest.mark.asyncio
        async def test_handles_0_providers(self, caplog, registry):
            """Loop: Should handle 0 providers."""
            mock_store = MockConfigStore({"providers": {}})

            with caplog.at_level(logging.DEBUG):
                await registry.load_resolvers_from_config(mock_store)
                assert "load_resolvers_from_config: Found 0 providers to check" in caplog.text

        @pytest.mark.asyncio
        async def test_handles_1_provider(self, caplog, registry):
            """Loop: Should handle 1 provider."""
            mock_store = MockConfigStore({
                "providers": {
                    "github": {"base_url": "test"}
                }
            })

            with caplog.at_level(logging.DEBUG):
                await registry.load_resolvers_from_config(mock_store)
                assert "load_resolvers_from_config: Found 1 providers to check" in caplog.text

        @pytest.mark.asyncio
        async def test_handles_multiple_providers(self, caplog, registry):
            """Loop: Should handle multiple providers."""
            mock_store = MockConfigStore({
                "providers": {
                    "github": {"base_url": "test1"},
                    "jira": {"base_url": "test2"},
                    "figma": {"base_url": "test3"},
                }
            })

            with caplog.at_level(logging.DEBUG):
                await registry.load_resolvers_from_config(mock_store)
                assert "load_resolvers_from_config: Found 3 providers to check" in caplog.text


# ========== resolve_startup_tokens Tests ==========


class TestResolveStartupTokens:
    """Tests for resolve_startup_tokens"""

    class TestDecisionBranchCoverage:
        """Decision/Branch coverage tests."""

        @pytest.mark.asyncio
        async def test_branch_1_no_config_store_warns_and_returns(self, caplog, registry):
            """Branch 1: No configStore provided - should warn and return."""
            with caplog.at_level(logging.WARNING):
                await registry.resolve_startup_tokens(None)
                assert "resolve_startup_tokens: No config_store provided" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_2_get_nested_throws_logs_error(self, caplog, registry):
            """Branch 2: config_store.get_nested throws - should log error."""
            mock_store = MagicMock()
            mock_store.get_nested.side_effect = Exception("Config error")

            with caplog.at_level(logging.ERROR):
                await registry.resolve_startup_tokens(mock_store)
                assert "resolve_startup_tokens: Failed to get providers from config" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_3_token_resolver_not_startup_skips(self, caplog, registry):
            """Branch 3: token_resolver != startup - should skip."""
            mock_store = MockConfigStore({
                "providers": {
                    "github": {"token_resolver": "static"}
                }
            })

            with caplog.at_level(logging.INFO):
                await registry.resolve_startup_tokens(mock_store)
                # Should not attempt to resolve
                assert "Resolving startup token for 'github'" not in caplog.text

        @pytest.mark.asyncio
        async def test_branch_4_no_resolver_for_startup_provider_logs_debug(self, caplog, registry):
            """Branch 4: No resolver for startup provider - should log debug."""
            mock_store = MockConfigStore({
                "providers": {
                    "github": {"token_resolver": "startup"}
                }
            })

            with caplog.at_level(logging.DEBUG):
                await registry.resolve_startup_tokens(mock_store)
                assert "resolve_startup_tokens: No resolver for startup provider 'github'" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_5_resolver_returns_valid_token_caches(self, caplog, registry):
            """Branch 5: Resolver returns valid token - should cache."""
            async def resolver(ctx):
                return "startup_token_123"

            registry.register_resolver("github", resolver)
            mock_store = MockConfigStore({
                "providers": {
                    "github": {"token_resolver": "startup"}
                }
            })

            with caplog.at_level(logging.INFO):
                await registry.resolve_startup_tokens(mock_store)
                assert "resolve_startup_tokens: Startup token resolved for 'github'" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_6_resolver_returns_none_warns(self, caplog, registry):
            """Branch 6: Resolver returns None - should warn."""
            async def resolver(ctx):
                return None

            registry.register_resolver("github", resolver)
            mock_store = MockConfigStore({
                "providers": {
                    "github": {"token_resolver": "startup"}
                }
            })

            with caplog.at_level(logging.WARNING):
                await registry.resolve_startup_tokens(mock_store)
                assert "resolve_startup_tokens: Resolver for 'github' returned invalid token" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_7_resolver_returns_non_string_warns(self, caplog, registry):
            """Branch 7: Resolver returns non-string - should warn."""
            async def resolver(ctx):
                return 12345

            registry.register_resolver("github", resolver)
            mock_store = MockConfigStore({
                "providers": {
                    "github": {"token_resolver": "startup"}
                }
            })

            with caplog.at_level(logging.WARNING):
                await registry.resolve_startup_tokens(mock_store)
                assert "resolve_startup_tokens: Resolver for 'github' returned invalid token" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_8_resolver_throws_logs_error(self, caplog, registry):
            """Branch 8: Resolver throws error - should log error."""
            async def resolver(ctx):
                raise Exception("Resolver failed")

            registry.register_resolver("github", resolver)
            mock_store = MockConfigStore({
                "providers": {
                    "github": {"token_resolver": "startup"}
                }
            })

            with caplog.at_level(logging.ERROR):
                await registry.resolve_startup_tokens(mock_store)
                assert "resolve_startup_tokens: Failed to resolve startup token for 'github'" in caplog.text


# ========== get_token Tests ==========


class TestGetToken:
    """Tests for get_token"""

    class TestDecisionBranchCoverageResolutionPriority:
        """Decision/Branch coverage for resolution priority."""

        @pytest.mark.asyncio
        async def test_branch_1_runtime_token_override_highest_priority(self, caplog, registry):
            """Branch 1: Runtime token override (highest priority)."""
            registry.set_api_token("github", "runtime_token")
            registry.register_resolver("github", lambda x: "resolver_token")

            with caplog.at_level(logging.DEBUG):
                token = await registry.get_token("github", None, {"token_resolver": "request"})

                assert token == "runtime_token"
                assert "get_token: Using runtime token override for 'github'" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_2_startup_token_from_cache(self, caplog, registry):
            """Branch 2: Startup token from cache."""
            async def resolver(ctx):
                return "startup_token"

            registry.register_resolver("github", resolver)
            mock_store = MockConfigStore({
                "providers": {
                    "github": {"token_resolver": "startup"}
                }
            })
            await registry.resolve_startup_tokens(mock_store)

            with caplog.at_level(logging.DEBUG):
                token = await registry.get_token("github", None, {"token_resolver": "startup"})

                assert token == "startup_token"
                assert "get_token: Returning startup token for 'github'" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_3_startup_token_not_found_returns_none(self, caplog, registry):
            """Branch 3: Startup token not found - returns None."""
            with caplog.at_level(logging.DEBUG):
                token = await registry.get_token("github", None, {"token_resolver": "startup"})
                assert token is None
                assert "get_token: Returning startup token for 'github' (found=False)" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_4_request_resolver_called_with_context(self, caplog, registry):
            """Branch 4: Request resolver called with context."""
            mock_resolver = AsyncMock(return_value="request_token")
            registry.register_resolver("github", mock_resolver)

            context = RequestContext(tenant_id="tenant123")

            with caplog.at_level(logging.DEBUG):
                token = await registry.get_token("github", context, {"token_resolver": "request"})

                assert token == "request_token"
                mock_resolver.assert_called_once_with(context)
                assert "get_token: Calling request resolver for 'github'" in caplog.text
                assert "get_token: Request resolver returned token for 'github' (has_token=True)" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_5_request_resolver_returns_none(self, caplog, registry):
            """Branch 5: Request resolver returns None."""
            async def resolver(ctx):
                return None

            registry.register_resolver("github", resolver)

            with caplog.at_level(logging.DEBUG):
                token = await registry.get_token("github", None, {"token_resolver": "request"})

                assert token is None
                assert "get_token: Request resolver returned token for 'github' (has_token=False)" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_6_request_resolver_throws_catches_and_returns_none(self, caplog, registry):
            """Branch 6: Request resolver throws - should catch and return None."""
            async def resolver(ctx):
                raise Exception("Resolver exploded")

            registry.register_resolver("github", resolver)

            with caplog.at_level(logging.ERROR):
                token = await registry.get_token("github", None, {"token_resolver": "request"})

                assert token is None
                assert "get_token: Request resolver failed for 'github': Resolver exploded" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_7_request_type_but_no_resolver_falls_through(self, caplog, registry):
            """Branch 7: Request type but no resolver - falls through."""
            with caplog.at_level(logging.DEBUG):
                token = await registry.get_token("github", None, {"token_resolver": "request"})

                assert token is None
                assert "get_token: No token override for 'github', will fall back to env var" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_8_static_resolver_type_returns_none(self, caplog, registry):
            """Branch 8: Static resolver type - returns None."""
            registry.register_resolver("github", lambda x: "should_not_be_called")

            with caplog.at_level(logging.DEBUG):
                token = await registry.get_token("github", None, {"token_resolver": "static"})

                assert token is None
                assert "get_token: resolver_type='static' for 'github'" in caplog.text

        @pytest.mark.asyncio
        async def test_branch_9_no_config_provided_defaults_to_static(self, caplog, registry):
            """Branch 9: No config provided - defaults to static."""
            with caplog.at_level(logging.DEBUG):
                token = await registry.get_token("github", None, None)

                assert token is None
                assert "get_token: resolver_type='static' for 'github'" in caplog.text

    class TestBoundaryValueTesting:
        """Boundary value tests."""

        @pytest.mark.asyncio
        async def test_handles_empty_context_object(self, registry):
            """Boundary: Should handle empty context dict - empty dict is falsy in Python."""
            async def resolver(ctx):
                # Note: In Python, {} is falsy, so we check for explicit None
                return "has_ctx" if ctx is not None else "no_ctx"

            registry.register_resolver("github", resolver)
            token = await registry.get_token("github", {}, {"token_resolver": "request"})
            assert token == "has_ctx"

        @pytest.mark.asyncio
        async def test_handles_none_context(self, registry):
            """Boundary: Should handle None context."""
            async def resolver(ctx):
                return "has_ctx" if ctx else "no_ctx"

            registry.register_resolver("github", resolver)
            token = await registry.get_token("github", None, {"token_resolver": "request"})
            assert token == "no_ctx"

        @pytest.mark.asyncio
        async def test_handles_context_with_all_fields(self, registry):
            """Boundary: Should handle context with all fields."""
            async def resolver(ctx):
                return f"{ctx.tenant_id}-{ctx.user_id}"

            registry.register_resolver("github", resolver)
            context = RequestContext(tenant_id="tenant1", user_id="user1")
            token = await registry.get_token("github", context, {"token_resolver": "request"})
            assert token == "tenant1-user1"


# ========== Utility Methods Tests ==========


class TestUtilityMethods:
    """Tests for utility methods"""

    class TestGetRegisteredProviders:
        """Tests for get_registered_providers"""

        def test_returns_empty_list_when_no_providers(self, registry):
            """Should return empty list when no providers."""
            assert registry.get_registered_providers() == []

        def test_includes_runtime_token_providers(self, registry):
            """Should include runtime token providers."""
            registry.set_api_token("github", "token")
            assert "github" in registry.get_registered_providers()

        def test_includes_resolver_providers(self, registry):
            """Should include resolver providers."""
            registry.register_resolver("jira", lambda x: "token")
            assert "jira" in registry.get_registered_providers()

        def test_deduplicates_providers_with_both_token_and_resolver(self, registry):
            """Should deduplicate providers with both token and resolver."""
            registry.set_api_token("github", "token")
            registry.register_resolver("github", lambda x: "resolver")
            providers = registry.get_registered_providers()
            assert providers.count("github") == 1

    class TestClear:
        """Tests for clear"""

        def test_clears_all_state_and_logs(self, caplog, registry):
            """Should clear all state and log."""
            registry.set_api_token("github", "token")
            registry.register_resolver("jira", lambda x: "token")

            with caplog.at_level(logging.INFO):
                registry.clear()

                assert registry.has_runtime_token("github") is False
                assert registry.has_resolver("jira") is False
                assert "clear: Clearing all resolvers and tokens" in caplog.text

    class TestGetDebugInfo:
        """Tests for get_debug_info"""

        def test_returns_accurate_counts(self, registry):
            """Should return accurate counts."""
            registry.set_api_token("github", "token")
            registry.register_resolver("jira", lambda x: "token")

            info = registry.get_debug_info()

            assert info["runtime_token_count"] == 1
            assert info["resolver_count"] == 1
            assert info["startup_token_count"] == 0
            assert "github" in info["runtime_token_providers"]
            assert "jira" in info["resolver_providers"]


# ========== Convenience Functions Tests ==========


class TestConvenienceFunctions:
    """Tests for module-level convenience functions"""

    def test_set_api_token_delegates_to_singleton(self, clean_singleton):
        """set_api_token should delegate to singleton registry."""
        set_api_token("github", "token")
        assert token_registry.has_runtime_token("github") is True

    def test_clear_api_token_delegates_to_singleton(self, clean_singleton):
        """clear_api_token should delegate to singleton registry."""
        token_registry.set_api_token("github", "token")
        clear_api_token("github")
        assert token_registry.has_runtime_token("github") is False


# ========== Integration Tests ==========


class TestIntegration:
    """Integration/E2E tests"""

    @pytest.mark.asyncio
    async def test_full_token_resolution_flow(self, registry):
        """Should resolve token through full priority chain."""
        # 1. Start with resolver (lowest priority)
        async def resolver(ctx):
            return "resolver_token"

        registry.register_resolver("github", resolver)

        # Resolver should work
        token = await registry.get_token("github", None, {"token_resolver": "request"})
        assert token == "resolver_token"

        # 2. Set runtime token (higher priority)
        registry.set_api_token("github", "runtime_token")

        # Runtime token should override
        token = await registry.get_token("github", None, {"token_resolver": "request"})
        assert token == "runtime_token"

        # 3. Clear runtime token
        registry.clear_api_token("github")

        # Back to resolver
        token = await registry.get_token("github", None, {"token_resolver": "request"})
        assert token == "resolver_token"

    @pytest.mark.asyncio
    async def test_concurrent_token_resolution(self, registry):
        """Should handle concurrent token resolution."""
        async def resolver(ctx):
            await asyncio.sleep(0.01)  # Simulate async work
            tenant_id = ctx.tenant_id if ctx else "default"
            return f"token_{tenant_id}"

        registry.register_resolver("github", resolver)

        tasks = [
            registry.get_token("github", RequestContext(tenant_id="1"), {"token_resolver": "request"}),
            registry.get_token("github", RequestContext(tenant_id="2"), {"token_resolver": "request"}),
            registry.get_token("github", RequestContext(tenant_id="3"), {"token_resolver": "request"}),
        ]

        results = await asyncio.gather(*tasks)
        assert results == ["token_1", "token_2", "token_3"]
