"""Retirement response and narrowly scoped cleanup for the former Saathi PWA."""
from starlette.responses import HTMLResponse, Response

RETIRE_WORKER = """
self.addEventListener('install', event => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil((async () => {
  const keys = await caches.keys();
  await Promise.all(keys.filter(k => k.startsWith('saathi-ruralos-')).map(k => caches.delete(k)));
  await self.registration.unregister();
})()));
"""

def attach_retired_routes(app):
    @app.get('/ruralos/sw.js')
    def retired_worker():
        return Response(RETIRE_WORKER, media_type='application/javascript', headers={'Cache-Control': 'no-store'})

    @app.get('/ruralos')
    @app.get('/ruralos/{path:path}')
    def retired_page(path=''):
        return HTMLResponse('<!doctype html><title>Saathi retired</title><h1>Saathi has been retired.</h1><p><a href="/trading/">Open Celesys Trading Desk</a></p>', status_code=410, headers={'Cache-Control': 'no-store'})
