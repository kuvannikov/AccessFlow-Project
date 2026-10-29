from typing import Annotated

from fastapi import Depends
from fastapi.testclient import TestClient

from accessflow.app import create_app
from accessflow.core.config import Settings
from accessflow.core.security import Principal, require_role


def protected_client(settings: Settings) -> TestClient:
    """Client of an application with an extra endpoint, /test/hr, open to the HR role only."""
    app = create_app(settings)

    @app.get("/test/hr")
    def hr_only(principal: Annotated[Principal, Depends(require_role("HR"))]) -> dict[str, str]:
        return {"subject": principal.subject}

    return TestClient(app)
