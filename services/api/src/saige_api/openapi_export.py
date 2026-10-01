"""Writes the OpenAPI document to disk so clients can be generated from it.

Usage: uv run saige-export-openapi [output_path]
CI regenerates it and fails if the committed copy is out of date.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from saige_api.core.config import Environment, Settings
from saige_api.main import create_app

DEFAULT_OUTPUT = Path("docs/api/openapi.json")


def build_spec() -> dict[str, object]:
    app = create_app(Settings(app_env=Environment.TEST, log_json=False))
    return app.openapi()


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_spec(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.write(f"Wrote {output}\n")


if __name__ == "__main__":
    main()
