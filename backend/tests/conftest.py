from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import auth
from app.config import settings
from app.db import Base, get_session
from app.main import app


@pytest.fixture
def client(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    monkeypatch.setattr(
        auth,
        "jwk_client",
        lambda: SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=public_key)),
    )
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)

    def session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = session_override

    def make_token(roles=("HR",), **changes):
        now = datetime.now(UTC)
        claims = {
            "sub": "test-user",
            "iss": settings.oidc_issuer,
            "aud": settings.oidc_audience,
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "realm_access": {"roles": list(roles)},
        }
        claims.update(changes)
        return jwt.encode(claims, private_key, algorithm="RS256")

    with TestClient(app) as test_client:
        yield test_client, make_token
    app.dependency_overrides.clear()
    engine.dispose()
