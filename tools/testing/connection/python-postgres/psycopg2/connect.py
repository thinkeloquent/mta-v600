import psycopg2
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def main():
    print("="*60)
    print("psycopg2 Connection Test")
    print("="*60)

    db_url = os.getenv("DATABASE_URL")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    dbname = os.getenv("POSTGRES_DB", "postgres")

    print(f"Config:")
    print(f"  DATABASE_URL: {db_url}")
    print(f"  Host: {host}:{port}")
    
    # ---------------------------------------------------------
    # Test 1: Using DATABASE_URL directly
    # ---------------------------------------------------------
    print("\n[Test 1] Using DATABASE_URL directly")
    if db_url:
        try:
            # psycopg2 uses libpq, so it parses ?sslmode=... automatically
            conn = psycopg2.connect(db_url)
            print("  SUCCESS: Connected!")
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                print(f"  Version: {cur.fetchone()[0][:50]}...")
            conn.close()
        except Exception as e:
            print(f"  FAILURE: {e}")
    else:
        print("  SKIPPED")

    # ---------------------------------------------------------
    # Test 2: Using DATABASE_URL + sslmode='disable' kwarg
    # ---------------------------------------------------------
    print("\n[Test 2] Using DATABASE_URL + sslmode='disable' kwarg")
    if db_url:
        try:
            # Overriding sslmode via kwarg
            conn = psycopg2.connect(db_url, sslmode="disable")
            print("  SUCCESS: Connected!")
            conn.close()
        except Exception as e:
            print(f"  FAILURE: {e}")
    else:
        print("  SKIPPED")

    # ---------------------------------------------------------
    # Test 3: Using Components + sslmode='disable'
    # ---------------------------------------------------------
    print("\n[Test 3] Using Components + sslmode='disable'")
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
