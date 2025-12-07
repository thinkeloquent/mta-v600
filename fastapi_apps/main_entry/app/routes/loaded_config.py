"""Loaded Config Admin Routes.

Exposes static configuration status and loaded properties via admin endpoints.
Uses the static_config singleton from static_config_property_management.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


class ConfigSummary(BaseModel):
    """Summary of config status."""
    filesLoaded: int
    appEnv: Optional[str]
    errorsCount: int


class ConfigStatusResponse(BaseModel):
    """Config status response."""
    status: str
    initialized: bool
    summary: ConfigSummary
    configFile: Optional[str]
    errors: List[Dict[str, Any]]
    timestamp: str


class ConfigDataResponse(BaseModel):
    """Config data response with full configuration."""
    status: str
    appEnv: Optional[str]
    data: Dict[str, Any]
    timestamp: str


class ConfigProviderResponse(BaseModel):
    """Config provider response."""
    status: str
    provider: str
    config: Dict[str, Any]
    timestamp: str


class ConfigProviderNotFoundResponse(BaseModel):
    """Provider not found response."""
    status: str
    provider: str
    message: str
    availableProviders: List[str]
    timestamp: str


router = APIRouter()


def get_static_config():
    """Get static_config from main module - deferred import to avoid circular dependency."""
    from app.main import static_config_env
    return static_config_env


@router.get("", response_model=ConfigStatusResponse)
async def get_config_status(static_config=Depends(get_static_config)) -> ConfigStatusResponse:
    """
    Get static configuration status and summary.

    Returns config initialization status, loaded files, and error count.
    """
    is_initialized = static_config.is_initialized() if static_config else False
    load_result = static_config.get_load_result() if static_config and is_initialized else None

    files_loaded = load_result.files_loaded if load_result else []
    errors = load_result.errors if load_result else []
    app_env = load_result.app_env if load_result else None
    config_file = load_result.config_file if load_result else None

    return ConfigStatusResponse(
        status="loaded" if is_initialized and not errors else "not_configured" if not is_initialized else "error",
        initialized=is_initialized,
        summary=ConfigSummary(
            filesLoaded=len(files_loaded),
            appEnv=app_env,
            errorsCount=len(errors),
        ),
        configFile=config_file,
        errors=errors,
        timestamp=datetime.now().isoformat(),
    )


@router.get("/data", response_model=ConfigDataResponse)
async def get_config_data(static_config=Depends(get_static_config)) -> ConfigDataResponse:
    """
    Get all loaded configuration data.

    Returns the full configuration object.
    """
    is_initialized = static_config.is_initialized() if static_config else False

    if not is_initialized:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Config not initialized",
                "message": "Static configuration has not been loaded",
            }
        )

    load_result = static_config.get_load_result()
    app_env = load_result.app_env if load_result else None
    data = static_config.get_all()

    return ConfigDataResponse(
        status="loaded",
        appEnv=app_env,
        data=data,
        timestamp=datetime.now().isoformat(),
    )


@router.get("/providers/{provider_name}")
async def get_provider_config(
    provider_name: str,
    static_config=Depends(get_static_config)
):
    """
    Get configuration for a specific provider.

    Args:
        provider_name: The name of the provider to get config for (e.g., 'gemini', 'openai')

    Returns:
        Configuration for the specific provider
    """
    is_initialized = static_config.is_initialized() if static_config else False

    if not is_initialized:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Config not initialized",
                "message": "Static configuration has not been loaded",
            }
        )

    providers = static_config.get("providers", {})
    available_providers = list(providers.keys()) if providers else []

    if provider_name not in providers:
        raise HTTPException(
            status_code=404,
            detail=ConfigProviderNotFoundResponse(
                status="not_found",
                provider=provider_name,
                message=f'Provider "{provider_name}" not found in configuration',
                availableProviders=available_providers,
                timestamp=datetime.now().isoformat(),
            ).model_dump()
        )

    return ConfigProviderResponse(
        status="loaded",
        provider=provider_name,
        config=providers[provider_name],
        timestamp=datetime.now().isoformat(),
    )
