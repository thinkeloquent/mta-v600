import psycopg2
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def get_db_url():
    """Get from env or build from components."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("POSTGRES_DB", "postgres")
    
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

def main():
    print("="*60)
    print("psycopg2 Connection Test (Enhanced)")
    print("="*60)

    db_url = get_db_url()
    
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("POSTGRES_DB", "postgres")

    print(f"Config:")
    print(f"  Target URL: {db_url}")

    # ---------------------------------------------------------
    # Test 1: Using URL directly
    # ---------------------------------------------------------
    print("\n[Test 1] Using URL directly")
    try:
        conn = psycopg2.connect(db_url)
        print("  SUCCESS: Connected!")
        conn.close()
    except Exception as e:
        print(f"  FAILURE: {e}")

    # ---------------------------------------------------------
    # Test 2: Using URL + sslmode='disable' kwarg
    # ---------------------------------------------------------
    print("\n[Test 2] Using URL + sslmode='disable'")
    try:
        conn = psycopg2.connect(db_url, sslmode="disable")
        print("  SUCCESS: Connected!")
        conn.close()
    except Exception as e:
        print(f"  FAILURE: {e}")

    # ---------------------------------------------------------
    # Test 3: Components + sslmode='disable'
    # ---------------------------------------------------------
    print("\n[Test 3] Components + sslmode='disable'")
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname,
            sslmode="disable"
        )
        print("  SUCCESS: Connected!")
        conn.close()
    except Exception as e:
        print(f"  FAILURE: {e}")

if __name__ == "__main__":
    main()
