"""Vercel serverless entry point for the FastAPI backend.

Vercel serves the built frontend as static files and sends every ``/api/*``
request here (see ``vercel.json``). The backend's routes are written without
that prefix, exactly as they run under uvicorn locally, so this strips it
before handing the request over. Frontend and API therefore share one origin:
no CORS, and no API hostname baked into the frontend build.
"""

import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app as backend  # noqa: E402

PREFIX = "/api"
# Where vercel.json rewrites to. Vercel normally hands the function the
# original URL, but if it ever passes the destination instead, the original
# path is in the ``path`` query parameter the rewrite adds.
REWRITE_TARGET = "/index"


def _backend_path(scope) -> tuple[str, bytes]:
    path = scope.get("path", "")[len(PREFIX):] or "/"
    query = scope.get("query_string", b"")
    if path == REWRITE_TARGET:
        pairs = parse_qsl(query.decode("latin-1"), keep_blank_values=True)
        original = [value for key, value in pairs if key == "path"]
        if original:
            path = "/" + original[0].lstrip("/")
            query = urlencode([(k, v) for k, v in pairs if k != "path"]).encode("latin-1")
    return path, query


async def app(scope, receive, send):
    if scope["type"] in ("http", "websocket"):
        path = scope.get("path", "")
        if path == PREFIX or path.startswith(PREFIX + "/"):
            scope = dict(scope)
            scope["path"], scope["query_string"] = _backend_path(scope)
            scope["raw_path"] = scope["path"].encode()
            # Lets the interactive docs at /api/docs find /api/openapi.json.
            scope["root_path"] = scope.get("root_path", "") + PREFIX
    await backend(scope, receive, send)
