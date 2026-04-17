"""
React frontend serving module for Celesys.
Imported by api.py. Adds routes to serve the built React SPA from static/dist/.
"""

from pathlib import Path
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


def attach_react_routes(app):
    """Call this AFTER all /api/* routes are registered on the FastAPI app."""

    react_dist = Path(__file__).parent / "static" / "dist"

    # Mount Vite's hashed JS/CSS bundles at /assets/*
    if (react_dist / "assets").exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(react_dist / "assets")),
            name="react_assets",
        )

    # Serve index.html at root
    @app.get("/")
    async def serve_react_root():
        index = react_dist / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"error": "React build not found. Run: npm install && npm run build"}

    # Catchall: serve static files or fall back to React SPA
    @app.get("/{full_path:path}")
    async def serve_react_catchall(full_path: str):
        # Don't intercept API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")

        # Try the exact file (favicon, manifest, etc.)
        target = react_dist / full_path
        if target.is_file():
            return FileResponse(str(target))

        # Otherwise fall back to React (SPA routing)
        index = react_dist / "index.html"
        if index.exists():
            return FileResponse(str(index))

        raise HTTPException(status_code=404, detail="Not found")