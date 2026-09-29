"""Create a local demonstration HR user in the imported Keycloak realm."""

import getpass
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("KEYCLOAK_BROWSER_URL", "http://localhost:8081/auth")
ADMIN = os.environ.get("KEYCLOAK_ADMIN", "admin")


def request(path: str, token: str | None = None, method: str = "GET", data: dict | list | None = None):
    body = json.dumps(data).encode() if data is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE}{path}", body, headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def main() -> None:
    email = input("Email тестового HR: ").strip().lower()
    if "@" not in email:
        sys.exit("Укажите корректный email")
    admin_password = getpass.getpass("Пароль администратора Keycloak из локального .env: ")
    hr_password = getpass.getpass("Пароль тестового HR: ")
    if len(hr_password) < 12:
        sys.exit("Пароль HR должен содержать не менее 12 символов")
    form = urllib.parse.urlencode({"client_id": "admin-cli", "grant_type": "password", "username": ADMIN, "password": admin_password}).encode()
    req = urllib.request.Request(f"{BASE}/realms/master/protocol/openid-connect/token", form, {"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            token = json.load(response)["access_token"]
        request("/admin/realms/accessflow/users", token, "POST", {
            "username": email,
            "email": email,
            "firstName": "Тестовый",
            "lastName": "HR",
            "enabled": True,
            "emailVerified": True,
            "credentials": [{"type": "password", "value": hr_password, "temporary": False}],
        })
        users = request(f"/admin/realms/accessflow/users?email={urllib.parse.quote(email)}&exact=true", token)
        user_id = next(user["id"] for user in users if user["email"] == email)
        role = request("/admin/realms/accessflow/roles/HR", token)
        request(f"/admin/realms/accessflow/users/{user_id}/role-mappings/realm", token, "POST", [role])
    except urllib.error.HTTPError as exc:
        sys.exit(f"Keycloak вернул HTTP {exc.code}. Проверьте настройки, email и запуск сервиса.")
    except (urllib.error.URLError, StopIteration) as exc:
        sys.exit(f"Не удалось создать пользователя: {exc}")
    print(f"Тестовый HR {email} создан. Роль HR назначена.")


if __name__ == "__main__":
    main()
