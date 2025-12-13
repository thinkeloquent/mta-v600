#!/usr/bin/env python3
"""
Servicenow Health Check - Standalone debugging script

Run directly: python -m provider_api_getters.health_check.providers.servicenow_health_check
"""
import asyncio
import json
import sys
from pathlib import Path

# ============================================================
# Handle both direct execution and module import
# ============================================================
if __name__ == "__main__":
    _src_dir = Path(__file__).parent.parent.parent.parent
    if str(_src_dir) not in sys.path:
        sys.path.insert(0, str(_src_dir))
    from provider_api_getters.api_token import ServicenowApiToken
else:
    from ...api_token import ServicenowApiToken

from fetch_client import create_client_with_dispatcher, AuthConfig

async def check_servicenow_health(config: dict = None) -> dict:
    if config is None:
        from static_config import config as static_config
        config = static_config

    print("=" * 60)
    print("SERVICENOW HEALTH CHECK")
    print("=" * 60)

    provider = ServicenowApiToken(config)
    api_key_result = provider.get_api_key()
    network_config = provider.get_network_config()
    base_url = provider.get_base_url()

    print(f"\n[Config]")
    print(f"  Base URL: {base_url}")
    print(f"  Auth type: {api_key_result.auth_type}")

    if not api_key_result.has_credentials:
        return {"success": False, "error": "Missing credentials"}

    client = create_client_with_dispatcher(
        base_url=base_url,
        auth=AuthConfig(
            type=api_key_result.auth_type,
            raw_api_key=api_key_result.raw_api_key,
            header_name=api_key_result.header_name,
            email=api_key_result.email,  # For basic auth
        ),
        default_headers={"Accept": "application/json"},
        verify=network_config.get("cert_verify"),
        proxy=network_config.get("proxy_url"),
    )

    # Standard table API check
    health_endpoint = "/api/now/table/sys_user?sysparm_limit=1"

    async with client:
        try:
            response = await client.get(health_endpoint)
            return {
                "success": response["ok"],
                "status_code": response["status"],
                "data": response.get("data"),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent.parent
    CONFIG_DIR = PROJECT_ROOT / "common" / "config"
    from static_config import load_yaml_config, config as static_config
    load_yaml_config(config_dir=str(CONFIG_DIR))
    
    result = asyncio.run(check_servicenow_health(static_config))
    print(json.dumps(result, indent=2, default=str))
