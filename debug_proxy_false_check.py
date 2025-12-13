import sys
from typing import Optional
from dataclasses import dataclass

# Mock the classes to test logic without full environment
@dataclass
class FactoryConfig:
    proxy_urls: Optional[dict] = None
    proxy_url: Optional[str] = None
    agent_proxy: Optional[dict] = None
    default_environment: str = "dev"
    ca_bundle: Optional[str] = None
    cert: Optional[str] = None
    cert_verify: Optional[bool] = None

class ProxyDispatcherFactory:
    def __init__(self, config: FactoryConfig):
        self.config = config

    def get_effective_proxy_url(self) -> Optional[str]:
        # Emulate logic: 
        # 1. if proxy_url is explicitly provided (and not falsy?), use it?
        #    BUT if it is False, does it mean "DISABLE"?
        #    Or does logic say: if proxy_url: use it, else: default?
        
        # Scenario A: Standard logic "if proxy_url:"
        # Scenario B: "if proxy_url is not None:"
        
        # Let's simulate what usually happens if we pass False to a string field
        print(f"DEBUG: config.proxy_url = {self.config.proxy_url} (type: {type(self.config.proxy_url)})")
        
        # If the library uses 'if proxy_url:', False behaves like None/Empty -> Fallback!
        # If the library uses 'if proxy_url is not None:', False is not None -> Used!
        
        # Let's try to interpret "False" as a string
        val = self.config.proxy_url
        
        if val is False:
             return "DISABLED_EXPLICITLY"
        elif val:
             return f"USED: {val}"
        else:
             return "FALLBACK_TO_GLOBAL"

# Test cases
def test_behavior(val, desc):
    print(f"\n--- Testing {desc} ---")
    config = FactoryConfig(proxy_url=val)
    factory = ProxyDispatcherFactory(config)
    result = factory.get_effective_proxy_url()
    print(f"Result: {result}")

test_behavior(False, "proxy_url: false")
test_behavior("http://proxy", "proxy_url: 'http://proxy'")
test_behavior(None, "proxy_url: null")

# Import actual factory logic if possible (attempting relative import might fail in script, 
# so we rely on the above logic check mostly, but let's try to see if we can instantiate the real one)
try:
    sys.path.append("/Users/Shared/autoload/mta-v600/packages_py/provider_api_getters/src")
    sys.path.append("/Users/Shared/autoload/mta-v600/packages_py/fetch_proxy_dispatcher/src") # Guessing path
    from fetch_proxy_dispatcher import FactoryConfig as RealFactoryConfig
    print("\n--- Real FactoryConfig Test ---")
    conf = RealFactoryConfig(proxy_url=False)
    print(f"Real FactoryConfig(proxy_url=False).proxy_url = {conf.proxy_url}")
except ImportError as e:
    print(f"\nCould not import real library: {e}")
except Exception as e:
    print(f"\nError using real library: {e}")
