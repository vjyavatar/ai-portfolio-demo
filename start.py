"""
Celesys AI — Startup Wrapper
This file is the uvicorn entry point. It imports api.py and exposes the app.
If api.py crashes during import, this shows the exact error.
"""
import sys
print(f"[START] Python {sys.version}", flush=True)
print(f"[START] Importing api module...", flush=True)

try:
    from api import app
    print(f"[START] ✅ app imported successfully: {type(app)}", flush=True)
except Exception as e:
    print(f"[START] ❌ IMPORT FAILED: {type(e).__name__}: {e}", flush=True)
    import traceback
    traceback.print_exc()
    
    # Create a minimal fallback app so uvicorn doesn't crash
    from fastapi import FastAPI
    app = FastAPI()
    
    @app.get("/")
    def error_page():
        return {"error": f"api.py failed to load: {str(e)[:200]}", "fix": "Check Render logs for traceback"}
    
    @app.get("/health")
    def health():
        return {"status": "error", "detail": str(e)[:200]}
    
    print(f"[START] ⚠️ Running fallback app — check logs for the real error", flush=True)

# Retire the removed Saathi app and its offline cache.
from retired_site import attach_retired_routes
attach_retired_routes(app)

# Isolated trading desk uses the deployed startup entrypoint.
try:
    from trading_site import attach_trading_desk
    attach_trading_desk(app)
except Exception:
    import logging
    logging.getLogger(__name__).exception("Trading Desk unavailable; existing routes remain active")

# Search-friendly discovery and read-only India/US option snapshots.
from discovery_site import attach_discovery
try:
    from api import stock_dashboard, decision_engine, options_quick
except ImportError:
    stock_dashboard = None
    decision_engine = options_quick = None
attach_discovery(app, dashboard_supplier=stock_dashboard, trading_supplier=decision_engine, options_supplier=options_quick)

# Verified sign-in is staged behind explicit enforcement, preserving current access during setup.
import ast
from pathlib import Path
from secure_access import attach_access
_api = sys.modules.get("api")

def _account_roles(email):
    if _api is None:return {}
    return {'full':email.lower() in _api.AUTHORIZED_EMAILS,
            'trades':email.lower() in [e.lower() for e in _api.PREMIUM_TIERS['trades']],
            'dream':email.lower() in [e.lower() for e in _api.PREMIUM_TIERS['dream']]}

_protected={'/api/auth/verify':'full','/today':'dream'}
for _node in ast.parse(Path(__file__).with_name('api.py').read_text()).body:
    if not isinstance(_node,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
    _tier=None
    for _call in ast.walk(_node):
        if isinstance(_call,ast.Call) and isinstance(_call.func,ast.Name):
            if _call.func.id=='check_premium_gate' and len(_call.args)>1 and isinstance(_call.args[1],ast.Constant):_tier=_call.args[1].value
            elif _call.func.id=='_is_premium_email':_tier=_tier or 'trades'
            elif _call.func.id=='_is_authorized':_tier=_tier or 'full'
    if _tier:
        for _dec in _node.decorator_list:
            if isinstance(_dec,ast.Call) and _dec.args and isinstance(_dec.args[0],ast.Constant):_protected[_dec.args[0].value]=_tier
attach_access(app,_account_roles,_protected)
from private_options import router as _private_options_router
app.include_router(_private_options_router)
