# Replace your @app.get("/api/smart-money-scanner") function with this:

@app.get("/api/smart-money-scanner")
def smart_money_scanner(region: str = "US", mcap: str = "large", email: str = "", limit: int = 50):
    if mcap not in ("large", "mid", "small", "micro"):
        mcap = "large"
    universe_map = _SMI_UNIVERSES_US if region == "US" else _SMI_UNIVERSES_IN
    universe = universe_map.get(mcap, [])
    if not universe:
        return {
            "success": False,
            "results": [],
            "universe_size": 0,
            "scan_time_sec": 0,
            "error": f"{mcap} cap for {region} not populated"
        }
    ck = f"smi:{region}:{mcap}"
    if ck in _smi_cache and time.time() - _smi_cache[ck]["t"] < 4*3600:
        return {**_smi_cache[ck]["data"], "_cached": True}
    t0 = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for f in as_completed({ex.submit(_smi_compute, t): t for t in universe[:limit]}):
            try:
                r = f.result(timeout=45)
                if r:
                    results.append(r)
            except Exception:
                pass
    payload = {
        "success": True,
        "universe_size": len(universe),
        "results": results,
        "scan_time_sec": round(time.time()-t0, 1),
        "region": region,
        "mcap": mcap,
    }
    _smi_cache[ck] = {"t": time.time(), "data": payload}
    return payload
