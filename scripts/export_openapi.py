"""
Export the OpenAPI spec to a JSON file for Postman import.

Usage (via Docker):
    docker compose exec api python scripts/export_openapi.py

The spec is written to /app/docs/openapi.json inside the container
and mapped to ./docs/openapi.json on the host.
"""

import json
import os
import sys

# Ensure the app package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "openapi.json")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    spec = app.openapi()
    with open(OUTPUT_FILE, "w") as f:
        json.dump(spec, f, indent=2, default=str)

    print(f"✅  OpenAPI spec exported to {OUTPUT_FILE}")
    print(f"    Title   : {spec['info']['title']}")
    print(f"    Version : {spec['info']['version']}")
    print(f"    Paths   : {len(spec.get('paths', {}))}")
    print()
    print("To import into Postman:")
    print("  1. Open Postman → Import → select the openapi.json file")
    print("  2. Or use the live URL: http://localhost:8000/openapi.json")


if __name__ == "__main__":
    main()

