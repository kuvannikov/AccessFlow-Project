"""Create a user in the accessflow realm of the development Keycloak.

The administrator password is read from KEYCLOAK_ADMIN_PASSWORD. The new user's
password is typed in twice and is never printed.
"""

import argparse
import os
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from getpass import getpass

import httpx2

REALM = "accessflow"
HR_ROLE = "HR"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_VARIABLE = "KEYCLOAK_ADMIN_PASSWORD"  # noqa: S105
DEFAULT_KEYCLOAK_URL = "http://localhost:8081"
REQUEST_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class NewUser:
    username: str
    email: str
    first_name: str
    last_name: str
    password: str
    roles: tuple[str, ...] = ()


@contextmanager
def admin_client(keycloak_url: str, admin_password: str) -> Iterator[httpx2.Client]:
    """Client of the realm's Admin API, signed in as the bootstrap administrator."""
    with httpx2.Client(
        base_url=f"{keycloak_url}/admin/realms/{REALM}", timeout=REQUEST_TIMEOUT_SECONDS
    ) as client:
        response = client.post(
            f"{keycloak_url}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": ADMIN_USERNAME,
                "password": admin_password,
            },
        ).raise_for_status()
        client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
        yield client


def create_user(admin: httpx2.Client, user: NewUser) -> str:
    """Create the user with a permanent password and its realm roles; return the user ID.

    Keycloak checks the password against the realm policy and creates nothing
    when it fails.
    """
    # Looked up first, so a missing role leaves no user behind.
    roles = [admin.get(f"/roles/{role}").raise_for_status().json() for role in user.roles]
    response = admin.post(
        "/users",
        json={
            "username": user.username,
            # Keycloak refuses to sign in a user whose required profile fields are empty.
            "email": user.email,
            "emailVerified": True,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "enabled": True,
            "credentials": [{"type": "password", "value": user.password, "temporary": False}],
        },
    ).raise_for_status()
    user_id = response.headers["Location"].rsplit("/", 1)[-1]
    if roles:
        admin.post(f"/users/{user_id}/role-mappings/realm", json=roles).raise_for_status()
    return user_id


def keycloak_error(response: httpx2.Response) -> str:
    # The Admin API and the token endpoint describe errors under different keys.
    try:
        body = response.json()
    except ValueError:
        return response.reason_phrase
    if isinstance(body, dict):
        for key in ("error_description", "errorMessage", "error"):
            if isinstance(detail := body.get(key), str):
                return detail
    return response.reason_phrase


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--first-name", required=True)
    parser.add_argument("--last-name", required=True)
    parser.add_argument("--hr", action="store_true", help=f"grant the {HR_ROLE} role")
    parser.add_argument(
        "--keycloak-url",
        default=DEFAULT_KEYCLOAK_URL,
        help=f"Keycloak of the dev stack (default: {DEFAULT_KEYCLOAK_URL})",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    admin_password = os.environ.get(ADMIN_PASSWORD_VARIABLE)
    if not admin_password:
        print(
            f"{ADMIN_PASSWORD_VARIABLE} is not set; run the script with uv run --env-file ../.env.",
            file=sys.stderr,
        )
        return 1
    password = getpass("Password of the new user: ")
    if getpass("Repeat the password: ") != password:
        print("The passwords do not match.", file=sys.stderr)
        return 1
    user = NewUser(
        username=args.username,
        email=args.email,
        first_name=args.first_name,
        last_name=args.last_name,
        password=password,
        roles=(HR_ROLE,) if args.hr else (),
    )
    try:
        with admin_client(args.keycloak_url, admin_password) as admin:
            user_id = create_user(admin, user)
    except httpx2.HTTPStatusError as error:
        request, response = error.request, error.response
        print(
            f"Keycloak refused {request.method} {request.url.path}: "
            f"{response.status_code} {keycloak_error(response)}",
            file=sys.stderr,
        )
        return 1
    except httpx2.TransportError as error:
        print(f"Keycloak is not reachable at {args.keycloak_url}: {error}", file=sys.stderr)
        return 1
    print(f"Created user {user.username} (id {user_id}), roles: {', '.join(user.roles) or 'none'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
