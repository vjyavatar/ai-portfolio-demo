"""Offline routing/security regression checks; no market calls or startup jobs."""
import ast
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.testclient import TestClient
from starlette.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles
import pytest

import marginradar_site

ROOT = Path(__file__).resolve().parents[1]


def build_app():
    app = FastAPI()
    # Execute only the actual offline stock homepage and discovery handlers.
    # Importing api.py would start unrelated market/cache infrastructure.
    tree = ast.parse((ROOT / "api.py").read_text())
    selected = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name in {"home", "robots", "sitemap"}]
    assert len(selected) == 3
    scope = dict(app=app, HTMLResponse=HTMLResponse, PlainTextResponse=PlainTextResponse,
                 Response=Response, datetime=datetime)
    exec(compile(ast.Module(body=selected, type_ignores=[]), "api.py", "exec"), scope)
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    @app.get("/api/test-stock-sentinel")
    def sentinel():
        return {"stock": "unchanged"}
    app.add_middleware(GZipMiddleware, minimum_size=500)
    return app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.chdir(ROOT)
    app = build_app()
    assert marginradar_site.attach_marginradar(app)
    with TestClient(app, base_url="https://celesys.ai") as client:
        yield client


def test_stock_routes_unchanged(client):
    assert client.get("/").text == (ROOT / "index.html").read_text()
    assert client.get("/api/test-stock-sentinel").json() == {"stock": "unchanged"}
    assert client.get("/static/app.min.js").content == (ROOT / "static/app.min.js").read_bytes()


def test_public_path_and_assets(client):
    r = client.get("/marginradar", follow_redirects=False)
    assert r.status_code in (307, 308)
    assert r.headers["location"].endswith("/marginradar/")
    for path in ("/marginradar/", "/marginradar/app.js", "/marginradar/style.css", "/marginradar/sitemap.xml"):
        r = client.get(path)
        assert r.status_code == 200
        assert r.headers["cache-control"] == "no-cache"
        assert r.headers["x-content-type-options"] == "nosniff"
    assert client.head("/marginradar/").content == b""


@pytest.mark.parametrize("path", ["/nextstep", "/nextstep/", "/nextstep/app.js", "/nextstep/guides/", "/nextstep/guides/work-with-ai/"])
def test_planner_retired(client, path):
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 308
    assert r.headers["location"] == "/marginradar/"


@pytest.mark.parametrize("path", ["/marginradar/%2e%2e%2fapi.py", "/marginradar/.git/config", "/marginradarevil", "/marginradar/missing"])
def test_invalid_routes(client, path):
    assert client.get(path).status_code == 404


def test_write_methods_rejected(client):
    for method in ("POST", "PUT", "DELETE", "PATCH"):
        assert client.request(method, "/marginradar/app.js").status_code == 405


def test_discovery_and_workspace_links(client):
    assert "Sitemap: https://celesys.ai/nextstep/sitemap.xml" in client.get("/robots.txt").text
    assert client.get("/nextstep/sitemap.xml").text == client.get("/marginradar/sitemap.xml").text
    page = client.get("/marginradar/").text
    assert 'href="https://celesys.ai/marginradar/"' in page
    assert 'https://marginradar.vjyrcks.chatgpt.site/workspace' in page
    assert 'opens on our ChatGPT-hosted app' in page


def test_existing_application_ast_unchanged_except_mount_and_sitemap():
    old = subprocess.check_output(["git", "show", "origin/main:api.py"], cwd=ROOT, text=True)
    new = (ROOT / "api.py").read_text()
    new = new.replace("from marginradar_site import attach_marginradar", "from nextstep_site import attach_nextstep").replace("attach_marginradar(app)", "attach_nextstep(app)").replace("MarginRadar unavailable; stock routes remain active", "NextStep unavailable; stock routes remain active").replace("https://celesys.ai/marginradar/sitemap.xml", "https://celesys.ai/nextstep/sitemap.xml")
    assert ast.dump(ast.parse(old)) == ast.dump(ast.parse(new))
