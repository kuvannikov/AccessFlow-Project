from datetime import UTC, datetime, timedelta
from io import StringIO
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import auth
from app.logging_config import logger


def test_api_requires_a_token_and_hr_role(client):
    http, token = client
    assert http.get("/api/employees").status_code == 401
    assert (
        http.get(
            "/api/employees", headers={"Authorization": f"Bearer {token(roles=('EMPLOYEE',))}"}
        ).status_code
        == 403
    )
    assert (
        http.get("/api/employees", headers={"Authorization": f"Bearer {token()}"}).status_code
        == 200
    )


def test_me_uses_the_hr_guard_and_returns_the_token_name(client):
    http, token = client
    assert http.get("/api/me").status_code == 401
    assert (
        http.get("/api/me", headers={"Authorization": f"Bearer {token(roles=())}"}).status_code
        == 403
    )
    response = http.get("/api/me", headers={"Authorization": f"Bearer {token(name='Тестовый HR')}"})
    assert response.status_code == 200
    assert response.json() == {"name": "Тестовый HR"}


def test_api_rejects_bad_audience_issuer_and_expiry(client):
    http, token = client
    bad_tokens = [
        token(aud="other-api"),
        token(iss="http://other/realms/accessflow"),
        token(exp=datetime.now(UTC) - timedelta(seconds=1)),
    ]
    for value in bad_tokens:
        assert (
            http.get("/api/employees", headers={"Authorization": f"Bearer {value}"}).status_code
            == 401
        )


def test_api_rejects_tampered_signature(client):
    http, token = client
    value = token()
    altered = value[:-2] + ("AA" if value[-2:] != "AA" else "BB")
    assert (
        http.get("/api/employees", headers={"Authorization": f"Bearer {altered}"}).status_code
        == 401
    )


@pytest.mark.parametrize("claim", ["exp", "iat", "iss", "aud", "sub"])
def test_api_requires_each_identity_claim(client, monkeypatch, claim):
    http, token = client
    claims = jwt.decode(token(), options={"verify_signature": False})
    del claims[claim]
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(
        auth,
        "jwk_client",
        lambda: SimpleNamespace(
            get_signing_key_from_jwt=lambda _: SimpleNamespace(key=private_key.public_key())
        ),
    )
    value = jwt.encode(claims, private_key, algorithm="RS256")
    response = http.get("/api/employees", headers={"Authorization": f"Bearer {value}"})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "realm_access",
    [
        None,
        [],
        "HR",
        {"roles": "NOT_HR"},
        {"roles": None},
        {"roles": {"HR": True}},
        {"roles": ["HR", 1]},
    ],
)
def test_api_rejects_malformed_role_claims(client, realm_access):
    http, token = client
    response = http.get(
        "/api/employees",
        headers={"Authorization": f"Bearer {token(realm_access=realm_access)}"},
    )
    assert response.status_code == 401


def test_invalid_algorithm_is_rejected_without_requesting_jwks(client, monkeypatch):
    http, _ = client
    calls = []
    healthy_client = auth.jwk_client()

    def unexpected_client():
        calls.append(True)
        return healthy_client

    monkeypatch.setattr(auth, "jwk_client", unexpected_client)
    token = jwt.encode({"sub": "test-user"}, "local-test-key" * 4, algorithm="HS256")
    response = http.get("/api/employees", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert calls == []


def test_future_identity_claims_are_rejected(client):
    http, token = client
    future = datetime.now(UTC) + timedelta(minutes=1)
    for changes in [{"iat": future}, {"nbf": future}]:
        response = http.get(
            "/api/employees", headers={"Authorization": f"Bearer {token(**changes)}"}
        )
        assert response.status_code == 401


def test_jwks_outage_is_safe_and_authentication_recovers(client, monkeypatch):
    http, token = client
    healthy_client = auth.jwk_client()
    output_stream = StringIO()
    monkeypatch.setattr(logger.handlers[0], "stream", output_stream)

    def unavailable(_):
        raise jwt.PyJWKClientConnectionError("private-provider-marker")

    monkeypatch.setattr(
        auth, "jwk_client", lambda: SimpleNamespace(get_signing_key_from_jwt=unavailable)
    )
    value = token()
    response = http.get("/api/employees", headers={"Authorization": f"Bearer {value}"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Служба входа недоступна"}
    assert "private-provider-marker" not in response.text + output_stream.getvalue()
    assert value not in output_stream.getvalue()

    monkeypatch.setattr(auth, "jwk_client", lambda: healthy_client)
    assert (
        http.get("/api/employees", headers={"Authorization": f"Bearer {value}"}).status_code == 200
    )
