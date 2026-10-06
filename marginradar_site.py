"""Celesys MarginRadar public entry; hosted identity stays on the workspace origin."""
from pathlib import Path
from starlette.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

ASSET_DIRECTORY = Path(__file__).resolve().parent / 'marginradar'

class MarginRadarFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'self'; form-action 'none'"
        return response

def attach_marginradar(app):
    if any(getattr(route, 'path', None) in ('/marginradar', '/nextstep') for route in app.routes):
        raise RuntimeError('MarginRadar or retired planner path already registered')
    # Register retirement even if optional new assets are unavailable.
    async def retire_planner(request):
        return RedirectResponse('/marginradar/', status_code=308)
    app.add_route('/nextstep', retire_planner, methods=['GET', 'HEAD'])
    async def retire_sitemap(request):
        return RedirectResponse('/marginradar/sitemap.xml', status_code=308)
    app.add_route('/nextstep/sitemap.xml', retire_sitemap, methods=['GET', 'HEAD'])
    app.add_route('/nextstep/{path:path}', retire_planner, methods=['GET', 'HEAD'])
    if not (ASSET_DIRECTORY / 'index.html').is_file():
        return False
    app.mount('/marginradar', MarginRadarFiles(directory=str(ASSET_DIRECTORY), html=True), name='marginradar')
    return True
