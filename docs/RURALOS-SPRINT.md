# RuralOS bounded improvement sprint

User authorized reversible improvements and Render web releases for nine hours on 28 September 2026. Follow-up runs are hourly, first 11:25 IST, last 19:25 IST (9 runs). Scheduling does not imply uninterrupted work or a successful future release. Update this log with actual outcomes only.

## Scope and release policy
- Public RuralOS is https://celesys.ai/ruralos/, repository vjyavatar/ai-portfolio-demo, Render srv-d690qd0gjchc73det890, confirmed workspace tea-d690ma14tr6s73cdsvn0. Preserve unrelated stock app, NextStep, routes and files.
- Private family persistence and owner-only tracking live at https://rural-family-action-os.vjyrcks.chatgpt.site/. Do not move them to unauthenticated public endpoints. Tracking allows only dispatcher-verified vjyavatar@gmail.com. Do not accept a client email or reuse this email as an authentication password.
- Read latest main and inspect pending deployments before every change. Use a clean isolated checkout and exact latest commit as parent. Never overwrite concurrent edits. No deployment while another is active.
- Every release needs a concrete user benefit or verified defect fix; passing tests, build and asset validation; live deployment and read-only smoke verification. No empty redeploys. Stop expanding scope when tests fail.
- All licensed/paid integrations require authorized credentials and permitted use. No new costs, account impersonation, fabricated data, autonomous bookings, government submissions or trades.
- "Learning" means recording failures, feedback and test evidence for reviewed improvements. This app does not retrain a model or rewrite production code by itself. Do not claim agentic LLM capability without an authorized model connection.

## Current iteration — 28 September
Implemented a homepage with all 42 guided services, categories, multilingual search titles, browser-voice search with explicit audio consent, direct service URLs, large action buttons, keyboard navigation, and clear handoff labels. Preserved family tools, secure reminders/help requests and private tracking. Hindi/Telugu remain quality-review previews. Lazy chunks are cached only after use; core home assets remain available offline. Runtime loading errors show an explicit refresh/recovery screen. Extracted lazy client chunks to reduce initial JavaScript from ~624KB to ~345KB before compression. Fixed live-feed malformed-row handling, observation freshness recomputation, and implausible event-time rejection.

Validation commands:
- `node ruralos-src/node_modules/typescript/bin/tsc -p ruralos-src/tsconfig.json`
- `python tools/build-ruralos.py` (requires source dependencies; do not ship symlinks)
- `npm run build` (asset graph/offline cache checks plus 54 workflow/directory/offline tests; also runs on Render before deployment)
- `PYTHONPATH=. python -m pytest tests/test_ruralos.py tests/test_ruralos_live.py -q` (27 checks at this iteration)
- `python tools/check-ruralos-live.py` after Render reports live (read-only, checks matching entry bundle, installation manifest, private redirect and missing routes)

Git CLI pushes are not authenticated in this workspace. Use available GitHub tree/commit/ref tools with exact latest parent and `force:false`. Atomic tree updates must include built assets and removals. Render's Git auto-deploy has not triggered for this public-clone service: check current deploys, and only trigger a deploy if it will not happen automatically. Source build tooling expects Node 22+ with type stripping support; Python tests run separately before publish. Never skip security tests to deploy faster.

## Ordered backlog for follow-up runs
1. Verify customer journeys in a real browser, including speech unavailable/permission denied, selected service routing/back/refresh, mobile overflow, keyboard access, cached navigation and offline provider failures. Record infrastructure limitations honestly.
2. Service detail experience: clearer document checklists, chosen state-specific routes, dated authoritative source review, action cards with listen/help/reminders. Existing common workflows are preparatory handoffs, not submission integrations.
3. Safe tool registry and provider adapters: enumerate connected feeds, verified external handoffs, and blocked APIs. Use schema validation, timeouts, failure cooldowns, bounded retries and idempotency where effects exist. Test all external boundary failures.
4. Authenticated improvement feedback and measurable completion funnel with explicit consent. Aggregate safely; no household content in public logs. Persist with the existing authenticated Site only after following Sites skills.
5. Model orchestration only after verifying an authorized LLM connection: structured tool calls, strict region/source constraints, no invented eligibility/fees/approvals, no uncontrolled purchases. Existing workflows are deterministic.
6. Additional data integrations only with documented official APIs, acceptable terms, current tests and clear coverage. Do not scrape protected providers or pass links off as integration.
7. Accessibility/low bandwidth: stronger mobile hierarchy, focus management, reduced motion, screen-reader labels, predictable offline refresh and spoken guidance review. Rural household testing remains external and cannot be claimed from automated tests.
8. Reliability: monitored health and contract checks, source review expiry, release rollback documentation, tested recovery of existing storage. Do not provision paid workers/databases without cost authorization.
9. Consolidate handover and factual release report. Record each shipped commit, measured improvement, remaining blocker and actual test coverage.

## Known blockers
- Flight fares/positions, vessel AIS, rail status, cab booking and holiday providers lack authorized production API entitlements.
- General AI model invocation is not connected for RuralOS; do not repurpose another app's secret without scope verification.
- Email/SMS/push delivery, staffed helpers, actual booking/payment/submission and institution partnerships are unavailable.
- App Store/Play Store accounts, signing credentials and native release toolchains are missing; no store publication.
- Full state-specific eligibility verification, translations, speech quality and actual rural-user comprehension validation are incomplete.
- USGS reports and airport observations are bounded public feeds, not all-clear emergency advice or village forecasts. ISS is one calculated orbit, not all satellites.

Browser QA limitation: Chromium installation failed because the supplied download was empty/invalid. No visual, microphone-device or real household testing is claimed. Repeat those checks when a browser environment is available.

## Run log
Append: time (IST), initial commit, goal/defect, changed files, checks and findings, deployment commit/status, remaining risk, next priority. Never fabricate a completed run.

- Initial implementation from fc89aa0eb52586d462aa2e8df23654c7b6bd6c06: TypeScript entry graph passed; 54 JS and 27 Python checks passed (81 total). Found and fixed malformed feed rows, cached observation age, and storage-quota failures discarding a valid network response. Browser installation failed; visual/device testing remains pending. Production verification is the next gate.
