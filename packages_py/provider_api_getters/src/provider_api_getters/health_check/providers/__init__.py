"""
Per-provider health check modules.

Each module is a standalone script that can be run directly for debugging:
    python confluence_health_check.py
    python github_health_check.py
    etc.

These modules directly use:
- static_config for YAML configuration
- provider_api_getters for API token resolution
- fetch_client for HTTP requests with proxy/auth support
"""

from .confluence_health_check import check_confluence_health
from .jira_health_check import check_jira_health
from .github_health_check import check_github_health
from .figma_health_check import check_figma_health
from .gemini_openai_health_check import check_gemini_openai_health
from .rally_health_check import check_rally_health
from .saucelabs_health_check import check_saucelabs_health
from .sonar_health_check import check_sonar_health
from .akamai_health_check import check_akamai_health
from .postgres_health_check import check_postgres_health
from .redis_health_check import check_redis_health
from .elasticsearch_health_check import check_elasticsearch_health

__all__ = [
    "check_confluence_health",
    "check_jira_health",
    "check_github_health",
    "check_figma_health",
    "check_gemini_openai_health",
    "check_rally_health",
    "check_saucelabs_health",
    "check_sonar_health",
    "check_akamai_health",
    "check_postgres_health",
    "check_redis_health",
    "check_elasticsearch_health",
]
