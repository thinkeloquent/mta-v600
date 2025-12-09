"""
Token Resolver Registry for dynamic API token resolution.

Supports three methods for token resolution:
- Option A: set_api_token(provider_name, token) - imperative runtime override
- Option B: runtime_import - YAML-configured module path
- Option C: register_resolver(provider_name, fn) - function registration at startup (PRIMARY)

Resolution priority:
1. Static token via set_api_token() (Option A)
2. Registered resolver via register_resolver() (Option C)
3. runtime_import module (Option B)
4. Static env var (default - handled in base class)
"""
import importlib
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Type alias for resolver functions
ResolverFunc = Callable[[Optional[Any]], Awaitable[Optional[str]]]


class TokenResolverRegistry:
    """
    Token Resolver Registry - singleton for managing token resolvers.

    Provides three methods for dynamic token resolution:
    - Option A: set_api_token() for static runtime overrides
    - Option B: load_resolvers_from_config() for YAML-based dynamic imports
    - Option C: register_resolver() for programmatic function registration (PRIMARY)
    """

    def __init__(self) -> None:
        """Initialize the registry with empty maps."""
        logger.debug("TokenResolverRegistry.__init__: Initializing registry")
        self._runtime_tokens: Dict[str, str] = {}  # Option A: set_api_token overrides
        self._resolvers: Dict[str, ResolverFunc] = {}  # Option B/C: registered resolvers
        self._startup_tokens: Dict[str, str] = {}  # Cache for startup-resolved tokens

    # ========== Option A: Static Token Override ==========

    def set_api_token(self, provider_name: str, token: str) -> None:
        """
        Set a static token at runtime (Option A).
        This takes highest priority - overrides all other methods.

        Args:
            provider_name: Provider name
            token: Static token value

        Raises:
            ValueError: If provider_name or token is empty/invalid
        """
        logger.info(f"set_api_token: Setting runtime token for '{provider_name}'")

        if not provider_name or not isinstance(provider_name, str):
            logger.error("set_api_token: provider_name must be a non-empty string")
            raise ValueError("provider_name must be a non-empty string")

        if not token or not isinstance(token, str):
            logger.error("set_api_token: token must be a non-empty string")
            raise ValueError("token must be a non-empty string")

        self._runtime_tokens[provider_name] = token
        logger.debug(
            f"set_api_token: Token set for '{provider_name}' (length={len(token)})"
        )

    def clear_api_token(self, provider_name: str) -> None:
        """
        Clear a runtime token override.

        Args:
            provider_name: Provider name
        """
        logger.info(f"clear_api_token: Clearing runtime token for '{provider_name}'")
        existed = provider_name in self._runtime_tokens
        self._runtime_tokens.pop(provider_name, None)
        logger.debug(f"clear_api_token: Token existed={existed} for '{provider_name}'")

    def has_runtime_token(self, provider_name: str) -> bool:
        """
        Check if provider has a runtime token override.

        Args:
            provider_name: Provider name

        Returns:
            True if runtime token is set
        """
        result = provider_name in self._runtime_tokens
        logger.debug(f"has_runtime_token: '{provider_name}' = {result}")
        return result

    # ========== Option C: Register Resolver Function (PRIMARY) ==========

    def register_resolver(
        self, provider_name: str, resolver: ResolverFunc
    ) -> None:
        """
        Register a resolver function directly (Option C - PRIMARY).
        This is the recommended approach for most use cases.

        The resolver function is called with a context object containing:
        - tenant_id: str | None
        - user_id: str | None
        - request: Any | None (FastAPI Request object)
        - app_state: Any | None
        - extra: dict

        Args:
            provider_name: Provider name
            resolver: Async function: (context) -> str | None

        Raises:
            ValueError: If provider_name is empty or resolver is not callable
        """
        logger.info(f"register_resolver: Registering resolver for '{provider_name}'")

        if not provider_name or not isinstance(provider_name, str):
            logger.error("register_resolver: provider_name must be a non-empty string")
            raise ValueError("provider_name must be a non-empty string")

        if not callable(resolver):
            logger.error("register_resolver: resolver must be a callable")
            raise ValueError("resolver must be a callable")

        self._resolvers[provider_name] = resolver
        logger.debug(f"register_resolver: Resolver registered for '{provider_name}'")

    def unregister_resolver(self, provider_name: str) -> None:
        """
        Unregister a resolver function.

        Args:
            provider_name: Provider name
        """
        logger.info(f"unregister_resolver: Unregistering resolver for '{provider_name}'")
        existed = provider_name in self._resolvers
        self._resolvers.pop(provider_name, None)
        logger.debug(
            f"unregister_resolver: Resolver existed={existed} for '{provider_name}'"
        )

    def has_resolver(self, provider_name: str) -> bool:
        """
        Check if provider has a registered resolver.

        Args:
            provider_name: Provider name

        Returns:
            True if resolver is registered or runtime token is set
        """
        result = (
            provider_name in self._runtime_tokens
            or provider_name in self._resolvers
        )
        logger.debug(f"has_resolver: '{provider_name}' = {result}")
        return result

    # ========== Option B: runtime_import Loading (ADVANCED) ==========

    async def load_resolvers_from_config(self, config_store: Any) -> None:
        """
        Load resolvers from YAML runtime_import paths (Option B - Advanced).
        Called during server initialization.

        Supports two formats:
        - Object: { fastify: "path.mjs", fastapi: "module.path" }
        - String: "module.path" (single platform)

        Args:
            config_store: ConfigStore instance
        """
        logger.info("load_resolvers_from_config: Loading resolvers from config")

        if not config_store:
            logger.warning("load_resolvers_from_config: No config_store provided")
            return

        try:
            providers = config_store.get_nested("providers") or {}
        except Exception as e:
            logger.error(
                f"load_resolvers_from_config: Failed to get providers from config: {e}"
            )
            return

        provider_names = list(providers.keys())
        logger.debug(
            f"load_resolvers_from_config: Found {len(provider_names)} providers to check"
        )

        for provider_name, config in providers.items():
            runtime_import = config.get("runtime_import") if config else None
            if not runtime_import:
                continue

            # Skip if already registered via register_resolver (Option C takes priority)
            if provider_name in self._resolvers:
                logger.debug(
                    f"load_resolvers_from_config: Skipping '{provider_name}' - "
                    "resolver already registered"
                )
                continue

            # Extract platform-specific import path
            import_path = None
            if isinstance(runtime_import, dict) and runtime_import.get("fastapi"):
                import_path = runtime_import["fastapi"]
                logger.debug(
                    f"load_resolvers_from_config: Found fastapi-specific import "
                    f"for '{provider_name}'"
                )
            elif isinstance(runtime_import, str):
                import_path = runtime_import
                logger.debug(
                    f"load_resolvers_from_config: Found string import "
                    f"for '{provider_name}'"
                )

            if not import_path:
                logger.debug(
                    f"load_resolvers_from_config: No import_path resolved "
                    f"for '{provider_name}'"
                )
                continue

            try:
                logger.info(
                    f"load_resolvers_from_config: Loading resolver for '{provider_name}' "
                    f"from {import_path}"
                )
                module = importlib.import_module(import_path)
                resolver = getattr(module, "resolve_token", None)

                if resolver and callable(resolver):
                    self._resolvers[provider_name] = resolver
                    logger.info(
                        f"load_resolvers_from_config: Successfully loaded resolver "
                        f"for '{provider_name}'"
                    )
                else:
                    logger.error(
                        f"load_resolvers_from_config: Module for '{provider_name}' "
                        "does not export a 'resolve_token' function"
                    )
            except Exception as e:
                logger.error(
                    f"load_resolvers_from_config: Failed to load resolver "
                    f"for '{provider_name}': {e}"
                )

    async def resolve_startup_tokens(self, config_store: Any) -> None:
        """
        Resolve startup tokens for providers with token_resolver: "startup".
        Should be called after load_resolvers_from_config or register_resolver.

        Args:
            config_store: ConfigStore instance
        """
        logger.info("resolve_startup_tokens: Resolving startup tokens")

        if not config_store:
            logger.warning("resolve_startup_tokens: No config_store provided")
            return

        try:
            providers = config_store.get_nested("providers") or {}
        except Exception as e:
            logger.error(
                f"resolve_startup_tokens: Failed to get providers from config: {e}"
            )
            return

        for provider_name, config in providers.items():
            if not config or config.get("token_resolver") != "startup":
                continue

            if provider_name not in self._resolvers:
                logger.debug(
                    f"resolve_startup_tokens: No resolver for startup provider "
                    f"'{provider_name}'"
                )
                continue

            try:
                logger.info(
                    f"resolve_startup_tokens: Resolving startup token "
                    f"for '{provider_name}'"
                )
                resolver = self._resolvers[provider_name]
                token = await resolver(None)  # No context at startup

                if token and isinstance(token, str):
                    self._startup_tokens[provider_name] = token
                    logger.info(
                        f"resolve_startup_tokens: Startup token resolved "
                        f"for '{provider_name}' (length={len(token)})"
                    )
                else:
                    logger.warning(
                        f"resolve_startup_tokens: Resolver for '{provider_name}' "
                        "returned invalid token"
                    )
            except Exception as e:
                logger.error(
                    f"resolve_startup_tokens: Failed to resolve startup token "
                    f"for '{provider_name}': {e}"
                )

    # ========== Token Resolution ==========

    async def get_token(
        self,
        provider_name: str,
        context: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Get token for a provider.

        Resolution priority:
        1. Static token via set_api_token() (Option A)
        2. Registered resolver (Option C) or runtime_import (Option B)
        3. None (fall back to env var in base class)

        Args:
            provider_name: Provider name
            context: Request context (for per-request resolution)
            config: Provider config (contains token_resolver)

        Returns:
            Resolved token or None
        """
        logger.debug(f"get_token: Resolving token for '{provider_name}'")

        # 1. Check Option A: runtime override (highest priority)
        if provider_name in self._runtime_tokens:
            logger.debug(f"get_token: Using runtime token override for '{provider_name}'")
            return self._runtime_tokens[provider_name]

        # 2. Check resolver type from config
        resolver_type = (config or {}).get("token_resolver", "static")
        logger.debug(f"get_token: resolver_type='{resolver_type}' for '{provider_name}'")

        # 3. For startup tokens, return cached value
        if resolver_type == "startup":
            startup_token = self._startup_tokens.get(provider_name)
            logger.debug(
                f"get_token: Returning startup token for '{provider_name}' "
                f"(found={startup_token is not None})"
            )
            return startup_token

        # 4. For request tokens, call resolver with context
        if resolver_type == "request" and provider_name in self._resolvers:
            logger.debug(f"get_token: Calling request resolver for '{provider_name}'")
            try:
                resolver = self._resolvers[provider_name]
                token = await resolver(context)
                logger.debug(
                    f"get_token: Request resolver returned token for '{provider_name}' "
                    f"(has_token={token is not None})"
                )
                return token
            except Exception as e:
                logger.error(
                    f"get_token: Request resolver failed for '{provider_name}': {e}"
                )
                return None

        # 5. Static - return None to fall back to env var in base class
        logger.debug(
            f"get_token: No token override for '{provider_name}', "
            "will fall back to env var"
        )
        return None

    # ========== Utility Methods ==========

    def get_registered_providers(self) -> List[str]:
        """
        Get list of all providers with registered resolvers.

        Returns:
            List of provider names
        """
        providers = set(self._runtime_tokens.keys()) | set(self._resolvers.keys())
        return list(providers)

    def clear(self) -> None:
        """
        Clear all registered resolvers and tokens.
        Useful for testing.
        """
        logger.info("clear: Clearing all resolvers and tokens")
        self._runtime_tokens.clear()
        self._resolvers.clear()
        self._startup_tokens.clear()

    def get_debug_info(self) -> Dict[str, Any]:
        """
        Get debug information about registry state.

        Returns:
            Dictionary with registry state info
        """
        return {
            "runtime_token_count": len(self._runtime_tokens),
            "resolver_count": len(self._resolvers),
            "startup_token_count": len(self._startup_tokens),
            "runtime_token_providers": list(self._runtime_tokens.keys()),
            "resolver_providers": list(self._resolvers.keys()),
            "startup_token_providers": list(self._startup_tokens.keys()),
        }


# Singleton instance
token_registry = TokenResolverRegistry()


# Convenience function (Option A API)
def set_api_token(provider_name: str, token: str) -> None:
    """Set a static token at runtime (Option A)."""
    token_registry.set_api_token(provider_name, token)


# Convenience function (Option A API)
def clear_api_token(provider_name: str) -> None:
    """Clear a runtime token override."""
    token_registry.clear_api_token(provider_name)
