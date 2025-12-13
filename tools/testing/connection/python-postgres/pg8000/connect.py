import pg8000.native
import os
import sys
from dotenv import load_dotenv
import ssl

load_dotenv()

def main():
    print("="*60)
    print("pg8000 Connection Test")
    print("="*60)

    # pg8000.native.Connection uses keyword args
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("POSTGRES_DB", "postgres")

    print(f"Config:")
    print(f"  Host: {host}:{port}")
    
    # ---------------------------------------------------------
    # Test 1: Components + ssl_context=None (Default: No SSL)
    # ---------------------------------------------------------
    print("\n[Test 1] Components + ssl_context=None (Default/Disable)")
    try:
        conn = pg8000.native.Connection(
            host=host,
            port=port,
            user=user,
            password=password,
            database=dbname,
            ssl_context=None # Explicitly None to disable
        )
        print("  SUCCESS: Connected!")
        print(f"  Version: {conn.run('SELECT version()')[0][0][:50]}...")
        conn.close()
    except Exception as e:
        print(f"  FAILURE: {e}")

    # ---------------------------------------------------------
    # Test 2: Components + ssl_context (Verify=False intent)
    # If user meant "disable verification" but use SSL.
    # ---------------------------------------------------------
    print("\n[Test 2] Components + ssl_context (check_hostname=False, CERT_NONE)")
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        conn = pg8000.native.Connection(
            host=host,
            port=port,
            user=user,
            password=password,
            database=dbname,
            ssl_context=ctx
        )
        print("  SUCCESS: Connected!")
        conn.close()
    except Exception as e:
        print(f"  FAILURE: {e}")

if __name__ == "__main__":
    main()
