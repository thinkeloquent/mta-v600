"""
Tests for dns_warmup.py
Logic testing: Happy Path, Error Path, Path coverage
"""
import pytest
from unittest.mock import patch, MagicMock

from fetch_client.dns_warmup import (
    warmup_dns,
    warmup_dns_many,
    extract_hostname,
    warmup_dns_for_url,
)


class TestWarmupDns:
    """Tests for warmup_dns function."""

    # Happy Path: successful resolution
    @pytest.mark.asyncio
    async def test_warmup_dns_success(self):
        mock_result = [
            (2, 1, 6, "", ("192.168.1.1", 443)),
            (2, 1, 6, "", ("192.168.1.2", 443)),
        ]
        with patch("socket.getaddrinfo", return_value=mock_result):
            result = await warmup_dns("api.example.com")

        assert result.success is True
        assert result.hostname == "api.example.com"
        assert len(result.addresses) > 0
        assert result.error is None

    # Path: measures duration
    @pytest.mark.asyncio
    async def test_warmup_dns_measures_duration(self):
        mock_result = [(2, 1, 6, "", ("127.0.0.1", 443))]
        with patch("socket.getaddrinfo", return_value=mock_result):
            result = await warmup_dns("localhost")

        assert result.duration >= 0

    # Error Path: DNS resolution failure
    @pytest.mark.asyncio
    async def test_warmup_dns_failure(self):
        with patch("socket.getaddrinfo", side_effect=Exception("ENOTFOUND")):
            result = await warmup_dns("nonexistent.invalid")

        assert result.success is False
        assert result.addresses == []
        assert result.error is not None
        assert "ENOTFOUND" in str(result.error)

    # Path: duration measured on failure
    @pytest.mark.asyncio
    async def test_warmup_dns_duration_on_failure(self):
        with patch("socket.getaddrinfo", side_effect=Exception("timeout")):
            result = await warmup_dns("slow.example.com")

        assert result.duration >= 0

    # Path: deduplicates addresses
    @pytest.mark.asyncio
    async def test_warmup_dns_dedupe(self):
        mock_result = [
            (2, 1, 6, "", ("192.168.1.1", 443)),
            (2, 1, 6, "", ("192.168.1.1", 443)),  # duplicate
        ]
        with patch("socket.getaddrinfo", return_value=mock_result):
            result = await warmup_dns("api.example.com")

        # Should be deduplicated
        assert len(set(result.addresses)) == len(result.addresses)


class TestWarmupDnsMany:
    """Tests for warmup_dns_many function."""

    # Path: multiple hostnames resolved in parallel
    @pytest.mark.asyncio
    async def test_warmup_dns_many_parallel(self):
        mock_result = [(2, 1, 6, "", ("1.1.1.1", 443))]
        with patch("socket.getaddrinfo", return_value=mock_result):
            results = await warmup_dns_many(["host1.com", "host2.com"])

        assert len(results) == 2
        assert results[0].hostname == "host1.com"
        assert results[1].hostname == "host2.com"

    # Error Path: partial failure
    @pytest.mark.asyncio
    async def test_warmup_dns_many_partial_failure(self):
        def mock_getaddrinfo(hostname, port, *args, **kwargs):
            if "bad" in hostname:
                raise Exception("ENOTFOUND")
            return [(2, 1, 6, "", ("1.1.1.1", 443))]

        with patch("socket.getaddrinfo", side_effect=mock_getaddrinfo):
            results = await warmup_dns_many(["good.com", "bad.invalid"])

        assert results[0].success is True
        assert results[1].success is False

    # Boundary: empty array
    @pytest.mark.asyncio
    async def test_warmup_dns_many_empty(self):
        results = await warmup_dns_many([])
        assert results == []

    # Path: single hostname
    @pytest.mark.asyncio
    async def test_warmup_dns_many_single(self):
        mock_result = [(2, 1, 6, "", ("1.1.1.1", 443))]
        with patch("socket.getaddrinfo", return_value=mock_result):
            results = await warmup_dns_many(["single.com"])

        assert len(results) == 1
        assert results[0].hostname == "single.com"


class TestExtractHostname:
    """Tests for extract_hostname function."""

    # Decision: string URL
    def test_extract_hostname_from_url(self):
        result = extract_hostname("https://api.example.com/path")
        assert result == "api.example.com"

    # Path: URL with port
    def test_extract_hostname_with_port(self):
        result = extract_hostname("https://api.example.com:8080/path")
        assert result == "api.example.com"

    # Path: URL with subdomain
    def test_extract_hostname_subdomain(self):
        result = extract_hostname("https://sub.api.example.com")
        assert result == "sub.api.example.com"

    # Path: localhost
    def test_extract_hostname_localhost(self):
        result = extract_hostname("http://localhost:3000")
        assert result == "localhost"

    # Boundary: empty URL
    def test_extract_hostname_empty(self):
        result = extract_hostname("")
        assert result == ""


class TestWarmupDnsForUrl:
    """Tests for warmup_dns_for_url function."""

    # Path: integration of extract + warmup
    @pytest.mark.asyncio
    async def test_warmup_dns_for_url(self):
        mock_result = [(2, 1, 6, "", ("93.184.216.34", 443))]
        with patch("socket.getaddrinfo", return_value=mock_result):
            result = await warmup_dns_for_url("https://example.com/api/users")

        assert result.hostname == "example.com"
        assert result.success is True

    # Error Path: DNS failure propagates
    @pytest.mark.asyncio
    async def test_warmup_dns_for_url_failure(self):
        with patch("socket.getaddrinfo", side_effect=Exception("ENOTFOUND")):
            result = await warmup_dns_for_url("https://nonexistent.invalid")

        assert result.success is False
