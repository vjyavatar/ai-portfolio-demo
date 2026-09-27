# NextStep under celesys.ai/nextstep

## Scope

This change adds the existing NextStep planner to `/nextstep/` on the Celesys FastAPI service. `/nextstep` redirects to `/nextstep/` so relative assets resolve correctly. No DNS, environment variable, dependency, stock UI, database, or Render start-command changes are required.

`api.py` has one guarded NextStep mount and one additional sitemap declaration in its existing robots response. `nextstep_site.py` mounts only the `nextstep/` asset directory. Missing optional assets skip NextStep and leave the stock application available. Existing stock handlers and homepage are preserved.

All NextStep guide links, canonical URLs, sharing URLs, and sitemap entries use `https://celesys.ai/nextstep/`. Its checklists and notes stay in browser memory until the visitor downloads a plan; the user can reopen that file later. There are no new server-side records, external AI calls, or account integrations.

## Validation completed

- 15 offline FastAPI/Starlette integration and regression checks passed against FastAPI 0.104.1 (the repository's pinned version).
- The actual stock home, robots, and sitemap handlers were exercised in an isolated app without starting market data infrastructure.
- Source AST comparison confirms existing application statements are preserved, except for the added mount and sitemap declaration.
- Stock homepage, startup wrapper, dependency file, and service worker are byte-for-byte unchanged.
- NextStep pages/assets, trailing-slash redirect, MIME types, HEAD, conditional requests, and missing assets were checked.
- Traversal attempts, unsupported write methods, and unknown paths are rejected.
- All guide navigation, canonical URLs, and sitemap destinations were checked under the new prefix.
- 2,511 recommendation combinations and simulated-DOM interaction tests passed, including plan export/import, invalid files, notes, checklists, and sharing links.
- `git diff --check` passed.

Not tested: live Render deployment, visual browser rendering, production market-data integrations, and end-to-end trading functions. The full stock module was deliberately not imported during tests because it has unrelated initialization and market-data side effects.

## Reproduce

Use a separate test environment (do not change production requirements):

```sh
python -m venv /tmp/nextstep-test-env
/tmp/nextstep-test-env/bin/pip install fastapi==0.104.1 httpx==0.27.2 'pytest>=8,<9'
/tmp/nextstep-test-env/bin/python -m pytest -q tests/test_nextstep.py
node tests/nextstep-ui.cjs
```

The httpx pin applies only to the test environment to maintain compatibility with this repository's older Starlette TestClient. Existing production dependencies are unchanged.

## Release

1. Review the `feat/nextstep-path` branch against the repository's current main branch. Rebase and rerun checks if main has changed.
2. Confirm the Celesys Render service is connected to this repository and identify its deployed branch and auto-deploy setting. These Render settings have not been verified from an authenticated dashboard.
3. Merge the reviewed change to that branch, then use the service's existing deployment process. Never replace the stock service or its start command.
4. Check `/`, one representative existing stock workflow, `/static/app.min.js`, `/robots.txt`, `/sitemap.xml`, `/nextstep`, `/nextstep/`, and `/nextstep/guides/` after deployment.
5. Check Render logs for a NextStep mount failure. If the main module itself fails, treat the existing startup wrapper's fallback response as a failure, not a healthy stock site.
6. Only after those checks pass, update promotional links to the celesys.ai path. Keep the already published standalone NextStep site available until migration is confirmed.

## Rollback

Revert the integration commit and redeploy the previously working Render version. No migrations, new storage, DNS changes, or secrets need to be reversed.

## Current delivery status

Prepared and verified against main commit 80d001994b27ffdac059213f384b3a631a44d575. The integration is being published on a separate branch for review. Render deployment and live stock regression checks must be confirmed after merge; passing local tests is not proof of a production deployment.
