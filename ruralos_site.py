"""Serve Saathi's public PWA under /ruralos, isolated from stock routes."""
from pathlib import Path
import logging
from starlette.staticfiles import StaticFiles
ASSET_DIRECTORY = Path(__file__).resolve().parent / 'ruralos'
class RuralOSFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; worker-src 'self'; object-src 'none'; frame-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'none'"
        response.headers['Permissions-Policy'] = 'microphone=(self), geolocation=(), camera=()'
        return response

def attach_ruralos(app):
    if any(getattr(route, 'path', None) == '/ruralos' for route in app.routes):
        raise RuntimeError('/ruralos is already registered')
    if not all((ASSET_DIRECTORY / name).is_file() for name in ('index.html', 'sw.js', 'manifest.webmanifest')):
        logging.getLogger(__name__).warning('Rural OS assets missing; skipping optional mount')
        return False
    from ruralos_live import router
    app.include_router(router)
    app.mount('/ruralos', RuralOSFiles(directory=str(ASSET_DIRECTORY), html=True), name='ruralos')
    return True
