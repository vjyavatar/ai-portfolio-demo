# Saathi · Rural Family Action OS on Celesys

Public mount: https://celesys.ai/ruralos/ (deployment must be verified before announcing live).

This reuses the v0.4.0 public client from the Rural Family Action OS Site. The existing app remains at https://rural-family-action-os.vjyrcks.chatgpt.site . Private family profiles, saved documents, reminders and support requests open that secure origin; they are not copied into Celesys or cached here. Browsing and structured national pension checks run in the client. Hindi/Telugu are opt-in review previews. Speech uses supported browser/device APIs, with Indian locales and text/tap fallbacks. No store publication, live notification delivery or staffed assistance is implied.

## Isolation
- Only /ruralos is mounted. Existing stock and NextStep handlers are unchanged.
- PWA manifest and service worker are scoped to /ruralos/; the cache contains only packaged public files.
- Missing optional assets do not prevent the stock server from starting.
- No new service, database or paid resource is provisioned.

## Source and build
The source snapshot is in ruralos-src; its Vite build uses React and the existing UI libraries. From that folder, install the package dependencies and run npm run build. Copy the four public artwork files into ruralos after a rebuild and regenerate the public service worker asset list (the current complete list is in ruralos/sw.js). No secrets are required. The production root npm build verifies committed prebuilt assets so the existing Render build command succeeds without introducing a frontend build dependency for stock routes.

The bundle is about 180 KB gzipped JavaScript plus 26 KB CSS and local artwork. Native binaries and store distribution are separate tasks.

## Verification
Run PYTHONPATH=. python -m pytest tests/test_ruralos.py -q. Coverage includes root/API preservation, AST comparison of existing start.py handlers, prefix redirect, all linked assets, Hindi/Telugu entry URLs, manifest scope, service worker scope, traversal denial, rejected writes and security headers. These checks do not replace browser/device voice or rural-user comprehension testing.

Rollback: remove the guarded ruralos_site import/attach block in start.py and redeploy. The original hosted app stays available.
