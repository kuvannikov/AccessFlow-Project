import contextlib
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from jwt import PyJWKClient, PyJWKClientConnectionError
from time_machine import TimeMachineFixture

from accessflow.core.config import Settings
from accessflow.core.security import (
    AccessTokenVerifier,
    IdentityProviderUnavailableError,
    InvalidAccessTokenError,
    KeySetClient,
    Principal,
    create_key_set_client,
    create_token_verifier,
    principal_from_claims,
)
from tests.identity import ISSUER, JwksServer, SigningKey, access_claims, with_jwks_url

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
ISSUED_AT = int(NOW.timestamp())


@pytest.fixture(autouse=True)
def frozen_time(time_machine: TimeMachineFixture) -> None:
    time_machine.move_to(NOW, tick=False)


@pytest.fixture
def claims() -> dict[str, Any]:
    return access_claims(ISSUED_AT)


@pytest.fixture
def verifier(auth_settings: Settings) -> AccessTokenVerifier:
    return create_token_verifier(auth_settings)


def sign_with(algorithm: str, claims: dict[str, Any], signing_key: SigningKey) -> str:
    key: Any
    match algorithm:
        case "none":
            key = ""
        case "HS256":
            key = secrets.token_bytes(32)
        case "ES256":
            key = ec.generate_private_key(ec.SECP256R1())
        case _:
            return signing_key.sign(claims, algorithm=algorithm)
    return jwt.encode(claims, key, algorithm=algorithm, headers={"kid": signing_key.kid})


@pytest.mark.parametrize("audience", ["accessflow-api", ["account", "accessflow-api"]])
def test_accepts_valid_token(
    verifier: AccessTokenVerifier,
    signing_key: SigningKey,
    claims: dict[str, Any],
    audience: str | list[str],
) -> None:
    claims["aud"] = audience

    assert verifier.verify(signing_key.sign(claims)) == claims


def test_caches_key_set(
    verifier: AccessTokenVerifier,
    jwks_server: JwksServer,
    signing_key: SigningKey,
    claims: dict[str, Any],
) -> None:
    for _ in range(3):
        verifier.verify(signing_key.sign(claims))

    assert jwks_server.requests == 1


@pytest.mark.parametrize("algorithm", ["none", "HS256", "RS512", "PS256", "ES256"])
def test_rejects_other_algorithm_without_key_lookup(
    verifier: AccessTokenVerifier,
    jwks_server: JwksServer,
    signing_key: SigningKey,
    claims: dict[str, Any],
    algorithm: str,
) -> None:
    token = sign_with(algorithm, claims, signing_key)

    with pytest.raises(InvalidAccessTokenError):
        verifier.verify(token)
    assert jwks_server.requests == 0


def test_rejects_token_without_key_id_without_key_lookup(
    verifier: AccessTokenVerifier,
    jwks_server: JwksServer,
    signing_key: SigningKey,
    claims: dict[str, Any],
) -> None:
    token = jwt.encode(claims, signing_key.private_key, algorithm="RS256")

    with pytest.raises(InvalidAccessTokenError):
        verifier.verify(token)
    assert jwks_server.requests == 0


@pytest.mark.parametrize("token", ["", "not-a-token", "a.b.c", "e30.e30."])
def test_rejects_malformed_token(verifier: AccessTokenVerifier, token: str) -> None:
    with pytest.raises(InvalidAccessTokenError):
        verifier.verify(token)


def test_rejects_signature_of_another_key(
    verifier: AccessTokenVerifier, signing_key: SigningKey, claims: dict[str, Any]
) -> None:
    forged = jwt.encode(
        claims, SigningKey().private_key, algorithm="RS256", headers={"kid": signing_key.kid}
    )

    with pytest.raises(InvalidAccessTokenError):
        verifier.verify(forged)


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"iss": "https://id.invalid/realms/other"}, id="other issuer"),
        pytest.param({"iss": f"{ISSUER}/"}, id="issuer with trailing slash"),
        pytest.param({"aud": "account"}, id="other audience"),
        pytest.param({"aud": ["account", "accessflow-web"]}, id="audience list without api"),
        pytest.param({"exp": ISSUED_AT - 31}, id="expired"),
        pytest.param({"iat": ISSUED_AT + 31}, id="issued in the future"),
        pytest.param({"sub": 42}, id="subject not a string"),
    ],
)
def test_rejects_invalid_claims(
    verifier: AccessTokenVerifier,
    signing_key: SigningKey,
    claims: dict[str, Any],
    changes: dict[str, Any],
) -> None:
    with pytest.raises(InvalidAccessTokenError):
        verifier.verify(signing_key.sign(claims | changes))


@pytest.mark.parametrize("claim", ["exp", "iat", "iss", "aud", "sub"])
def test_rejects_token_without_required_claim(
    verifier: AccessTokenVerifier,
    signing_key: SigningKey,
    claims: dict[str, Any],
    claim: str,
) -> None:
    del claims[claim]

    with pytest.raises(InvalidAccessTokenError):
        verifier.verify(signing_key.sign(claims))


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"exp": ISSUED_AT - 29}, id="expired within skew"),
        pytest.param({"iat": ISSUED_AT + 29}, id="issued within skew"),
    ],
)
def test_tolerates_clock_skew(
    verifier: AccessTokenVerifier,
    signing_key: SigningKey,
    claims: dict[str, Any],
    changes: dict[str, Any],
) -> None:
    claims |= changes

    assert verifier.verify(signing_key.sign(claims)) == claims


def test_unknown_key_id_reloads_key_set(
    jwks_server: JwksServer, signing_key: SigningKey, claims: dict[str, Any]
) -> None:
    keys = KeySetClient(jwks_server.url, cooldown_duration=0)
    verifier = AccessTokenVerifier(keys, issuer=ISSUER, audience="accessflow-api")
    verifier.verify(signing_key.sign(claims))
    rotated = SigningKey()
    jwks_server.keys = [rotated.jwk]

    assert verifier.verify(rotated.sign(claims)) == claims
    assert jwks_server.requests == 2


def test_key_set_reload_is_rate_limited(
    verifier: AccessTokenVerifier,
    jwks_server: JwksServer,
    signing_key: SigningKey,
    claims: dict[str, Any],
) -> None:
    verifier.verify(signing_key.sign(claims))
    unknown = SigningKey()

    for _ in range(3):
        with pytest.raises(InvalidAccessTokenError):
            verifier.verify(unknown.sign(claims))
    assert jwks_server.requests == 1


def test_unreachable_key_set_is_unavailable(
    settings: Settings, closed_port: int, signing_key: SigningKey, claims: dict[str, Any]
) -> None:
    verifier = create_token_verifier(
        with_jwks_url(settings, f"http://127.0.0.1:{closed_port}/certs")
    )

    with pytest.raises(IdentityProviderUnavailableError):
        verifier.verify(signing_key.sign(claims))


def test_connection_reset_while_reading_key_set_is_unavailable(
    jwks_server: JwksServer,
    signing_key: SigningKey,
    claims: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reset(self: PyJWKClient) -> object:
        raise ConnectionResetError

    monkeypatch.setattr(PyJWKClient, "fetch_data", reset)
    verifier = AccessTokenVerifier(
        KeySetClient(jwks_server.url), issuer=ISSUER, audience="accessflow-api"
    )

    with pytest.raises(IdentityProviderUnavailableError):
        verifier.verify(signing_key.sign(claims))


def test_key_set_timeout_is_unavailable(
    jwks_server: JwksServer, signing_key: SigningKey, claims: dict[str, Any]
) -> None:
    jwks_server.stalled = True
    keys = KeySetClient(jwks_server.url, timeout=0.2)
    verifier = AccessTokenVerifier(keys, issuer=ISSUER, audience="accessflow-api")

    with pytest.raises(IdentityProviderUnavailableError):
        verifier.verify(signing_key.sign(claims))


def test_key_set_client_is_configured_from_constants(auth_settings: Settings) -> None:
    keys = create_key_set_client(auth_settings)

    assert keys.timeout == 5
    assert keys.cooldown_duration == 30
    assert keys.jwk_set_cache is not None
    assert keys.jwk_set_cache.lifespan == 300


def test_failed_download_is_not_repeated_during_cooldown(
    jwks_server: JwksServer, signing_key: SigningKey, claims: dict[str, Any]
) -> None:
    jwks_server.response = (HTTPStatus.SERVICE_UNAVAILABLE, b"")
    keys = KeySetClient(jwks_server.url, failure_cooldown=60)
    verifier = AccessTokenVerifier(keys, issuer=ISSUER, audience="accessflow-api")

    for _ in range(3):
        with pytest.raises(IdentityProviderUnavailableError):
            verifier.verify(signing_key.sign(claims))

    assert jwks_server.requests == 1


def test_download_is_retried_after_cooldown(
    jwks_server: JwksServer, signing_key: SigningKey, claims: dict[str, Any]
) -> None:
    jwks_server.response = (HTTPStatus.SERVICE_UNAVAILABLE, b"")
    keys = KeySetClient(jwks_server.url, failure_cooldown=0)
    verifier = AccessTokenVerifier(keys, issuer=ISSUER, audience="accessflow-api")
    with pytest.raises(IdentityProviderUnavailableError):
        verifier.verify(signing_key.sign(claims))
    jwks_server.response = None

    assert verifier.verify(signing_key.sign(claims)) == claims
    assert jwks_server.requests == 2


def test_concurrent_requests_share_a_slow_download(
    verifier: AccessTokenVerifier,
    jwks_server: JwksServer,
    signing_key: SigningKey,
    claims: dict[str, Any],
) -> None:
    jwks_server.delay = 0.2
    tokens = [signing_key.sign(claims) for _ in range(8)]

    with ThreadPoolExecutor(max_workers=len(tokens)) as pool:
        results = list(pool.map(verifier.verify, tokens))

    assert results == [claims] * len(tokens)
    assert jwks_server.requests == 1


def test_wait_for_a_download_in_progress_is_limited_by_timeout(
    jwks_server: JwksServer,
    signing_key: SigningKey,
    claims: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    download_started = threading.Event()

    def stall(self: PyJWKClient) -> object:
        download_started.set()
        time.sleep(1)
        raise PyJWKClientConnectionError

    monkeypatch.setattr(PyJWKClient, "fetch_data", stall)
    keys = KeySetClient(jwks_server.url, timeout=0.2)
    verifier = AccessTokenVerifier(keys, issuer=ISSUER, audience="accessflow-api")
    first = threading.Thread(target=lambda: _verify_quietly(verifier, signing_key.sign(claims)))
    first.start()
    download_started.wait()

    started = time.perf_counter()
    with pytest.raises(IdentityProviderUnavailableError):
        verifier.verify(signing_key.sign(claims))
    waited = time.perf_counter() - started
    first.join()

    assert 0.2 <= waited < 0.5


def _verify_quietly(verifier: AccessTokenVerifier, token: str) -> None:
    with contextlib.suppress(IdentityProviderUnavailableError):
        verifier.verify(token)


@pytest.mark.parametrize(
    "response",
    [
        pytest.param((HTTPStatus.SERVICE_UNAVAILABLE, b""), id="error status"),
        pytest.param((HTTPStatus.OK, b"<html></html>"), id="not json"),
        pytest.param((HTTPStatus.OK, b"[]"), id="not an object"),
        pytest.param((HTTPStatus.OK, b'{"keys": []}'), id="no keys"),
        pytest.param(
            (HTTPStatus.OK, b'{"keys": [{"kty": "RSA", "use": "enc", "kid": "x"}]}'),
            id="no usable keys",
        ),
    ],
)
def test_broken_key_set_is_unavailable(
    verifier: AccessTokenVerifier,
    jwks_server: JwksServer,
    signing_key: SigningKey,
    claims: dict[str, Any],
    response: tuple[HTTPStatus, bytes],
) -> None:
    jwks_server.response = response

    with pytest.raises(IdentityProviderUnavailableError):
        verifier.verify(signing_key.sign(claims))


def test_key_set_without_signing_keys_is_unavailable(
    verifier: AccessTokenVerifier,
    jwks_server: JwksServer,
    signing_key: SigningKey,
    claims: dict[str, Any],
) -> None:
    jwks_server.keys = [{**signing_key.jwk, "use": "enc"}]

    with pytest.raises(IdentityProviderUnavailableError):
        verifier.verify(signing_key.sign(claims))


def test_principal_from_claims(claims: dict[str, Any]) -> None:
    assert principal_from_claims(claims) == Principal(
        subject="5f0c7a52-3d3e-4f53-9d55-4a3d5c0b7f11",
        display_name="Анна Смирнова",
        roles=frozenset({"default-roles-accessflow", "HR"}),
    )


@pytest.mark.parametrize("name", [None, "", "   ", 42])
def test_display_name_falls_back_to_username(claims: dict[str, Any], name: object) -> None:
    claims["name"] = name

    assert principal_from_claims(claims).display_name == "a.smirnova"


def test_principal_without_any_name_is_rejected(claims: dict[str, Any]) -> None:
    del claims["name"], claims["preferred_username"]

    with pytest.raises(InvalidAccessTokenError):
        principal_from_claims(claims)


@pytest.mark.parametrize(
    "realm_access",
    [{}, {"roles": []}],
    ids=["without roles", "empty roles"],
)
def test_principal_without_realm_roles_has_no_roles(
    claims: dict[str, Any], realm_access: dict[str, Any]
) -> None:
    claims["realm_access"] = realm_access

    assert principal_from_claims(claims).roles == frozenset()


def test_principal_without_realm_access_has_no_roles(claims: dict[str, Any]) -> None:
    del claims["realm_access"]

    assert principal_from_claims(claims).roles == frozenset()


@pytest.mark.parametrize(
    "realm_access",
    [
        pytest.param("HR", id="claim not an object"),
        pytest.param({"roles": "HR"}, id="roles not a list"),
        pytest.param({"roles": None}, id="roles null"),
        pytest.param({"roles": ["HR", 1]}, id="role not a string"),
        pytest.param({"roles": [["HR"]]}, id="nested list"),
    ],
)
def test_malformed_roles_are_rejected(claims: dict[str, Any], realm_access: object) -> None:
    claims["realm_access"] = realm_access

    with pytest.raises(InvalidAccessTokenError):
        principal_from_claims(claims)
