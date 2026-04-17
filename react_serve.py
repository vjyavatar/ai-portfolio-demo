"""
React frontend serving module for Celesys — HYBRID MODE.
React UI is served at /new (while old UI stays at /).
"""

from pathlib import Path
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


def attach_react_routes(app):
    """Mount React at /new. Call AFTER all /api/* routes are registered."""

    react_dist = Path(__file__).parent / "static" / "dist"

    if (react_dist / "assets").exists():
        app.mount(
            "/new/assets",
            StaticFiles(directory=str(react_dist / "assets")),
            name="react_assets",
        )

    @app.get("/new")
    async def serve_react_root():
        index = react_dist / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"error": "React build not found. Run: npm install && npm run build"}

    @app.get("/new/")
    async def serve_react_root_slash():
        index = react_dist / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"error": "React build not found"}

    @app.get("/new/{full_path:path}")
    async def serve_react_catchall(full_path: str):
        target = react_dist / full_path
        if target.is_file():
            return FileResponse(str(target))
        index = react_dist / "index.html"
        if index.exists():
            return FileResponse(str(index))
        raise HTTPException(status_code=404, detail="Not found")
