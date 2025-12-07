"""Vault Admin Routes.

Exposes vault status and loaded secrets information via admin endpoints.
Uses the vault_file singleton.
"""

from datetime import datetime
from os.path import basename
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


def _redact_value(value: str) -> str:
    """Return first 5 characters followed by redacted marker."""
    if not value or not isinstance(value, str):
        return "**(redacted)"
    if len(value) <= 5:
        return value[:len(value)] + "**(redacted)"
    return value[:5] + "**(redacted)"


class VaultSummary(BaseModel):
    """Summary of vault status."""
    filesLoaded: int
    keysLoaded: int
    errorsCount: int


class VaultStatusResponse(BaseModel):
    """Vault status response."""
    status: str
    initialized: bool
    summary: VaultSummary
    files: List[str]
    errors: List[Dict[str, Any]]
    timestamp: str


class VaultKeysResponse(BaseModel):
    """Vault keys response with redacted values."""
    status: str
    keysCount: int
    keys: Dict[str, str]
    timestamp: str


class VaultFileResponse(BaseModel):
    """Vault file status response."""
    status: str
    fileName: str
    filePath: str
    timestamp: str


class VaultFileErrorResponse(BaseModel):
    """Vault file error response."""
    status: str
    fileName: str
    filePath: str
    error: str
    timestamp: str


class VaultFileNotFoundResponse(BaseModel):
    """Vault file not found response."""
    status: str
    fileName: str
    message: str
    availableFiles: List[str]
    timestamp: str


router = APIRouter()


def get_vault_env():
    """Get vault_env from main module - deferred import to avoid circular dependency."""
    from app.main import vault_env
    return vault_env


@router.get("", response_model=VaultStatusResponse)
async def get_vault_status(vault_env=Depends(get_vault_env)) -> VaultStatusResponse:
    """
    Get vault status and summary.

    Returns vault initialization status, loaded files, and error count.
    """
    is_initialized = vault_env.is_initialized() if vault_env else False
    load_result = vault_env.get_load_result() if vault_env and is_initialized else None
    all_vars = vault_env.get_all() if vault_env and is_initialized else {}

    files_loaded = load_result.files_loaded if load_result else []
    errors = load_result.errors if load_result else []

    return VaultStatusResponse(
        status="loaded" if is_initialized else "not_configured",
        initialized=is_initialized,
        summary=VaultSummary(
            filesLoaded=len(files_loaded),
            keysLoaded=len(all_vars),
            errorsCount=len(errors),
        ),
        files=files_loaded,
        errors=errors,
        timestamp=datetime.now().isoformat(),
    )


@router.get("/keys", response_model=VaultKeysResponse)
async def get_vault_keys(vault_env=Depends(get_vault_env)) -> VaultKeysResponse:
    """
    Get all loaded keys with redacted values.

    Returns all environment variable keys loaded from vault files
    with their values redacted for security.
    """
    is_initialized = vault_env.is_initialized() if vault_env else False

    if not is_initialized:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Vault not initialized",
                "message": "No VAULT_SECRET_FILE configured or failed to load",
            }
        )

    all_vars = vault_env.get_all()
    redacted_vars = {key: _redact_value(value) for key, value in all_vars.items()}

    return VaultKeysResponse(
        status="loaded",
        keysCount=len(redacted_vars),
        keys=redacted_vars,
        timestamp=datetime.now().isoformat(),
    )


@router.get("/{file_name}")
async def get_vault_file_status(
    file_name: str,
    vault_env=Depends(get_vault_env)
):
    """
    Get status for a specific loaded file.

    Args:
        file_name: The name of the vault file to check status for

    Returns:
        Status of the specific vault file (loaded, error, or not found)
    """
    is_initialized = vault_env.is_initialized() if vault_env else False

    if not is_initialized:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Vault not initialized",
                "message": "No VAULT_SECRET_FILE configured or failed to load",
            }
        )

    load_result = vault_env.get_load_result()
    loaded_files = load_result.files_loaded if load_result else []
    errors = load_result.errors if load_result else []

    # Find file in loaded files
    matched_file = None
    for file_path in loaded_files:
        if basename(file_path) == file_name or file_path == file_name:
            matched_file = file_path
            break

    if matched_file:
        return VaultFileResponse(
            status="loaded",
            fileName=file_name,
            filePath=matched_file,
            timestamp=datetime.now().isoformat(),
        )

    # Check if file had an error
    matched_error = None
    for err in errors:
        err_path = err.get("path", "")
        if basename(err_path) == file_name or err_path == file_name:
            matched_error = err
            break

    if matched_error:
        raise HTTPException(
            status_code=500,
            detail=VaultFileErrorResponse(
                status="error",
                fileName=file_name,
                filePath=matched_error.get("path", ""),
                error=matched_error.get("error", "Unknown error"),
                timestamp=datetime.now().isoformat(),
            ).model_dump()
        )

    raise HTTPException(
        status_code=404,
        detail=VaultFileNotFoundResponse(
            status="not_found",
            fileName=file_name,
            message=f'File "{file_name}" was not loaded by vault',
            availableFiles=[basename(f) for f in loaded_files],
            timestamp=datetime.now().isoformat(),
        ).model_dump()
    )
