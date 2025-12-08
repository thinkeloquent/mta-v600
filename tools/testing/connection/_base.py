#!/usr/bin/env python3
"""
Base module for connection testing.

Provides shared setup and utilities for provider connection tests.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path for local imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "packages_py" / "provider_api_getters" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages_py" / "app_static_config_yaml" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages_py" / "fetch_client" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages_py" / "fetch_proxy_dispatcher" / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# Load static config
from static_config import load_yaml_config, config as static_config

CONFIG_DIR = PROJECT_ROOT / "common" / "config"
load_yaml_config(config_dir=str(CONFIG_DIR))

# Import health checker
from provider_api_getters import ProviderHealthChecker, check_provider_connection


def print_result(result):
    """Print a provider connection result in a formatted way."""
    status_icons = {
        "connected": "\033[92m✓\033[0m",  # Green checkmark
        "error": "\033[91m✗\033[0m",       # Red X
        "not_implemented": "\033[93m○\033[0m",  # Yellow circle
    }

    icon = status_icons.get(result.status, "?")

    print(f"\n{'='*60}")
    print(f"{icon} Provider: {result.provider}")
    print(f"  Status: {result.status}")

    if result.latency_ms is not None:
        print(f"  Latency: {result.latency_ms:.2f}ms")

    if result.message:
        print(f"  Message: {result.message}")

    if result.error:
        print(f"  Error: \033[91m{result.error}\033[0m")

    print(f"  Timestamp: {result.timestamp}")
    print(f"{'='*60}\n")

    return result.status == "connected"


async def test_provider(provider_name: str) -> bool:
    """Test a single provider connection."""
    print(f"\nTesting connection to: {provider_name}")
    print("-" * 40)

    checker = ProviderHealthChecker(static_config)
    result = await checker.check(provider_name)

    return print_result(result)


async def test_all_providers(providers: list[str]) -> dict:
    """Test multiple providers and return summary."""
    results = {
        "connected": [],
        "error": [],
        "not_implemented": [],
    }

    for provider in providers:
        checker = ProviderHealthChecker(static_config)
        result = await checker.check(provider)
        print_result(result)
        results[result.status].append(provider)

    return results


def print_summary(results: dict):
    """Print a summary of all test results."""
    total = sum(len(v) for v in results.values())

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total providers tested: {total}")
    print(f"\033[92m✓ Connected:\033[0m {len(results['connected'])} - {', '.join(results['connected']) or 'None'}")
    print(f"\033[91m✗ Error:\033[0m {len(results['error'])} - {', '.join(results['error']) or 'None'}")
    print(f"\033[93m○ Not Implemented:\033[0m {len(results['not_implemented'])} - {', '.join(results['not_implemented']) or 'None'}")
    print("=" * 60 + "\n")


def run_single_test(provider_name: str):
    """Run a single provider test (entry point for individual scripts)."""
    success = asyncio.run(test_provider(provider_name))
    sys.exit(0 if success else 1)


def run_all_tests(providers: list[str]):
    """Run all provider tests (entry point for all_providers script)."""
    results = asyncio.run(test_all_providers(providers))
    print_summary(results)

    # Exit with error if any providers failed
    sys.exit(0 if len(results["error"]) == 0 else 1)
