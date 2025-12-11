"""
Auth Header Factory - RFC-compliant Authorization header construction.

This module provides a factory pattern for creating HTTP Authorization headers
following RFC 7617 (Basic), RFC 6750 (Bearer), RFC 7616 (Digest), and AWS Signature v4.

Supported auth schemes:
- Basic (user:password, email:token, user:token)
- Bearer (PAT, OAuth, JWT)
- X-Api-Key (custom header)
- Custom header (any header name/value)
- AWS Signature v4 (HMAC)
- Digest (RFC 7616)
"""

import base64
import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _mask_user(value: str, visible_chars: int = 3) -> str:
    """Mask a username/email for logging, preserving only first visible_chars."""
    if not value:
        return "<empty>"
    if len(value) <= visible_chars:
        return "*" * len(value)
    return f"{value[:visible_chars]}***"


class AuthScheme(Enum):
    """Auth scheme enumeration."""

    # Basic variants (RFC 7617)
    BASIC_USER_PASS = "basic_user_pass"
    BASIC_EMAIL_TOKEN = "basic_email_token"
    BASIC_USER_TOKEN = "basic_user_token"

    # Bearer variants (RFC 6750)
    BEARER_PAT = "bearer_pat"
    BEARER_OAUTH = "bearer_oauth"
    BEARER_JWT = "bearer_jwt"

    # API Key (custom header)
    X_API_KEY = "x_api_key"

    # Custom header
    CUSTOM_HEADER = "custom_header"

    # AWS Signature v4
    AWS_SIGNATURE = "aws_signature"

    # Digest (RFC 7616)
    DIGEST = "digest"


# Mapping from config auth types to factory methods
CONFIG_AUTH_TYPE_MAP: Dict[str, AuthScheme] = {
    "bearer": AuthScheme.BEARER_PAT,
    "basic": AuthScheme.BASIC_USER_TOKEN,
    "x-api-key": AuthScheme.X_API_KEY,
    "custom": AuthScheme.CUSTOM_HEADER,
    "aws_signature": AuthScheme.AWS_SIGNATURE,
    "digest": AuthScheme.DIGEST,
}


@dataclass
class AuthHeader:
    """Result of auth header construction."""

    header_name: str
    header_value: str
    scheme: AuthScheme

    def __post_init__(self) -> None:
        """Log header creation."""
        logger.debug(
            f"AuthHeader.__post_init__: Creating header "
            f"name='{self.header_name}', scheme='{self.scheme.value}', "
            f"value_length={len(self.header_value) if self.header_value else 0}"
        )

    def to_dict(self) -> Dict[str, str]:
        """Convert to dict for use in requests headers."""
        return {self.header_name: self.header_value}

    def __str__(self) -> str:
        """String representation with masked value for logging."""
        masked_value = (
            self.header_value[:10] + "***"
            if len(self.header_value) > 10
            else "***"
        )
        return f"{self.header_name}: {masked_value}"


class AuthHeaderFactory:
    """Factory for creating RFC-compliant Authorization headers."""

    @staticmethod
    def create(scheme: AuthScheme, **credentials: Any) -> AuthHeader:
        """
        Create an auth header using a scheme and credentials.

        Args:
            scheme: Auth scheme from AuthScheme enum
            **credentials: Credentials (scheme-specific)

        Returns:
            AuthHeader instance
        """
        logger.debug(f"AuthHeaderFactory.create: Creating header for scheme='{scheme.value}'")

        if scheme in (
            AuthScheme.BASIC_USER_PASS,
            AuthScheme.BASIC_EMAIL_TOKEN,
            AuthScheme.BASIC_USER_TOKEN,
        ):
            user = (
                credentials.get("user")
                or credentials.get("email")
                or credentials.get("username")
            )
            secret = (
                credentials.get("secret")
                or credentials.get("password")
                or credentials.get("token")
                or credentials.get("api_key")
            )
            return AuthHeaderFactory.create_basic(user, secret)

        elif scheme in (
            AuthScheme.BEARER_PAT,
            AuthScheme.BEARER_OAUTH,
            AuthScheme.BEARER_JWT,
        ):
            token = credentials.get("token") or credentials.get("api_key")
            return AuthHeaderFactory.create_bearer(token)

        elif scheme == AuthScheme.X_API_KEY:
            key = credentials.get("key") or credentials.get("api_key")
            header_name = credentials.get("header_name")
            return AuthHeaderFactory.create_api_key(key, header_name)

        elif scheme == AuthScheme.CUSTOM_HEADER:
            header_name = credentials.get("header_name")
            value = credentials.get("value") or credentials.get("api_key")
            return AuthHeaderFactory.create_custom(header_name, value)

        elif scheme == AuthScheme.AWS_SIGNATURE:
            return AuthHeaderFactory.create_aws_signature(**credentials)

        elif scheme == AuthScheme.DIGEST:
            return AuthHeaderFactory.create_digest(**credentials)

        else:
            logger.warning(
                f"AuthHeaderFactory.create: Unknown scheme '{scheme}', defaulting to Bearer"
            )
            token = credentials.get("token") or credentials.get("api_key")
            return AuthHeaderFactory.create_bearer(token)

    @staticmethod
    def create_basic(user: str, secret: str) -> AuthHeader:
        """
        Create a Basic auth header (RFC 7617).

        Encodes credentials as Base64(user:secret).
        Works for all Basic variants:
        - username:password
        - email:token (Atlassian products)
        - username:token (Jenkins, GitHub Enterprise)

        Args:
            user: Username, email, or identifier
            secret: Password, token, or API key

        Returns:
            AuthHeader instance

        Raises:
            ValueError: If user or secret is missing
        """
        logger.debug(
            f"AuthHeaderFactory.create_basic: Creating Basic auth "
            f"user='{_mask_user(user)}', secret_length={len(secret) if secret else 0}"
        )

        if not user or not secret:
            logger.error("AuthHeaderFactory.create_basic: Missing user or secret")
            raise ValueError("Basic auth requires both user and secret")

        # RFC 7617: Base64 encode "user:secret"
        credentials = f"{user}:{secret}"
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")

        logger.debug(
            f"AuthHeaderFactory.create_basic: Encoded credentials "
            f"(input_length={len(credentials)}, encoded_length={len(encoded)})"
        )

        return AuthHeader(
            header_name="Authorization",
            header_value=f"Basic {encoded}",
            scheme=AuthScheme.BASIC_USER_PASS,
        )

    @staticmethod
    def create_bearer(token: str) -> AuthHeader:
        """
        Create a Bearer auth header (RFC 6750).

        Used for:
        - Personal Access Tokens (PAT)
        - OAuth 2.0 tokens
        - JWT tokens

        Args:
            token: Bearer token

        Returns:
            AuthHeader instance

        Raises:
            ValueError: If token is missing
        """
        logger.debug(
            f"AuthHeaderFactory.create_bearer: Creating Bearer auth "
            f"token_length={len(token) if token else 0}"
        )

        if not token:
            logger.error("AuthHeaderFactory.create_bearer: Missing token")
            raise ValueError("Bearer auth requires a token")

        return AuthHeader(
            header_name="Authorization",
            header_value=f"Bearer {token}",
            scheme=AuthScheme.BEARER_PAT,
        )

    @staticmethod
    def create_api_key(key: str, header_name: Optional[str] = None) -> AuthHeader:
        """
        Create an X-Api-Key header.

        Common in simpler public APIs (Google Maps, Weather APIs).

        Args:
            key: API key
            header_name: Custom header name (default: 'X-Api-Key')

        Returns:
            AuthHeader instance

        Raises:
            ValueError: If key is missing
        """
        header_name = header_name or "X-Api-Key"

        logger.debug(
            f"AuthHeaderFactory.create_api_key: Creating API key auth "
            f"header_name='{header_name}', key_length={len(key) if key else 0}"
        )

        if not key:
            logger.error("AuthHeaderFactory.create_api_key: Missing API key")
            raise ValueError("API key auth requires a key")

        return AuthHeader(
            header_name=header_name,
            header_value=key,
            scheme=AuthScheme.X_API_KEY,
        )

    @staticmethod
    def create_custom(header_name: str, value: str) -> AuthHeader:
        """
        Create a custom header.

        Used for provider-specific headers like X-Figma-Token.

        Args:
            header_name: Header name
            value: Header value

        Returns:
            AuthHeader instance

        Raises:
            ValueError: If header_name or value is missing
        """
        logger.debug(
            f"AuthHeaderFactory.create_custom: Creating custom header "
            f"name='{header_name}', value_length={len(value) if value else 0}"
        )

        if not header_name or not value:
            logger.error("AuthHeaderFactory.create_custom: Missing header_name or value")
            raise ValueError("Custom header requires both header_name and value")

        return AuthHeader(
            header_name=header_name,
            header_value=value,
            scheme=AuthScheme.CUSTOM_HEADER,
        )

    @staticmethod
    def create_aws_signature(
        access_key_id: str,
        secret_access_key: str,
        region: str,
        service: str,
        method: str,
        url: str,
        body: str = "",
        headers: Optional[Dict[str, str]] = None,
        session_token: Optional[str] = None,
        **_: Any,
    ) -> AuthHeader:
        """
        Create an AWS Signature v4 header.

        Implements AWS4-HMAC-SHA256 signing for AWS services.

        Args:
            access_key_id: AWS Access Key ID
            secret_access_key: AWS Secret Access Key
            region: AWS region (e.g., 'us-east-1')
            service: AWS service (e.g., 's3', 'execute-api')
            method: HTTP method (GET, POST, etc.)
            url: Full request URL
            body: Request body (default: empty string)
            headers: Additional headers to sign (default: empty dict)
            session_token: AWS session token for temp credentials (optional)

        Returns:
            AuthHeader instance

        Raises:
            ValueError: If required parameters are missing
        """
        logger.debug(
            f"AuthHeaderFactory.create_aws_signature: Creating AWS signature "
            f"region='{region}', service='{service}', method='{method}'"
        )

        if not all([access_key_id, secret_access_key, region, service, method, url]):
            logger.error("AuthHeaderFactory.create_aws_signature: Missing required parameters")
            raise ValueError(
                "AWS signature requires access_key_id, secret_access_key, "
                "region, service, method, and url"
            )

        headers = headers or {}

        parsed_url = urlparse(url)
        host = parsed_url.netloc
        path = parsed_url.path or "/"
        query = parsed_url.query

        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        # Helper functions
        def sha256_hash(data: str) -> str:
            return hashlib.sha256(data.encode("utf-8")).hexdigest()

        def sign(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        # Step 1: Create canonical request
        signed_headers = "host;x-amz-date"
        payload_hash = sha256_hash(body)

        canonical_uri = path if path else "/"
        canonical_querystring = query if query else ""

        canonical_headers = f"host:{host}\nx-amz-date:{amz_date}\n"

        canonical_request = "\n".join(
            [
                method.upper(),
                canonical_uri,
                canonical_querystring,
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )

        logger.debug(
            f"AuthHeaderFactory.create_aws_signature: Canonical request created "
            f"(length={len(canonical_request)})"
        )

        # Step 2: Create string to sign
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"

        string_to_sign = "\n".join(
            [
                algorithm,
                amz_date,
                credential_scope,
                sha256_hash(canonical_request),
            ]
        )

        # Step 3: Calculate signature
        k_date = sign(f"AWS4{secret_access_key}".encode("utf-8"), date_stamp)
        k_region = sign(k_date, region)
        k_service = sign(k_region, service)
        k_signing = sign(k_service, "aws4_request")

        signature = hmac.new(
            k_signing, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        # Step 4: Build authorization header
        authorization_header = (
            f"{algorithm} "
            f"Credential={access_key_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        logger.debug("AuthHeaderFactory.create_aws_signature: AWS signature created successfully")

        return AuthHeader(
            header_name="Authorization",
            header_value=authorization_header,
            scheme=AuthScheme.AWS_SIGNATURE,
        )

    @staticmethod
    def create_digest(
        username: str,
        password: str,
        realm: str,
        nonce: str,
        uri: str,
        method: str,
        qop: str = "auth",
        nc: str = "00000001",
        cnonce: Optional[str] = None,
        opaque: Optional[str] = None,
        algorithm: str = "MD5",
        **_: Any,
    ) -> AuthHeader:
        """
        Create a Digest auth header (RFC 7616).

        Used for challenge-response authentication.
        Note: This generates the response to a server challenge.

        Args:
            username: Username
            password: Password
            realm: Server realm from challenge
            nonce: Server nonce from challenge
            uri: Request URI
            method: HTTP method
            qop: Quality of protection (default: 'auth')
            nc: Nonce count (default: '00000001')
            cnonce: Client nonce (generated if not provided)
            opaque: Opaque value from server (optional)
            algorithm: Hash algorithm - 'MD5' or 'SHA-256' (default: 'MD5')

        Returns:
            AuthHeader instance

        Raises:
            ValueError: If required parameters are missing
        """
        logger.debug(
            f"AuthHeaderFactory.create_digest: Creating Digest auth "
            f"username='{username}', realm='{realm}', uri='{uri}', method='{method}'"
        )

        if not all([username, password, realm, nonce, uri, method]):
            logger.error("AuthHeaderFactory.create_digest: Missing required parameters")
            raise ValueError(
                "Digest auth requires username, password, realm, nonce, uri, and method"
            )

        # Generate client nonce if not provided
        client_nonce = cnonce or secrets.token_hex(8)

        # Hash function based on algorithm
        def compute_hash(data: str) -> str:
            if algorithm.upper() == "SHA-256":
                return hashlib.sha256(data.encode("utf-8")).hexdigest()
            return hashlib.md5(data.encode("utf-8")).hexdigest()

        # Calculate HA1 = hash(username:realm:password)
        ha1 = compute_hash(f"{username}:{realm}:{password}")

        # Calculate HA2 = hash(method:uri)
        ha2 = compute_hash(f"{method}:{uri}")

        # Calculate response
        if qop:
            # RFC 2617 with qop
            response = compute_hash(f"{ha1}:{nonce}:{nc}:{client_nonce}:{qop}:{ha2}")
        else:
            # RFC 2069 (legacy, no qop)
            response = compute_hash(f"{ha1}:{nonce}:{ha2}")

        # Build Digest header value
        parts = [
            f'username="{username}"',
            f'realm="{realm}"',
            f'nonce="{nonce}"',
            f'uri="{uri}"',
            f'response="{response}"',
        ]

        if qop:
            parts.append(f"qop={qop}")
            parts.append(f"nc={nc}")
            parts.append(f'cnonce="{client_nonce}"')

        if opaque:
            parts.append(f'opaque="{opaque}"')

        if algorithm and algorithm.upper() != "MD5":
            parts.append(f"algorithm={algorithm}")

        header_value = f"Digest {', '.join(parts)}"

        logger.debug("AuthHeaderFactory.create_digest: Digest auth header created successfully")

        return AuthHeader(
            header_name="Authorization",
            header_value=header_value,
            scheme=AuthScheme.DIGEST,
        )

    @staticmethod
    def from_api_key_result(api_key_result: Any) -> AuthHeader:
        """
        Create an auth header from an existing ApiKeyResult.

        Bridge method for integrating with existing provider implementations.
        Supports all extended auth types:
        - Basic family: basic, basic_email_token, basic_token, basic_email
        - Bearer family: bearer, bearer_oauth, bearer_jwt, bearer_*_token, bearer_*_password
        - Custom: x-api-key, custom, custom_header

        Args:
            api_key_result: ApiKeyResult instance with api_key, auth_type,
                           header_name, and optional username/email

        Returns:
            AuthHeader instance
        """
        logger.debug(
            f"AuthHeaderFactory.from_api_key_result: Creating header from ApiKeyResult "
            f"auth_type='{api_key_result.auth_type}', "
            f"has_api_key={api_key_result.api_key is not None}"
        )

        api_key = api_key_result.api_key
        auth_type = api_key_result.auth_type
        header_name = getattr(api_key_result, "header_name", None)
        username = getattr(api_key_result, "username", None)
        email = getattr(api_key_result, "email", None)
        raw_api_key = getattr(api_key_result, "raw_api_key", None)

        # Define auth type families
        basic_types = {"basic", "basic_email_token", "basic_token", "basic_email"}
        bearer_types = {
            "bearer", "bearer_oauth", "bearer_jwt",
            "bearer_username_token", "bearer_username_password",
            "bearer_email_token", "bearer_email_password",
        }

        # === Basic Auth Family ===
        if auth_type in basic_types:
            # If api_key is already "Basic <encoded>", use it directly
            if api_key and api_key.startswith("Basic "):
                logger.debug(
                    f"AuthHeaderFactory.from_api_key_result: api_key is pre-encoded Basic auth"
                )
                return AuthHeader(
                    header_name="Authorization",
                    header_value=api_key,
                    scheme=AuthScheme.BASIC_USER_PASS,
                )

            # Otherwise, encode from raw credentials
            identifier = email or username
            if not identifier:
                logger.warning(
                    f"AuthHeaderFactory.from_api_key_result: {auth_type} auth without "
                    f"identifier (email/username), falling back to Bearer"
                )
                return AuthHeaderFactory.create_bearer(api_key or raw_api_key or "")

            secret = raw_api_key or api_key or ""
            return AuthHeaderFactory.create_basic(identifier, secret)

        # === Bearer Auth Family ===
        if auth_type in bearer_types:
            # If api_key is already "Bearer <value>", use it directly
            if api_key and api_key.startswith("Bearer "):
                logger.debug(
                    f"AuthHeaderFactory.from_api_key_result: api_key is pre-encoded Bearer auth"
                )
                return AuthHeader(
                    header_name="Authorization",
                    header_value=api_key,
                    scheme=AuthScheme.BEARER_PAT,
                )

            # For bearer with credentials that need base64 encoding
            if auth_type in (
                "bearer_username_token", "bearer_username_password",
                "bearer_email_token", "bearer_email_password",
            ):
                identifier = email if "email" in auth_type else username
                secret = raw_api_key or api_key or ""
                if identifier and secret:
                    # Encode as Bearer base64(identifier:secret)
                    import base64
                    credentials = f"{identifier}:{secret}"
                    encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
                    return AuthHeader(
                        header_name="Authorization",
                        header_value=f"Bearer {encoded}",
                        scheme=AuthScheme.BEARER_PAT,
                    )

            # Default bearer - use token as-is
            token = api_key or raw_api_key or ""
            return AuthHeaderFactory.create_bearer(token)

        # === X-API-Key ===
        if auth_type == "x-api-key":
            return AuthHeaderFactory.create_api_key(api_key or raw_api_key or "", header_name or "X-Api-Key")

        # === Custom Header ===
        if auth_type in ("custom", "custom_header"):
            if not header_name:
                logger.warning(
                    "AuthHeaderFactory.from_api_key_result: Custom auth without header_name, "
                    "using X-Custom-Token"
                )
                return AuthHeaderFactory.create_custom("X-Custom-Token", api_key or raw_api_key or "")
            return AuthHeaderFactory.create_custom(header_name, api_key or raw_api_key or "")

        # === Unknown - default to Bearer ===
        logger.warning(
            f"AuthHeaderFactory.from_api_key_result: Unknown auth_type '{auth_type}', "
            "defaulting to Bearer"
        )
        return AuthHeaderFactory.create_bearer(api_key or raw_api_key or "")
