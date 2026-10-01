from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientConnectionError

from app.config import settings
from app.logging_config import logger

bearer = HTTPBearer(auto_error=False)


@lru_cache
def jwk_client() -> PyJWKClient:
    return PyJWKClient(settings.oidc_jwks_url, cache_jwk_set=True, lifespan=300, timeout=5)


def require_hr(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if credentials is None:
        logger.warning("auth_denied reason=missing_token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход")
    try:
        if jwt.get_unverified_header(credentials.credentials).get("alg") != "RS256":
            raise jwt.InvalidAlgorithmError("Only RS256 access tokens are accepted")
        key = jwk_client().get_signing_key_from_jwt(credentials.credentials).key
        claims = jwt.decode(
            credentials.credentials,
            key,
            algorithms=["RS256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            leeway=0,
        )
    except PyJWKClientConnectionError as exc:
        logger.warning("keycloak_keys_unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Служба входа недоступна"
        ) from exc
    except (jwt.PyJWTError, ValueError) as exc:
        logger.warning("auth_denied reason=invalid_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен"
        ) from exc
    realm_access = claims.get("realm_access", {})
    roles = realm_access.get("roles", []) if isinstance(realm_access, dict) else None
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        logger.warning("auth_denied reason=invalid_role_claims")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен"
        )
    if "HR" not in roles:
        logger.warning("auth_denied reason=missing_hr_role")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нужна роль HR")
    return claims
