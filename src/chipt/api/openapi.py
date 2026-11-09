"""Print the API's OpenAPI schema as JSON, without starting a server.

Used by the web app's `npm run gen:api` to generate TypeScript types, so the
Pydantic models in `chipt.schemas` stay the single source of truth.

    uv run chipt-openapi > web/lib/api/openapi.json
"""

import json
import sys

from chipt.api.main import app


def main() -> None:
    json.dump(app.openapi(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
