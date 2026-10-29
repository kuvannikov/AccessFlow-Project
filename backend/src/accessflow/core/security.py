"""Verification of access tokens issued by the identity provider."""

from typing import Any

import jwt
from jwt import PyJWK, PyJWKClient, PyJWKClientError, PyJWKSetError

from accessflow.core.config import Settings

ALGORITHM = "RS256"
REQUIRED_CLAIMS = ["exp", "iat", "iss", "aud", "sub"]
CLOCK_SKEW_SECONDS = 30
KEY_SET_LIFESPAN_SECONDS = 300
KEY_SET_TIMEOUT_SECONDS = 5
KEY_SET_REFRESH_COOLDOWN_SECONDS = 30


class InvalidAccessTokenError(Exception):
    """The token is malformed, expired or not issued for this API."""


class IdentityProviderUnavailableError(Exception):
    """The signing keys of the identity provider cannot be loaded."""


class KeySetClient(PyJWKClient):
    """JWKS client that tells a failed key set download from an unknown key ID.

    PyJWKClient raises PyJWKClientError in both cases, but only the first one
    is a server-side failure.
    """

    def get_signing_keys(self, refresh: bool = False) -> list[PyJWK]:
        try:
            return super().get_signing_keys(refresh)
        # OSError and ValueError cover a connection reset while reading the
        # response and a body that is not JSON: PyJWKClient does not wrap them.
        except (PyJWKClientError, PyJWKSetError, OSError, ValueError) as error:
            raise IdentityProviderUnavailableError from error


class AccessTokenVerifier:
    def __init__(self, keys: KeySetClient, *, issuer: str, audience: str) -> None:
        self._keys = keys
        self._issuer = issuer
        self._audience = audience

    def verify(self, token: str) -> dict[str, Any]:
        """Return the claims of a valid access token.

        Raises InvalidAccessTokenError when the token must be rejected and
        IdentityProviderUnavailableError when the signing keys cannot be loaded.
        """
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as error:
            raise InvalidAccessTokenError from error
        key_id = header.get("kid")
        # Rejected before any key lookup, so a forged header costs no download.
        if header.get("alg") != ALGORITHM or not isinstance(key_id, str) or not key_id:
            raise InvalidAccessTokenError
        try:
            key = self._keys.get_signing_key(key_id)
            return jwt.decode(
                token,
                key,
                algorithms=[ALGORITHM],
                audience=self._audience,
                issuer=self._issuer,
                leeway=CLOCK_SKEW_SECONDS,
                options={"require": REQUIRED_CLAIMS},
            )
        except (PyJWKClientError, jwt.InvalidTokenError) as error:
            raise InvalidAccessTokenError from error


def create_token_verifier(settings: Settings) -> AccessTokenVerifier:
    keys = KeySetClient(
        str(settings.auth_jwks_url),
        lifespan=KEY_SET_LIFESPAN_SECONDS,
        timeout=KEY_SET_TIMEOUT_SECONDS,
        cooldown_duration=KEY_SET_REFRESH_COOLDOWN_SECONDS,
    )
    return AccessTokenVerifier(keys, issuer=settings.auth_issuer, audience=settings.auth_audience)
