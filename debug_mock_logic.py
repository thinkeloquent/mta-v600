import asyncio
import sys
from unittest.mock import MagicMock
import logging

# Configure logging to see internal debugs
logging.basicConfig(level=logging.DEBUG)

# 1. MOCK DEPENDENCIES
sys.modules["yaml"] = MagicMock()
sys.modules["static_config"] = MagicMock()

# Add paths
sys.path.append("/Users/Shared/autoload/mta-v600/packages_py/provider_api_getters/src")
sys.path.append("/Users/Shared/autoload/mta-v600/packages_py/fetch_client/src")
sys.path.append("/Users/Shared/autoload/mta-v600/packages_py/fetch_proxy_dispatcher/src")
sys.path.append("/Users/Shared/autoload/mta-v600/common/src")
sys.path.append("/Users/Shared/autoload/mta-v600")

# Import
import provider_api_getters.fetch_client.factory as factory_module
from provider_api_getters.fetch_client.factory import ProviderClientFactory

print(f"DEBUG: Loaded ProviderClientFactory from: {factory_module.__file__}")

async def test_logic():
    print("\n--- Testing Factory Logic with Mocked Dependencies ---")
    
    class MockConfig:
        def __init__(self, data):
            self._data = data
            
        def __getattr__(self, name):
            sentinel = object()
            val = self._data.get(name, sentinel)
            if val is sentinel:
                return None
            if isinstance(val, dict):
                return MockConfig(val)
            return val
            
        def get_nested(self, *keys):
            val = self._data
            for k in keys:
                if isinstance(val, dict):
                    val = val.get(k)
                else:
                    return None
            return val
            
        def get(self, key, default=None):
            return self._data.get(key, default)

    # Configuration mimicking server.dev.yaml
    config_data = {
        "providers": {
            "github": {
                "base_url": "https://api.github.com",
                "env_api_key": "GITHUB_TOKEN",
                "proxy_url": False, # TARGET VALUE
                "network": {"timeout_seconds": 10}
            }
        },
        "network": {
            "proxy_urls": {"dev": "http://BAD_PROXY:1234"},
            "default_environment": "dev",
            "agent_proxy": {"http_proxy": "http://BAD_PROXY:1234"}
        }
    }
    
    mock_conf = MockConfig(config_data)
    factory = ProviderClientFactory(mock_conf)
    
    print("Creating client for 'github'...")
    try:
        # DIAGNOSTIC: Check ApiToken manually first
        api_token = factory.get_api_token("github")
        print(f"DEBUG: ApiToken class: {api_token.__class__.__name__}")
        print(f"DEBUG: ApiToken has get_proxy_url? {'get_proxy_url' in dir(api_token)}")
        
        proxy_val = api_token.get_proxy_url()
        print(f"DEBUG: MANUAL CALL api_token.get_proxy_url() returned: {proxy_val} (Type: {type(proxy_val)})")

        client = await factory.get_client("github")
        
        if not client:
            print("Failed to create client")
            return

        httpx_client = client._client
        print(f"Client Created. Base URL: {httpx_client.base_url}")
        
        # CHECK PROXIES using private _mounts if available
        mounts = getattr(httpx_client, 'mounts', getattr(httpx_client, '_mounts', {}))
        print(f"Mounts keys: {list(mounts.keys())}")
        
        has_proxy = False
        for pattern, transport in mounts.items():
            print(f"Mount point '{pattern}': {transport}")
            # Check for proxy attributes
            p = getattr(transport, '_proxy', None) or getattr(transport, 'proxy', None)
            if p:
                 print(f"  -> FOUND PROXY: {p}")
                 has_proxy = True
        
        if not has_proxy:
            print("\nSUCCESS: No proxy configured in client transports!")
        else:
            print("\nFAILURE: Proxy detected despite proxy_url=False!")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Test Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_logic())
