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
    return PyJWKClient(settings.oidc_jwks_url, cache_jwk_set=True, lifespan=300)


def require_hr(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if credentials is None:
        logger.warning("auth_denied reason=missing_token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход")
    try:
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
    if "HR" not in claims.get("realm_access", {}).get("roles", []):
        logger.warning("auth_denied reason=missing_hr_role")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нужна роль HR")
    return claims
