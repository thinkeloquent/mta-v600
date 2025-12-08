"""Main Entry FastAPI Application.

Serves a shared frontend from frontend_apps with SSR config injection.
"""

# ============================================================
# IMPORTANT: Load vault secrets BEFORE any other imports
# This ensures environment variables are set before config loads
# ============================================================
import os

# Load vault file if VAULT_SECRET_FILE is set
_vault_secret_file = os.environ.get("VAULT_SECRET_FILE")
if _vault_secret_file:
    from vault_file import env as vault_env
    vault_env.load(location=_vault_secret_file, override=False)
else:
    vault_env = None

# ============================================================
# Load static config AFTER vault (so APP_ENV can be set from vault)
# ============================================================
from static_config import config as static_config_env, load_yaml_config

# Determine config directory path (common/config relative to monorepo root)
_config_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "common", "config"
)
load_yaml_config(config_dir=_config_dir)

# ============================================================
# Now import the rest of the application
# ============================================================
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import hello, vault, loaded_config, provider_connection

# ============================================================
# Vault service dependency for routes
# ============================================================
def get_vault_service():
    """Dependency to get the vault service singleton."""
    if vault_env is None:
        # Return a minimal mock if vault not loaded
        from vault_file import EnvStore
        return EnvStore()
    return vault_env


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Frontend configuration
FRONTEND_APP = "main_entry"
FRONTEND_DIR = Path(__file__).parent.parent.parent.parent / "frontend_apps" / FRONTEND_APP / "dist"


def get_ssr_config() -> dict:
    """Generate SSR config to inject into HTML."""
    return {
        "apiBase": "/api/fastapi",
        "backendType": "fastapi",
        "backendVersion": settings.APP_VERSION,
        "appName": "Main Entry (FastAPI)",
        # Build parameters
        "buildId": settings.BUILD_ID,
        "buildVersion": settings.BUILD_VERSION,
        "gitCommit": settings.GIT_COMMIT,
    }


def inject_config_into_html(html: str) -> str:
    """Inject SSR config into HTML by replacing the placeholder."""
    config_script = f"<script>window.__APP_CONFIG__ = {json.dumps(get_ssr_config())};</script>"
    return html.replace(
        "<!-- SSR_CONFIG_PLACEHOLDER - Backend injects window.__APP_CONFIG__ here -->",
        config_script
    )


# Cache the injected HTML
_cached_html: str | None = None


def get_index_html() -> str | None:
    """Get index.html with injected config (cached)."""
    global _cached_html
    if _cached_html is None:
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            raw_html = index_path.read_text()
            _cached_html = inject_config_into_html(raw_html)
    return _cached_html


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    frontend_status = "READY" if FRONTEND_DIR.exists() else "NOT BUILT"
    vault_status = "LOADED" if vault_env and vault_env.is_initialized() else "NOT CONFIGURED"
    vault_keys = len(vault_env.get_all()) if vault_env and vault_env.is_initialized() else 0

    # Static config status
    static_config_status = "LOADED" if static_config_env.is_initialized() else "NOT CONFIGURED"
    static_config_result = static_config_env.get_load_result()
    static_config_env_name = static_config_result.app_env if static_config_result else "N/A"
    static_config_file = static_config_result.config_file if static_config_result else "N/A"

    print(f"""
╔════════════════════════════════════════════════════════════╗
║                  Main Entry FastAPI Server                 ║
╠════════════════════════════════════════════════════════════╣
║  Server running at: http://{settings.HOST}:{settings.PORT:<25}║
║                                                            ║
║  Build Info:                                               ║
║    BUILD_ID:      {settings.BUILD_ID:<33}║
║    BUILD_VERSION: {settings.BUILD_VERSION:<33}║
║    GIT_COMMIT:    {settings.GIT_COMMIT:<33}║
║                                                            ║
║  Vault:                                                    ║
║    Status: {vault_status:<41}║
║    Keys loaded: {vault_keys:<36}║
║                                                            ║
║  Static Config:                                            ║
║    Status: {static_config_status:<41}║
║    APP_ENV: {static_config_env_name:<40}║
║                                                            ║
║  API Endpoints:                                            ║
║    GET  /health              - Health check                ║
║    GET  /api/fastapi         - API info                    ║
║    GET  /api/fastapi/hello   - Hello endpoint              ║
║    POST /api/fastapi/echo    - Echo endpoint               ║
║    GET  /docs                - Swagger UI                  ║
║    GET  /redoc               - ReDoc                       ║
║                                                            ║
║  Admin Endpoints:                                          ║
║    GET  /healthz/admin/vault          - Vault status       ║
║    GET  /healthz/admin/vault/keys     - Loaded keys        ║
║    GET  /healthz/admin/loaded-config       - Config status ║
║    GET  /healthz/admin/loaded-config/data  - Full config   ║
║                                                            ║
║  Provider Health Endpoints:                                ║
║    GET  /healthz/providers/connection      - Providers list║
║    GET  /healthz/providers/connection/:p   - Check provider║
║                                                            ║
║  Frontend: {str(FRONTEND_DIR):<40}║
║    Status: {frontend_status:<42}║
║    GET  /                    - SPA with SSR config         ║
╚════════════════════════════════════════════════════════════╝
    """)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
    }


# Register API routes
app.include_router(hello.router, prefix="/api/fastapi", tags=["hello"])
app.include_router(vault.router, prefix="/healthz/admin/vault", tags=["vault"])
app.include_router(loaded_config.router, prefix="/healthz/admin/loaded-config", tags=["loaded-config"])
app.include_router(provider_connection.router, prefix="/healthz/providers/connection", tags=["provider-connection"])


# Mount static files if frontend is built (must be after API routes)
if FRONTEND_DIR.exists():
    # Mount assets directory for JS, CSS, images
    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


# Serve index.html with SSR config (includes build info)
@app.get("/", response_class=HTMLResponse)
async def serve_root():
    """Serve frontend with SSR config injection."""
    html = get_index_html()
    if html:
        return HTMLResponse(content=html)
    return HTMLResponse(
        content="<h1>Frontend not built</h1><p>Run: cd frontend_apps/main-entry && pnpm build</p>",
        status_code=404
    )


# SPA fallback - catch all non-API routes
@app.get("/{path:path}", response_class=HTMLResponse)
async def spa_fallback(path: str):
    """SPA fallback - serve index.html for client-side routing."""
    # Don't intercept API, docs, or static file requests
    if path.startswith(("api/", "docs", "redoc", "openapi.json", "assets/")):
        return HTMLResponse(content="Not found", status_code=404)

    # Try to serve static file first
    static_file = FRONTEND_DIR / path
    if static_file.exists() and static_file.is_file():
        return FileResponse(static_file)

    # Otherwise serve SPA
    html = get_index_html()
    if html:
        return HTMLResponse(content=html)
    return HTMLResponse(
        content="<h1>Frontend not built</h1><p>Run: cd frontend_apps/main-entry && pnpm build</p>",
        status_code=404
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
