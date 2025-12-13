import asyncio
import sys
import os

# Add paths to sys.path to mimic app environment
sys.path.append("/Users/Shared/autoload/mta-v600/packages_py/provider_api_getters/src")
sys.path.append("/Users/Shared/autoload/mta-v600/packages_py/fetch_client/src")
sys.path.append("/Users/Shared/autoload/mta-v600/packages_py/fetch_proxy_dispatcher/src")
sys.path.append("/Users/Shared/autoload/mta-v600/common/src")
sys.path.append("/Users/Shared/autoload/mta-v600")

from provider_api_getters import get_provider_client
from provider_api_getters.fetch_client.factory import ProviderClientFactory
from static_config import config

async def test_provider(name):
    print(f"\n--- Testing Provider: {name} ---")
    
    # Manually inspect config first
    factory = ProviderClientFactory(config)
    api_token = factory.get_api_token(name)
    if not api_token:
        print(f"Error: Could not load ApiToken for {name}")
        return

    proxy_url = api_token.get_proxy_url()
    print(f"Configured proxy_url (from YAML): {proxy_url} (Type: {type(proxy_url)})")

    # Get client
    try:
        client = await get_provider_client(name)
        if not client:
             print("Client creation failed (returned None)")
             return
             
        # Inspect internal httpx client
        httpx_client = client._client
        print(f"HTTPX Client Base URL: {httpx_client.base_url}")
        print(f"HTTPX Client Proxies: {httpx_client.mounts}")
        
        # Try a real request (lightweight)
        # Note: most providers need auth, so 401/403 is "Success" for connectivity
        print(f"Attempting GET {httpx_client.base_url}...")
        try:
            resp = await client.get("/")
            print(f"Response: {resp.status_code}")
        except Exception as e:
            print(f"Request Failed: {e}")
            
    except Exception as e:
        print(f"Setup Failed: {e}")

async def main():
    await test_provider("github")
    await test_provider("gemini_openai")

if __name__ == "__main__":
    asyncio.run(main())
