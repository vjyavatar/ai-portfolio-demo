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
