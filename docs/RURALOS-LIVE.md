# Public feeds and tracking centre

Two server-side integrations are deployed in this release: NOAA/Aviation Weather Center METAR observations from eight Indian airports, and the USGS magnitude 2.5+ past-day earthquake feed filtered to 6–38°N / 68–98°E. Airport conditions are not village weather, forecasts or crop advice. The earthquake box includes neighbouring countries and is not a warning/prediction service.

GET /ruralos-data/weather and /ruralos-data/earthquakes accept only the two fixed source names. No user-provided URL or private identifier is accepted. Eight-second upstream timeout, two-MB body cap, five-minute per-process cache, request coalescing and sixty-second failure backoff limit dependency traffic. Stale data is labelled; no invented fallback values are returned. Responses are no-store and excluded from the public offline cache. The frontend loads only on request, displays retrieval/source/observation times and provides English readout.

Official tracking links: rail/PNR, Aadhaar, passports, India Post, ServicePlus applications, PM-KISAN, scholarships, government grievances, licences and IMD warnings. These open the official provider. There is no embedded private status feed, CAPTCHA bypass, credential collection, live vehicle location, flight feed, cab fare comparison or new automatic notification integration.

Public source docs checked 28 September 2026:
- https://aviationweather.gov/data/api/
- https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php

Capacity limits: cache/coalescing are per process, suitable for the existing single-instance deployment. A shared cache and global rate limits are required before horizontal scaling. No large-scale load or device speech tests have been performed. The external sources have their own coverage, delays and outages.

Validation: 23 backend/routing tests include schema errors, invalid sources, concurrency, cache hits, unavailable and stale states. Both upstream endpoints returned real public data during pre-deployment connectivity checks. Rebuild with python tools/build-ruralos.py after installing ruralos-src dependencies; production uses committed validated public assets.
