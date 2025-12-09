#!/usr/bin/env python3
"""
Usage:
    # Basic usage
    python find_safe_version.py rich --url <HOST>/api/pypi/pypi/simple

    # Check more versions (e.g. last 20)
    python find_safe_version.py mdurl --url <HOST>/api/pypi/pypi/simple --limit 20
"""
import subprocess
import sys
import argparse
import tempfile


def get_available_versions(package_name, index_url=None):
    """
    Uses 'pip index versions' to find what the repository claims is available.
    """
    cmd = [sys.executable, "-m", "pip", "index", "versions", package_name]
    if index_url:
        cmd.extend(["--index-url", index_url])

    print(f"[*] Fetching metadata for '{package_name}'...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # Look for the line starting with "Available versions:"
        for line in result.stdout.splitlines():
            if "Available versions:" in line:
                # Extract the versions string and split by comma
                versions_str = line.split("Available versions:")[1].strip()
                # Split, strip whitespace, and filter empty strings
                versions = [v.strip() for v in versions_str.split(",") if v.strip()]
                return versions
    except subprocess.CalledProcessError as e:
        print(f"[!] Error fetching versions: {e.stderr}")
        return []

    return []


def is_version_quarantined(package_name, version, index_url=None):
    """
    Attempts to download the specific version to a temp folder to ensure
    the artifact is not quarantined/blocked by the registry.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "download",
            f"{package_name}=={version}",
            "--dest",
            temp_dir,
            "--no-deps",
        ]
        if index_url:
            cmd.extend(["--index-url", index_url])

        # Suppress output to keep the terminal clean, unless it fails
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            return False  # Success = Not Quarantined
        else:
            # Check if it was a 403 or 404 which usually implies blocking/quarantine
            return True


def main():
    parser = argparse.ArgumentParser(
        description="Find the latest non-quarantined version of a package."
    )
    parser.add_argument("package", help="The name of the package (e.g., rich)")
    parser.add_argument(
        "--url", help="The registry/PyPi index URL", default=None
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="How many versions to check (default: 5)",
    )

    args = parser.parse_args()

    # 1. Get List of Versions
    versions = get_available_versions(args.package, args.url)

    if not versions:
        print(
            f"[!] No versions found for {args.package}. Check your spelling or VPN/Network connection."
        )
        sys.exit(1)

    print(
        f"[*] Found {len(versions)} versions in metadata. Checking the latest {args.limit}..."
    )

    # 2. Iterate and Verify
    found_safe = False

    # We take the top N versions from the list
    candidates = versions[: args.limit]

    for ver in candidates:
        sys.stdout.write(f"    Checking version {ver}... ")
        sys.stdout.flush()

        quarantined = is_version_quarantined(args.package, ver, args.url)

        if not quarantined:
            print("OK (Downloadable)")
            print("\n" + "=" * 50)
            print(f"SUCCESS: Version {ver} is safe to use.")
            print("Run this command:")
            print(f"\n    poetry add {args.package}@{ver}")
            print("\n" + "=" * 50)
            found_safe = True
            break
        else:
            print("FAILED (Quarantined/Blocked)")

    if not found_safe:
        print("\n[!] Could not find a safe version in the latest candidates.")
        print("Try increasing the search limit with --limit 20")


if __name__ == "__main__":
    main()
