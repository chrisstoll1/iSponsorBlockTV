"""Authenticated configuration dashboard, sharing the worker's configuration format."""

import base64
import binascii
import hmac
import os
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import aiohttp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from iSponsorBlockTV.api_helpers import ApiHelper
from iSponsorBlockTV.config_store import read_config, write_config


class PairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: StrictStr = Field(min_length=1, max_length=64)
    name: StrictStr = Field(default="", max_length=4096)
    offset: StrictInt = 0


def create_app(config_path=None, static_dir=None, password=None, password_file=None):
    config_path = Path(config_path or os.environ.get("CONFIG_PATH", "/app/data/config.json"))
    static_dir = Path(static_dir or os.environ.get("STATIC_DIR", "/app/static")).resolve()

    @asynccontextmanager
    async def lifespan(app):
        configured_file = password_file or os.environ.get("DASHBOARD_PASSWORD_FILE")
        secret = password if password is not None else os.environ.get("DASHBOARD_PASSWORD")
        if configured_file:
            secret = Path(configured_file).read_text(encoding="utf-8").rstrip("\r\n")
        if not secret:
            raise RuntimeError("Set DASHBOARD_PASSWORD or DASHBOARD_PASSWORD_FILE before starting")
        app.state.password = secret.encode("utf-8")
        app.state.username = os.environ.get("DASHBOARD_USERNAME", "admin").encode("utf-8")
        yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        if request.url.path != "/health":
            try:
                scheme, encoded = request.headers.get("authorization", "").split(" ", 1)
                if scheme.lower() != "basic":
                    raise ValueError()
                user, secret = base64.b64decode(encoded, validate=True).split(b":", 1)
                valid = hmac.compare_digest(user, request.app.state.username)
                valid &= hmac.compare_digest(secret, request.app.state.password)
            except (ValueError, binascii.Error):
                valid = False
            if not valid:
                return Response(
                    status_code=401,
                    headers={
                        "WWW-Authenticate": 'Basic realm="iSponsorBlockTV", charset="UTF-8"',
                        "Cache-Control": "no-store",
                    },
                )
            origin = request.headers.get("origin")
            if (
                request.method not in ("GET", "HEAD", "OPTIONS")
                and origin
                and urlsplit(origin).netloc != request.headers.get("host")
            ):
                return JSONResponse(
                    {"detail": "Cross-origin writes are not permitted"}, status_code=403
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health")
    def health():
        return {"status": "ok"}

    def load_config():
        try:
            return read_config(config_path)
        except (ValueError, TypeError):
            raise HTTPException(409, "Stored configuration is invalid; restore a valid config.json")
        except OSError:
            raise HTTPException(500, "Cannot read the configuration directory")

    @app.get("/api/config")
    def get_config():
        return load_config()

    @app.post("/api/config")
    def update_config(config: dict):
        try:
            saved = write_config(config_path, config)
            return {"status": "success", "config": saved}
        except (ValueError, TypeError) as error:
            raise HTTPException(422, str(error))
        except OSError:
            raise HTTPException(500, "Cannot write the configuration directory")

    @app.post("/api/pair")
    async def pair_device(data: PairRequest):
        code = data.code.replace("-", "").replace(" ", "")
        if not re.fullmatch(r"[0-9]{12}", code):
            raise HTTPException(
                422, "Enter the 12-digit code from YouTube Settings ? Link with TV code"
            )
        config = SimpleNamespace(**load_config())
        try:
            async with aiohttp.ClientSession(
                trust_env=config.use_proxy, timeout=aiohttp.ClientTimeout(total=20)
            ) as session:
                paired = await ApiHelper(config, session).pair_with_code(code)
            if not paired:
                raise HTTPException(
                    400, "Pairing code is invalid or expired. Request a new TV code."
                )
            return {
                "name": data.name or paired["name"] or "YouTube on TV",
                "screen_id": paired["screen_id"],
                "offset": data.offset,
            }
        except (aiohttp.ClientError, TimeoutError):
            raise HTTPException(502, "YouTube could not be reached. Try again shortly.")

    @app.get("/api/channels/search")
    async def search_channels(query: str = ""):
        if not query.strip():
            return []
        if len(query) > 200:
            raise HTTPException(422, "Search must be at most 200 characters")
        config = SimpleNamespace(**load_config())
        if not config.apikey:
            raise HTTPException(400, "Save a YouTube API key before searching for channels")
        try:
            async with aiohttp.ClientSession(
                trust_env=config.use_proxy, timeout=aiohttp.ClientTimeout(total=20)
            ) as session:
                results = await ApiHelper(config, session).search_channels(query)
            return [
                {"id": result[0], "name": result[1], "subscribers": result[2]} for result in results
            ]
        except ValueError:
            raise HTTPException(
                400, "YouTube rejected the search. Check the saved API key and quota."
            )
        except (aiohttp.ClientError, TimeoutError, KeyError, IndexError):
            raise HTTPException(502, "Channel search is unavailable. Try again shortly.")

    # StaticFiles handles path containment and symlinks; the fallback serves only index.html.
    if (static_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(404)
        target = (static_dir / full_path).resolve()
        if not target.is_relative_to(static_dir):
            raise HTTPException(404)
        if target.is_file():
            return FileResponse(target)
        if "." in Path(full_path).name:
            raise HTTPException(404)
        index = static_dir / "index.html"
        if not index.is_file():
            raise HTTPException(503, "Dashboard assets are unavailable")
        return FileResponse(index)

    return app


app = create_app()
