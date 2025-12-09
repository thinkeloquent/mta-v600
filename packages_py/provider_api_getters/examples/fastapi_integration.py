"""
FastAPI Integration Example for Token Resolver

This file demonstrates how to integrate the token_resolver registry
with a FastAPI server for dynamic API token management.

Usage Patterns:
- Option A: set_api_token() for runtime token overrides (testing/debugging)
- Option C: register_resolver() for programmatic token resolution (PRIMARY)
- Option B: load_resolvers_from_config() for YAML-based dynamic imports (ADVANCED)
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

from provider_api_getters import (
    RequestContext,
    clear_api_token,
    set_api_token,
    token_registry,
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# Example 1: Option A - Static Runtime Token Override
# Use this for testing, debugging, or when tokens are known at startup
# ============================================================


def setup_static_token_override() -> None:
    """
    Set a static token override (highest priority).

    This is useful for:
    - Testing with known tokens
    - Debugging with override tokens
    - Simple single-tenant deployments
    """
    logger.info("Setting up static token override (Option A)")

    # Set a static token - this takes highest priority
    github_token = os.getenv("GITHUB_TOKEN", "ghp_test_token")
    set_api_token("github", github_token)

    logger.info(f"Static token set for 'github' (length={len(github_token)})")
    # Can be cleared later if needed
    # clear_api_token("github")


# ============================================================
# Example 2: Option C - Register Resolver Functions (PRIMARY)
# Use this for most production scenarios with dynamic tokens
# ============================================================


async def oauth_token_resolver(context: Optional[RequestContext]) -> Optional[str]:
    """
    OAuth token resolver example.
    Refreshes OAuth tokens on-demand for each request.

    Args:
        context: Request context with tenant/user info

    Returns:
        Resolved token or None
    """
    logger.debug(
        f"OAuth resolver called: tenant_id={context.tenant_id if context else None}, "
        f"user_id={context.user_id if context else None}"
    )

    # Example: Fetch refresh token from database and exchange for access token
    if not context or not context.tenant_id:
        logger.warning("No tenant ID in context, cannot resolve OAuth token")
        return None

    try:
        # Simulate OAuth token refresh
        # In production, this would:
        # 1. Look up refresh token from database by tenant ID
        # 2. Call OAuth provider to exchange for access token
        # 3. Cache the access token with TTL

        mock_access_token = f"oauth_access_{context.tenant_id}_{datetime.now().timestamp()}"
        logger.debug(
            f"OAuth token resolved: tenant_id={context.tenant_id}, "
            f"token_length={len(mock_access_token)}"
        )
        return mock_access_token
    except Exception as e:
        logger.error(
            f"OAuth token resolution failed: tenant_id={context.tenant_id}, "
            f"error={str(e)}"
        )
        return None


async def jwt_token_resolver(context: Optional[RequestContext]) -> str:
    """
    JWT generator example.
    Generates short-lived JWTs for service-to-service auth.

    Args:
        context: Request context

    Returns:
        Generated JWT
    """
    logger.debug("JWT resolver called")

    # Example: Generate a JWT for internal service auth
    # In production, this would use a proper JWT library (python-jose, pyjwt)

    import base64
    import json

    payload = {
        "iss": "main-entry-fastapi",
        "sub": context.user_id if context else "anonymous",
        "aud": "internal-api",
        "exp": int(datetime.now().timestamp()) + 3600,  # 1 hour
    }

    # Mock JWT (in production, use python-jose or pyjwt)
    mock_jwt = f"eyJ.{base64.b64encode(json.dumps(payload).encode()).decode()}.sig"
    return mock_jwt


def setup_resolver_functions() -> None:
    """
    Setup resolver functions at server startup.
    This is the PRIMARY recommended approach for most use cases.
    """
    logger.info("Setting up resolver functions (Option C - PRIMARY)")

    # Register OAuth resolver for providers that need per-request tokens
    token_registry.register_resolver("salesforce", oauth_token_resolver)
    token_registry.register_resolver("hubspot", oauth_token_resolver)

    # Register JWT resolver for internal services
    token_registry.register_resolver("internal_api", jwt_token_resolver)

    logger.info(f"Registered resolvers: {token_registry.get_registered_providers()}")


# ============================================================
# Example 3: Option B - Load Resolvers from YAML (ADVANCED)
# Use this for modular/plugin architectures
# ============================================================


async def setup_resolvers_from_config(config_store: Any) -> None:
    """
    Load resolvers from YAML configuration.
    This is an ADVANCED pattern for modular architectures.

    Requires runtime_import in YAML config:
    ```yaml
    providers:
      custom_oauth_provider:
        token_resolver: "request"
        runtime_import:
          fastapi: "myapp.resolvers.oauth"
    ```

    Args:
        config_store: ConfigStore instance from static_config
    """
    logger.info("Loading resolvers from YAML config (Option B - ADVANCED)")

    # Load resolvers from runtime_import paths in YAML
    await token_registry.load_resolvers_from_config(config_store)

    # Resolve startup tokens for providers with token_resolver: "startup"
    await token_registry.resolve_startup_tokens(config_store)

    logger.info(f"Loaded resolvers: {token_registry.get_registered_providers()}")


# ============================================================
# FastAPI Dependencies
# ============================================================


def get_request_context(
    request: Request,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-Id"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> RequestContext:
    """
    Dependency to create RequestContext from request headers.

    Customize this based on your authentication system.
    """
    return RequestContext(
        tenant_id=x_tenant_id,
        user_id=x_user_id,
        request=request,
        app_state=request.app.state,
        extra={
            "client_host": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        },
    )


# ============================================================
# Pydantic Models
# ============================================================


class TokenStatus(BaseModel):
    """Token resolver status response."""

    status: str
    registered_providers: list[str]
    runtime_tokens: list[str]
    startup_tokens: list[str]


class TokenResponse(BaseModel):
    """Token response."""

    provider: str
    has_token: bool
    token_length: int
    context: Dict[str, Optional[str]]


class TokenSetRequest(BaseModel):
    """Request to set a token."""

    token: Optional[str] = None
    action: Optional[str] = None  # "clear" to clear the token


class TokenSetResponse(BaseModel):
    """Response after setting a token."""

    status: str
    provider: str
    token_length: Optional[int] = None


# ============================================================
# FastAPI Application
# ============================================================


def create_app() -> FastAPI:
    """Create and configure the FastAPI application with token resolver."""

    app = FastAPI(
        title="Token Resolver Integration Example",
        version="1.0.0",
        description="Example FastAPI app demonstrating token resolver integration",
    )

    @app.on_event("startup")
    async def startup_event():
        """Setup token resolution on startup."""
        logger.info("Starting token resolver integration example")

        # ============================================================
        # Setup Token Resolution (choose one or combine)
        # ============================================================

        # Option A: Static token override (for testing)
        if os.getenv("USE_STATIC_TOKENS") == "true":
            setup_static_token_override()

        # Option C: Register resolver functions (PRIMARY - recommended)
        setup_resolver_functions()

        # Option B: Load from YAML config (ADVANCED)
        # from static_config import config
        # await setup_resolvers_from_config(config)

        logger.info("Token resolver setup complete")

    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown."""
        logger.info("Shutting down token resolver integration example")
        token_registry.clear()

    # ============================================================
    # Health Check Endpoint
    # ============================================================

    @app.get("/healthz/token-resolver", response_model=TokenStatus)
    async def token_resolver_health():
        """Get token resolver registry status."""
        debug_info = token_registry.get_debug_info()
        return TokenStatus(
            status="ok",
            registered_providers=debug_info["resolver_providers"],
            runtime_tokens=debug_info["runtime_token_providers"],
            startup_tokens=debug_info["startup_token_providers"],
        )

    # ============================================================
    # Debug Endpoints
    # ============================================================

    @app.get("/api/debug/token/{provider}", response_model=TokenResponse)
    async def get_token_for_provider(
        provider: str,
        context: RequestContext = Depends(get_request_context),
    ):
        """
        Get token for a provider (debugging endpoint).

        Pass X-Tenant-Id and X-User-Id headers to test context-aware resolution.
        """
        try:
            # Get provider config from static config (simplified)
            provider_config = {"token_resolver": "request"}

            token = await token_registry.get_token(provider, context, provider_config)

            return TokenResponse(
                provider=provider,
                has_token=token is not None,
                token_length=len(token) if token else 0,
                context={
                    "tenant_id": context.tenant_id,
                    "user_id": context.user_id,
                },
            )
        except Exception as e:
            logger.error(f"Token resolution failed: {e}")
            raise HTTPException(status_code=500, detail=f"Token resolution failed: {str(e)}")

    @app.post("/api/admin/token/{provider}", response_model=TokenSetResponse)
    async def set_or_clear_token(
        provider: str,
        request: TokenSetRequest,
    ):
        """
        Admin endpoint to set/clear runtime tokens.

        Send {"action": "clear"} to clear a token.
        Send {"token": "your-token"} to set a token.
        """
        if request.action == "clear":
            clear_api_token(provider)
            return TokenSetResponse(status="cleared", provider=provider)

        if request.token:
            set_api_token(provider, request.token)
            return TokenSetResponse(
                status="set",
                provider=provider,
                token_length=len(request.token),
            )

        raise HTTPException(status_code=400, detail="Missing token or action")

    # ============================================================
    # Example Provider Endpoint
    # ============================================================

    @app.get("/api/providers/{provider}/data")
    async def get_provider_data(
        provider: str,
        context: RequestContext = Depends(get_request_context),
    ):
        """
        Example endpoint that uses token resolver to fetch provider data.

        This demonstrates the typical usage pattern:
        1. Get request context
        2. Resolve token for the provider
        3. Use token to make API call
        """
        # Get provider config (in production, from static_config)
        provider_config = {"token_resolver": "request"}

        # Resolve token
        token = await token_registry.get_token(provider, context, provider_config)

        if not token:
            raise HTTPException(
                status_code=401,
                detail=f"No token available for provider '{provider}'",
            )

        # In production, use the token to make API call to the provider
        # For this example, just return mock data
        return {
            "provider": provider,
            "data": {
                "message": f"Data from {provider}",
                "token_used": True,
                "token_length": len(token),
            },
            "context": {
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
            },
        }

    return app


# ============================================================
# Main Entry Point
# ============================================================


app = create_app()


if __name__ == "__main__":
    import uvicorn

    print("""
╔══════════════════════════════════════════════════════════════╗
║           Token Resolver Integration Example                  ║
╠══════════════════════════════════════════════════════════════╣
║  Server: http://localhost:8000                               ║
║  Docs:   http://localhost:8000/docs                          ║
║                                                              ║
║  Endpoints:                                                  ║
║    GET  /healthz/token-resolver    - Registry status         ║
║    GET  /api/debug/token/{provider}- Get token for provider  ║
║    POST /api/admin/token/{provider}- Set/clear token         ║
║    GET  /api/providers/{p}/data    - Example data endpoint   ║
╚══════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "examples.fastapi_integration:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
