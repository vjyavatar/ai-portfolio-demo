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

import nextstep_site

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
    assert nextstep_site.attach_nextstep(app)
    with TestClient(app, base_url="https://celesys.ai") as client:
        yield client


def test_stock_homepage_unchanged(client):
    result = client.get("/")
    assert result.status_code == 200
    assert result.text == (ROOT / "index.html").read_text()
    assert client.get("/api/test-stock-sentinel").json() == {"stock": "unchanged"}
    asset = next(p for p in (ROOT / "static").glob("*.js") if p.is_file())
    assert client.get("/static/" + asset.name).content == asset.read_bytes()


def test_prefix_redirect_and_assets(client):
    response = client.get("/nextstep", follow_redirects=False)
    assert response.status_code in (307, 308)
    assert response.headers["location"] == "https://celesys.ai/nextstep/"
    for path, kind in [("/nextstep/", "text/html"), ("/nextstep/style.css", "text/css"),
                       ("/nextstep/app.js", "javascript"), ("/nextstep/guides/", "text/html")]:
        r = client.get(path)
        assert r.status_code == 200, path
        assert kind in r.headers["content-type"]
        assert r.headers["cache-control"] == "no-cache"
        assert r.headers["x-content-type-options"] == "nosniff"
    assert client.head("/nextstep/").status_code == 200
    assert client.head("/nextstep/").content == b""
    assert client.get("/nextstep/app.js?v=2").status_code == 200
    r = client.get("/nextstep/app.js")
    assert client.get("/nextstep/app.js", headers={"If-None-Match": r.headers["etag"]}).status_code == 304


@pytest.mark.parametrize("path", ["/nextstep/missing", "/nextstep/%2e%2e/api.py",
    "/nextstep/%2e%2e%2fapi.py", "/nextstep/%2e%2e%2f.git/config", "/nextstep/..%5capi.py",
    "/nextstep/.git/config", "/nextstepevil", "/nextstep/guides/missing/"])
def test_missing_and_traversal(client, path):
    r = client.get(path)
    assert r.status_code == 404
    assert "VERIFIED Real-Time Data" not in r.text
    assert "ref: refs/heads" not in r.text


def test_write_methods_rejected(client):
    for method in ("POST", "PUT", "DELETE", "PATCH"):
        assert client.request(method, "/nextstep/app.js", content="bad").status_code == 405


def test_missing_assets_do_not_break_stocks(monkeypatch, tmp_path):
    monkeypatch.chdir(ROOT)
    app = build_app()
    monkeypatch.setattr(nextstep_site, "ASSET_DIRECTORY", tmp_path)
    assert not nextstep_site.attach_nextstep(app)
    with TestClient(app) as c:
        assert c.get("/").text == (ROOT / "index.html").read_text()
        assert c.get("/nextstep/").status_code == 404


def test_working_directory_independent(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    app = FastAPI()
    assert nextstep_site.attach_nextstep(app)
    with TestClient(app) as c:
        assert c.get("/nextstep/").status_code == 200
    with pytest.raises(RuntimeError):
        nextstep_site.attach_nextstep(app)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("href", "src") and value.startswith("/"):
                self.links.append(value)


def test_guide_links_canonicals_and_sitemaps(client):
    for path in (ROOT / "nextstep").rglob("*.html"):
        text = path.read_text()
        assert "chatgpt.site" not in text
        assert 'href="https://celesys.ai/nextstep/' in text
        parser = Links(); parser.feed(text)
        for link in parser.links:
            assert link.startswith("/nextstep/"), (path, link)
            assert client.get(link).status_code == 200, (path, link)
    root_map = ET.fromstring(client.get("/sitemap.xml").text)
    assert len(root_map) == 7  # All stock discovery pages are retained.
    ns_map = ET.fromstring(client.get("/nextstep/sitemap.xml").text)
    assert len(ns_map) == 5
    for loc in ns_map.findall(".//{*}loc"):
        assert loc.text.startswith("https://celesys.ai/nextstep/")
        assert client.get(loc.text).status_code == 200
    robots = client.get("/robots.txt").text
    assert "Disallow: /api/" in robots
    assert "Sitemap: https://celesys.ai/sitemap.xml" in robots
    assert "Sitemap: https://celesys.ai/nextstep/sitemap.xml" in robots


def test_existing_app_code_preserved():
    baseline = subprocess.check_output(["git", "show", "80d001994b27ffdac059213f384b3a631a44d575:api.py"], cwd=ROOT, text=True)
    old = ast.parse(baseline)
    new = ast.parse((ROOT / "api.py").read_text())
    # The only added executable top-level statement is the guarded mount.
    mounts = [n for n in new.body if isinstance(n, ast.Try) and any(
        isinstance(c, ast.ImportFrom) and c.module == "nextstep_site" for c in n.body)]
    assert len(mounts) == 1
    new.body.remove(mounts[0])
    for n in ast.walk(new):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            n.value = n.value.replace("Sitemap: https://celesys.ai/nextstep/sitemap.xml\n", "")
    assert ast.dump(old, include_attributes=False) == ast.dump(new, include_attributes=False)
    for name in ("index.html", "start.py", "requirements.txt", "sw.js"):
        assert (ROOT / name).read_bytes() == subprocess.check_output(["git", "show", f"80d001994b27ffdac059213f384b3a631a44d575:{name}"], cwd=ROOT)
