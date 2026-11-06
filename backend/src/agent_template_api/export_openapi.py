import argparse
import json
from pathlib import Path

from agent_template_api.main import app


def write_openapi(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Export the FastAPI OpenAPI schema.")
    parser.add_argument(
        "--output",
        type=Path,
        default=repository_root / "openapi" / "openapi.json",
        help="Path to write the generated OpenAPI schema.",
    )
    arguments = parser.parse_args()
    write_openapi(arguments.output)


if __name__ == "__main__":
    main()
