"""
Celesys AI Startup Wrapper
"""
import sys
print(f"[START] Python {sys.version}", flush=True)

_import_error = None

try:
    from api import app
    print("[START] app imported OK", flush=True)
except Exception as ex:
    _import_error = str(ex)[:500]
    print(f"[START] IMPORT FAILED: {_import_error}", flush=True)
    import traceback
    traceback.print_exc()
    from fastapi import FastAPI
    app = FastAPI()
    _err_msg = _import_error

    @app.get("/")
    def error_page():
        return {"error": _err_msg, "python": sys.version}
