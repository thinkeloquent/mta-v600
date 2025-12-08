#!/usr/bin/env python3
"""Test all provider connections."""
from _base import run_all_tests

# All providers from server.*.yaml (excluding placeholders)
ALL_PROVIDERS = [
    "figma",
    "github",
    "jira",
    "confluence",
    "gemini",
    "openai",
    "saucelabs",
    "postgres",
    "redis",
    # Placeholders (will report not_implemented)
    "rally",
    "elasticsearch",
]

if __name__ == "__main__":
    run_all_tests(ALL_PROVIDERS)
