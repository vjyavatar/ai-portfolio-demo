# Celesys automated QA agent

The coordinator discovers all current menus, Python route declarations and Python functions; runs regression suites; inspects public HTML and local assets; and validates selected live stock/trading/options responses. Reports contain PASS, FAIL and UNVERIFIED. It fails its exit code on a failed check. HTTP 200 with empty stock evidence fails. An unavailable option chain is explicitly unverified.

Run from the repository root with Node 22 and Python 3.11+:

```sh
pip install fastapi==0.115.6 httpx==0.27.2 requests==2.32.3
python qa/audit.py --live https://celesys.ai --output qa-output
```

Read `qa-output/report.md` for the check results and all 50 menu entries. `report.json` also lists route and function inventory. Suite logs preserve individual regression results. Function inventory is **not** coverage: unexecuted functions are labelled UNVERIFIED. Only known read-only pages and seven bounded data probes are requested; arbitrary API routes are not crawled. No email allowlist, secrets or complete API responses are written into reports.

## Browser checks

The GitHub workflow is configured to run code checks and 110 Chromium fixture checks after relevant main-branch changes and pull requests. Configuration is not evidence of execution: confirm a completed Actions run and inspect its artifacts before reporting browser results. Browser checks use a local copy, mocked API responses, and synthetic access flags. They test navigation and rendering, not production authentication or independent financial correctness. They never place orders, request paid reports or use production authorized emails. Full UI fixture means permission simulation, not a real signed-in identity.

```sh
npm install --no-save --package-lock=false @playwright/test@1.56.1
npx playwright install --with-deps chromium
npx playwright test --config qa/playwright.config.cjs
```

The browser HTML/JSON report, screenshots and failure traces are uploaded as GitHub Actions artifacts. A manual workflow run also performs production HTTP/data probes. A nightly 03:17 UTC workflow is configured for fixture checks; it does not self-deploy. Actual scheduled execution requires enabled GitHub Actions. Audits must expose failures before any corrective release.

## Coverage limits

- All 50 menus: catalogued; browser basic/full UI checks defined individually. Passing a menu-open check does not validate every control within that menu.
- Email restrictions: original resolver unit tests exercise public/trading/full/admin rules; browser tests check basic/full UI boundaries. Existing email-based gating is not equivalent to verified login authentication.
- Stock/trading data: US and India brief responses checked for actual source-labelled evidence; market values are not independently reconciled.
- Options: contract/expiry/strike response checks. Unavailable exchange feed is UNVERIFIED, not a pass.
- Charts: original report fixture must create populated Chart.js instances; screenshots allow visual inspection.
- Voice: opt-in and mute controls checked. Audible playback, microphone permissions and transcription accuracy require device testing.
- All financial engines: computational correctness, broker-side execution, every sub-control and every possible input remain unverified until explicit test cases and independent expected results exist.

This agent makes missing coverage visible. It does not claim that a large menu inventory proves the entire platform works.

## Regression memory and automatic gap detection

The coordinator writes stable, target-specific gap IDs into every `report.json`. Compare the next run with a saved report:

```sh
python qa/audit.py --previous qa-output/previous/report.json --output qa-output/current
```

A failing check becomes OPEN; missing evidence becomes NEEDS_VERIFICATION. Only a passing rerun of the same check against the same target marks a tracked gap RESOLVED. Skipped checks cannot close findings. Retain reports as CI artifacts or supply a checked-in baseline deliberately; the code-audit workflow restores the previous branch-specific report from Actions cache and saves the new report. Cache eviction starts a fresh history; downloaded artifacts remain the durable evidence. The coordinator learns regression history through evidence, not by changing strategies, permissions, source code or production deployments automatically.

All browser fixture tests now collect uncaught JavaScript errors before navigation, including startup and report rendering. Passing fixture navigation still does not prove device voice behavior, real authentication, provider availability or calculation accuracy. See `docs/UI_GAPS.md` for the review register.

Six additional UI fixtures cover collapsed homepage controls, trading/options expansion, internal stock-task expansion, focus-loss readability, and restoring loaded research without another analysis request. These checks are defined and syntax-checked; runtime results require a completed browser run.
