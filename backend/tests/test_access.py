from datetime import UTC, datetime, timedelta


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
