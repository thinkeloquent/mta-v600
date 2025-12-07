"""
DNS warmup utilities for fetch_client.

Pre-resolves hostnames to populate DNS cache and reduce first-request latency.
"""
import asyncio
import socket
import time
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse


@dataclass
class DnsWarmupResult:
    """DNS warmup result."""

    hostname: str
    addresses: List[str]
    duration: float
    success: bool
    error: Optional[Exception] = None


async def warmup_dns(hostname: str) -> DnsWarmupResult:
    """
    Warm up DNS for a single hostname.

    Args:
        hostname: The hostname to resolve.

    Returns:
        DnsWarmupResult with resolution details.
    """
    start = time.time()

    try:
        loop = asyncio.get_event_loop()
        # Run DNS lookup in thread pool
        addresses = await loop.run_in_executor(
            None,
            lambda: socket.getaddrinfo(hostname, 443, socket.AF_UNSPEC, socket.SOCK_STREAM),
        )
        duration = time.time() - start

        # Extract unique IP addresses
        ip_addresses = list(set(addr[4][0] for addr in addresses))

        return DnsWarmupResult(
            hostname=hostname,
            addresses=ip_addresses,
            duration=duration,
            success=True,
        )
    except Exception as error:
        duration = time.time() - start
        return DnsWarmupResult(
            hostname=hostname,
            addresses=[],
            duration=duration,
            success=False,
            error=error,
        )


async def warmup_dns_many(hostnames: List[str]) -> List[DnsWarmupResult]:
    """
    Warm up DNS for multiple hostnames in parallel.

    Args:
        hostnames: Array of hostnames to resolve.

    Returns:
        List of warmup results.
    """
    return await asyncio.gather(*[warmup_dns(h) for h in hostnames])


def extract_hostname(url: str) -> str:
    """
    Extract hostname from URL.

    Args:
        url: URL string.

    Returns:
        Hostname string.
    """
    parsed = urlparse(url)
    return parsed.hostname or ""


async def warmup_dns_for_url(url: str) -> DnsWarmupResult:
    """
    Warm up DNS for a URL.

    Args:
        url: URL string.

    Returns:
        DnsWarmupResult.
    """
    hostname = extract_hostname(url)
    return await warmup_dns(hostname)


def warmup_dns_sync(hostname: str) -> DnsWarmupResult:
    """
    Synchronous DNS warmup for a single hostname.

    Args:
        hostname: The hostname to resolve.

    Returns:
        DnsWarmupResult with resolution details.
    """
    start = time.time()

    try:
        addresses = socket.getaddrinfo(hostname, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        duration = time.time() - start

        # Extract unique IP addresses
        ip_addresses = list(set(addr[4][0] for addr in addresses))

        return DnsWarmupResult(
            hostname=hostname,
            addresses=ip_addresses,
            duration=duration,
            success=True,
        )
    except Exception as error:
        duration = time.time() - start
        return DnsWarmupResult(
            hostname=hostname,
            addresses=[],
            duration=duration,
            success=False,
            error=error,
        )
