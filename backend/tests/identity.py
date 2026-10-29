"""Signing keys and a local JWKS endpoint that stand in for Keycloak."""

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any, Self
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

ISSUER = "https://id.invalid/realms/accessflow"


class SigningKey:
    def __init__(self) -> None:
        self.kid = str(uuid4())
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    @property
    def jwk(self) -> dict[str, Any]:
        public = RSAAlgorithm.to_jwk(self.private_key.public_key(), as_dict=True)
        return {**public, "kid": self.kid, "use": "sig", "alg": "RS256"}

    def sign(self, claims: dict[str, Any], *, algorithm: str = "RS256") -> str:
        return jwt.encode(claims, self.private_key, algorithm=algorithm, headers={"kid": self.kid})


class JwksServer:
    """Serves a JWK Set on a random loopback port and counts the requests."""

    def __init__(self) -> None:
        self.keys: list[dict[str, Any]] = []
        self.response: tuple[HTTPStatus, bytes] | None = None
        self.stalled = False
        self.requests = 0
        self._released = threading.Event()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self._server.server_port}/certs"

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                owner.requests += 1
                if owner.stalled:
                    owner._released.wait()
                    return
                status, body = owner.response or (
                    HTTPStatus.OK,
                    json.dumps({"keys": owner.keys}).encode(),
                )
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: Any) -> None:
                pass

        return Handler

    def __enter__(self) -> Self:
        # shutdown() waits for the next poll; the default interval of 0.5 s
        # would add that much to every test.
        threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        ).start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._released.set()
        self._server.shutdown()
        self._server.server_close()
