"""Access tokens of the identity provider and the principal they authenticate."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWK, PyJWKClient, PyJWKClientError, PyJWKSetError

from accessflow.core.config import Settings
from accessflow.core.errors import DomainError, ProblemDefinition

ALGORITHM = "RS256"
REQUIRED_CLAIMS = ["exp", "iat", "iss", "aud", "sub"]
CLOCK_SKEW_SECONDS = 30
KEY_SET_LIFESPAN_SECONDS = 300
KEY_SET_TIMEOUT_SECONDS = 5
KEY_SET_REFRESH_COOLDOWN_SECONDS = 30
DISPLAY_NAME_CLAIMS = ("name", "preferred_username")


class InvalidAccessTokenError(Exception):
    """The token is malformed, expired or not issued for this API."""


class IdentityProviderUnavailableError(DomainError):
    """The signing keys of the identity provider cannot be loaded."""


PROVIDER_UNAVAILABLE = ProblemDefinition(
    503, "auth.provider_unavailable", "Identity provider unavailable"
)


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


@dataclass(frozen=True)
class Principal:
    subject: str
    display_name: str
    roles: frozenset[str]


def _display_name(claims: Mapping[str, Any]) -> str:
    for name in DISPLAY_NAME_CLAIMS:
        value = claims.get(name)
        if isinstance(value, str) and value.strip():
            return value
    raise InvalidAccessTokenError


def _realm_roles(claims: Mapping[str, Any]) -> frozenset[str]:
    # A user without realm roles is still authenticated; only a malformed claim is rejected.
    realm_access = claims.get("realm_access", {})
    roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else None
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        raise InvalidAccessTokenError
    return frozenset(roles)


def principal_from_claims(claims: Mapping[str, Any]) -> Principal:
    return Principal(
        subject=claims["sub"], display_name=_display_name(claims), roles=_realm_roles(claims)
    )


bearer_token = HTTPBearer()


def get_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_token)],
) -> Principal:
    """Authenticate the request by its bearer token; a missing header is rejected earlier."""
    verifier: AccessTokenVerifier = request.app.state.token_verifier
    try:
        return principal_from_claims(verifier.verify(credentials.credentials))
    except InvalidAccessTokenError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from None


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def require_role(role: str) -> Callable[[Principal], Principal]:
    """Dependency that admits only principals holding the given realm role."""

    def check_role(principal: PrincipalDep) -> Principal:
        if role not in principal.roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN)
        return principal

    return check_role
