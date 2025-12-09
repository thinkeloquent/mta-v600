"""
Token Resolver module exports.

Primary API (Option C - recommended):
    token_registry.register_resolver(provider_name, resolver_fn)

Override API (Option A):
    set_api_token(provider_name, token)
    clear_api_token(provider_name)

Advanced API (Option B):
    await token_registry.load_resolvers_from_config(config_store)
    await token_registry.resolve_startup_tokens(config_store)
"""

from .registry import (
    TokenResolverRegistry,
    token_registry,
    set_api_token,
    clear_api_token,
)

__all__ = [
    "TokenResolverRegistry",
    "token_registry",
    "set_api_token",
    "clear_api_token",
]
