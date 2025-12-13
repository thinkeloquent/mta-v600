import pg8000.native
import os
import sys
from dotenv import load_dotenv
import ssl

load_dotenv()

# pg8000 uses minimal URL parsing or components. 
# We'll focus on components since that's its native style, 
# but we can try to parse a URL if given for logging.

def main():
    print("="*60)
    print("pg8000 Connection Test (Enhanced)")
    print("="*60)

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("POSTGRES_DB", "postgres")

    print(f"Config:")
    print(f"  Host: {host}:{port}")
    
    # ---------------------------------------------------------
    # Test 1: Components + ssl_context=None (Default/Disable)
    # ---------------------------------------------------------
    print("\n[Test 1] Components + ssl_context=None")
    try:
        conn = pg8000.native.Connection(
            host=host,
            port=port,
            user=user,
            password=password,
            database=dbname,
            ssl_context=None
        )
        print("  SUCCESS: Connected!")
        conn.close()
    except Exception as e:
        print(f"  FAILURE: {e}")

    # ---------------------------------------------------------
    # Test 2: Components + ssl_context (No Verify)
    # ---------------------------------------------------------
    print("\n[Test 2] Components + ssl_context (check_hostname=False)")
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
