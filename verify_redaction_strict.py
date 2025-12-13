
import sys
import logging
from fetch_client.config import AuthConfig, format_auth_header_value
from fetch_client.core.base_client import _mask_headers_for_logging

def test_redaction():
    print("Testing Redaction...")
    
    # Test 1: Bearer Long
    h1 = {"Authorization": "Bearer 12345678901234567890"}
    m1 = _mask_headers_for_logging(h1)
    print(f"1. Bearer Long: {m1['Authorization']}")
    assert "Bearer 123456789012345***" in m1['Authorization'] or "Bearer 123456789012345..." in m1['Authorization']

    # Test 2: Basic Long
    h2 = {"Authorization": "Basic user:pass123456789012345"}
    m2 = _mask_headers_for_logging(h2)
    print(f"2. Basic Long:  {m2['Authorization']}")
    # Expect: Basic user:pass1234... OR Basic user:pass1234***
    # Logic: f"{schema} {preview}" + "*" * ...
    # Preview is 15 chars: "user:pass123456"
    assert "Basic user:pass123456" in m2['Authorization']

    # Test 3: No Schema
    h3 = {"Authorization": "supersecrettokenvalue"}
    m3 = _mask_headers_for_logging(h3)
    print(f"3. No Schema:   {m3['Authorization']}")
    assert "Basic" not in m3['Authorization']
    assert "Bearer" not in m3['Authorization']
    assert "*" * len("supersecrettokenvalue") == m3['Authorization']

def test_strict_bearer():
    print("\nTesting Strict Bearer...")
    
    # Config with bearer type, raw key, AND username (which should be IGNORED)
    auth = AuthConfig(
        type="bearer",
        raw_api_key="my-raw-token",
        username="ignored-user",
        password="ignored-pass"
    )
    
    # Old logic would see username and switch to bearer_username_password encoding
    # New strict logic should just use raw_api_key
    
    val = format_auth_header_value(auth, auth.raw_api_key)
    print(f"Value: {val}")
    
    assert val == "Bearer my-raw-token"
    # assert val != "Bearer <base64...>"

if __name__ == "__main__":
    try:
        test_redaction()
        test_strict_bearer()
        print("\n✅ Verification Passed!")
    except AssertionError as e:
        print(f"\n❌ Verification Failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        sys.exit(1)
