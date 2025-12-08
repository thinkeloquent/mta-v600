"""
Cache-Control header parsing and utilities for RFC 7234 compliance.
"""
import time
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Tuple

from .types import CacheControlDirectives, CacheEntryMetadata, CacheFreshness


def parse_cache_control(header: Optional[str]) -> CacheControlDirectives:
    """Parse Cache-Control header into directives."""
    directives = CacheControlDirectives()

    if not header:
        return directives

    parts = [p.strip().lower() for p in header.split(",")]

    for part in parts:
        if "=" in part:
            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip()
        else:
            key = part.strip()
            value = None

        if key == "no-store":
            directives.no_store = True
        elif key == "no-cache":
            directives.no_cache = True
        elif key == "max-age" and value:
            try:
                directives.max_age = int(value)
            except ValueError:
                pass
        elif key == "s-maxage" and value:
            try:
                directives.s_maxage = int(value)
            except ValueError:
                pass
        elif key == "private":
            directives.private = True
        elif key == "public":
            directives.public = True
        elif key == "must-revalidate":
            directives.must_revalidate = True
        elif key == "proxy-revalidate":
            directives.proxy_revalidate = True
        elif key == "no-transform":
            directives.no_transform = True
        elif key == "stale-while-revalidate" and value:
            try:
                directives.stale_while_revalidate = int(value)
            except ValueError:
                pass
        elif key == "stale-if-error" and value:
            try:
                directives.stale_if_error = int(value)
            except ValueError:
                pass
        elif key == "immutable":
            directives.immutable = True

    return directives


def build_cache_control(directives: CacheControlDirectives) -> str:
    """Build Cache-Control header from directives."""
    parts: List[str] = []

    if directives.no_store:
        parts.append("no-store")
    if directives.no_cache:
        parts.append("no-cache")
    if directives.private:
        parts.append("private")
    if directives.public:
        parts.append("public")
    if directives.must_revalidate:
        parts.append("must-revalidate")
    if directives.proxy_revalidate:
        parts.append("proxy-revalidate")
    if directives.no_transform:
        parts.append("no-transform")
    if directives.immutable:
        parts.append("immutable")
    if directives.max_age is not None:
        parts.append(f"max-age={directives.max_age}")
    if directives.s_maxage is not None:
        parts.append(f"s-maxage={directives.s_maxage}")
    if directives.stale_while_revalidate is not None:
        parts.append(f"stale-while-revalidate={directives.stale_while_revalidate}")
    if directives.stale_if_error is not None:
        parts.append(f"stale-if-error={directives.stale_if_error}")

    return ", ".join(parts)


def extract_etag(headers: Dict[str, str]) -> Optional[str]:
    """Extract ETag from response headers."""
    etag = headers.get("etag") or headers.get("ETag")
    return etag.strip() if etag else None


def extract_last_modified(headers: Dict[str, str]) -> Optional[str]:
    """Extract Last-Modified from response headers."""
    last_modified = headers.get("last-modified") or headers.get("Last-Modified")
    return last_modified.strip() if last_modified else None


def parse_date_header(header: Optional[str]) -> Optional[float]:
    """Parse Date header to timestamp."""
    if not header:
        return None
    try:
        dt = parsedate_to_datetime(header)
        return dt.timestamp()
    except Exception:
        return None


def calculate_expiration(
    headers: Dict[str, str],
    directives: CacheControlDirectives,
    default_ttl_seconds: float = 0,
    max_ttl_seconds: float = 86400,
    now: Optional[float] = None,
) -> float:
    """Calculate expiration time based on Cache-Control and other headers."""
    if now is None:
        now = time.time()

    # If no-store, don't cache
    if directives.no_store:
        return now

    # Use s-maxage for shared caches (higher priority than max-age)
    if directives.s_maxage is not None:
        ttl = min(directives.s_maxage, max_ttl_seconds)
        return now + ttl

    # Use max-age
    if directives.max_age is not None:
        ttl = min(directives.max_age, max_ttl_seconds)
        return now + ttl

    # Try Expires header
    expires = headers.get("expires") or headers.get("Expires")
    if expires:
        expires_timestamp = parse_date_header(expires)
        if expires_timestamp:
            ttl = min(expires_timestamp - now, max_ttl_seconds)
            return now + max(0, ttl)

    # Use default TTL
    if default_ttl_seconds > 0:
        return now + min(default_ttl_seconds, max_ttl_seconds)

    # No caching
    return now


def determine_freshness(
    metadata: CacheEntryMetadata, now: Optional[float] = None
) -> CacheFreshness:
    """Determine freshness status of a cached response."""
    if now is None:
        now = time.time()

    expires_at = metadata.expires_at
    directives = metadata.directives

    # If immutable and not expired, always fresh
    if directives and directives.immutable and now < expires_at:
        return CacheFreshness.FRESH

    # Check if within freshness lifetime
    if now < expires_at:
        return CacheFreshness.FRESH

    # Check stale-while-revalidate window
    if directives and directives.stale_while_revalidate:
        stale_window = directives.stale_while_revalidate
        if now < expires_at + stale_window:
            return CacheFreshness.STALE

    # Check stale-if-error window
    if directives and directives.stale_if_error:
        stale_window = directives.stale_if_error
        if now < expires_at + stale_window:
            return CacheFreshness.STALE

    return CacheFreshness.EXPIRED


def is_cacheable_status(
    status_code: int,
    cacheable_statuses: Optional[List[int]] = None,
) -> bool:
    """Check if response is cacheable based on status code."""
    if cacheable_statuses is None:
        cacheable_statuses = [200, 203, 204, 206, 300, 301, 404, 405, 410, 414, 501]
    return status_code in cacheable_statuses


def is_cacheable_method(
    method: str,
    cacheable_methods: Optional[List[str]] = None,
) -> bool:
    """Check if request method is cacheable."""
    if cacheable_methods is None:
        cacheable_methods = ["GET", "HEAD"]
    return method.upper() in cacheable_methods


def should_cache(
    directives: CacheControlDirectives,
    respect_no_store: bool = True,
    respect_no_cache: bool = True,
    respect_private: bool = True,
) -> bool:
    """Check if response should be cached based on directives."""
    # no-store means never cache
    if respect_no_store and directives.no_store:
        return False

    # private means only store in private cache (browser)
    if respect_private and directives.private:
        return False

    return True


def needs_revalidation(
    metadata: CacheEntryMetadata,
    respect_no_cache: bool = True,
) -> bool:
    """Check if cached response needs revalidation."""
    # If no-cache directive, always revalidate
    if respect_no_cache and metadata.directives and metadata.directives.no_cache:
        return True

    # If must-revalidate and stale
    if metadata.directives and metadata.directives.must_revalidate:
        freshness = determine_freshness(metadata)
        if freshness != CacheFreshness.FRESH:
            return True

    return False


def parse_vary(header: Optional[str]) -> List[str]:
    """Parse Vary header into list of header names."""
    if not header:
        return []
    if header == "*":
        return ["*"]
    return [h.strip().lower() for h in header.split(",")]


def is_vary_uncacheable(vary: Optional[str]) -> bool:
    """Check if Vary header indicates uncacheable."""
    return vary == "*"


def extract_vary_headers(
    headers: Dict[str, str], vary: List[str]
) -> Dict[str, str]:
    """Extract headers needed for Vary matching."""
    result: Dict[str, str] = {}

    for key in vary:
        if key == "*":
            continue
        lower_key = key.lower()
        for k, v in headers.items():
            if k.lower() == lower_key:
                result[lower_key] = v
                break

    return result


def match_vary_headers(
    request_headers: Dict[str, str],
    cached_vary_headers: Dict[str, str],
) -> bool:
    """Check if request headers match cached Vary headers."""
    for key, value in cached_vary_headers.items():
        request_value = get_header_value(request_headers, key)
        if request_value != value:
            return False
    return True


def get_header_value(
    headers: Dict[str, str], key: str
) -> Optional[str]:
    """Get header value case-insensitively."""
    lower_key = key.lower()
    for k, v in headers.items():
        if k.lower() == lower_key:
            return v
    return None


def normalize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Normalize headers to lowercase keys."""
    return {k.lower(): v for k, v in headers.items()}
