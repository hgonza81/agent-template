import json
from pathlib import Path

from pytest import MonkeyPatch


def test_openapi_export_writes_current_application_schema(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://127.0.0.1:5173"]')
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://agent_template:local-dev-only@127.0.0.1:5433/agent_template",
    )

    from agent_template_api.export_openapi import write_openapi
    from agent_template_api.main import app

    output_path = tmp_path / "openapi" / "openapi.json"

    write_openapi(output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == app.openapi()
