from fastapi.testclient import TestClient
from pytest import MonkeyPatch


def test_liveness_returns_ok_without_external_dependencies(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://127.0.0.1:5173"]')

    from agent_template_api.main import app

    with TestClient(app) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
