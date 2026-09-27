"""Serve the optional NextStep app without changing Celesys stock routes."""
from pathlib import Path
import logging

from starlette.staticfiles import StaticFiles

ASSET_DIRECTORY = Path(__file__).resolve().parent / "nextstep"


class NextStepFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        # Revalidate unversioned assets when a deployment updates the app.
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def attach_nextstep(app):
    """Mount only /nextstep. Missing optional assets leave stock routes intact."""
    if any(getattr(route, "path", None) == "/nextstep" for route in app.routes):
        raise RuntimeError("The /nextstep path is already registered")
    if not all((ASSET_DIRECTORY / name).is_file()
               for name in ("index.html", "app.js", "style.css")):
        logging.getLogger(__name__).warning(
            "NextStep assets missing; skipping /nextstep without affecting stock routes"
        )
        return False
    app.mount("/nextstep", NextStepFiles(directory=str(ASSET_DIRECTORY), html=True),
              name="nextstep")
    return True
