# UI and QA gap register

Reviewed 2026-10-12. This register distinguishes observed source gaps from tested behavior. It is not a claim that every page or control has passed browser testing.

| ID | Finding | Evidence / impact | Resolution and next check |
|---|---|---|---|
| QA-001 | Browser errors during startup and initial report rendering escaped the test error listener | The listener previously attached only after `displayReport` in full-menu tests; other tests did not record errors. | Fixed in `qa/browser.spec.cjs`: register before navigation and assert after every test. Syntax checked. Browser execution still required. |
| QA-002 | Audits had no persistent failure history | Reports inventoried unverified checks without comparing prior evidence. | Fixed: `qa/gaps.py` gives checks stable target-specific IDs, first/last observations and OPEN / NEEDS_VERIFICATION / RESOLVED states. Six regression tests cover closure, reopening, omissions and target isolation. Use `--previous` to load the prior report. |
| QA-003 | Workflow definition could be confused with completed browser verification | Browser suite exists, but a definition and test count do not establish an executed run. | Documentation clarified. Require completed CI artifacts before asserting rendered charts, layout or menu behavior passed. |
| QA-004 | Menu-open checks do not cover every menu control | Fixtures use synthetic access flags and deliberately unavailable API responses. | Remains unverified: real account transitions, all input/control combinations and independent outputs. Add deterministic expected outputs and authorized session fixtures before expanding claims. |
| QA-005 | Visual layout and device voice quality need runtime evidence | Source/DOM checks cannot establish readable layout, microphone behavior or audible speech quality. | Remains unverified: inspect desktop/mobile screenshots and test voice on a supported device; preserve muted default. |
| QA-006 | CI trigger patterns omit some backend modules | Workflow paths include `api.py`, `start.py` and UI directories but omit `secure_access.py`, `private_options.py`, `existing_engines.py` and other top-level Python modules. | Fixed: trigger paths include `*.py`, `package.json` and `package-lock.json`. Nightly workflow configured for 03:17 UTC; execution still requires a completed Actions run. |

## Review loop

1. Run the bounded coordinator and retain JSON, Markdown and suite logs.
2. Compare the next run using `--previous`; omitted checks remain unverified.
3. Convert confirmed failures into minimal regression fixtures before fixing them.
4. Rerun affected checks; inspect browser artifacts for visual findings.
5. Release only reviewed fixes, preserving authorization boundaries and explicit data-source limitations.

This is regression memory and a review process. It does not autonomously rewrite trading strategies, reveal gated information, enable paid providers or place orders.

## UI defects addressed in this release

- Removed global focus-loss blur and unreliable DevTools overlays. Existing tier checks and trading-specific content guards remain.
- Kept original full analysis as the primary form; quick research is a secondary disclosure that opens for trading/options.
- Returning to Stock research restores the original overview and loaded charts.
- Moved old fixed decision controls into report flow; long submenu strips scroll horizontally.
- Grouped event and earnings context in a disclosure, including dynamically inserted content.
- Improved mobile form sizing, report spacing and touch targets.
- Five added workspace regression tests pass. Rendering and device voice remain unverified until browser artifacts are reviewed.

Validation: all eight coordinator suites passed (193 distinct regression tests; the build repeats eight scanner tests). The coordinator inventories 50 menus, 260 routes and 1,158 functions; this inventory is not execution coverage. The 110 browser fixtures are defined but were not executed in this environment.

Production recheck: all 18 public HTML documents passed. `/today` correctly denied the anonymous audit (403); the auditor now marks its signed-in view UNVERIFIED instead of treating that denial as a page failure. Three regression tests cover this distinction, taking distinct local tests to 196. US/India stock and trading briefs returned source-labelled evidence; US options returned 51 strikes. India live options remained unavailable. Live UI assets matched the tested source byte for byte; protected option/scanner endpoints retained 401/403 denials.

## Follow-up review: data honesty and actual browser execution

GitHub Actions run 7 executed all 110 browser fixtures: 98 passed, 12 failed. Failures included a shared Analyst container defect, mobile overflow and synthetic account setup that did not survive the original role resolver. These are distinguished from live-provider and real-account verification.

Confirmed fixes under rerun:

- Legacy daily-history algo results now remain historical research with WAIT; computation time cannot masquerade as quote time. Removed price-point-to-OHLC and invented-volume fallbacks.
- Candidate guards check exact symbol/currency/interval, source quote and closed-bar age, session bounds and quote-after-signal ordering. Voice Stop prevents later expiry announcements.
- A decorative hero gradient caused exactly 242px of desktop horizontal overflow; its scoped removal preserves content.
- Overview and Stock research no longer highlight simultaneously. Scanner disclosure and footer contrast are clearer.
- Technical charts were created and immediately hidden by a delayed redraw; visible populated canvases now require browser acceptance evidence.
- Production live checks have separate persistent evidence, and run during both markets' sessions in addition to nightly regression checks.

Still requires configuration or independent verification: licensed India options credentials, US production provider entitlement, verified email delivery/enforcement, actual device voice playback, every input combination within each of 50 menus, financial strategy performance and Google Search Console ownership/submission.

## Accepted release and production checks

Runtime commit `1054fdf` deployed successfully on Render on 2026-10-12 at 05:34 UTC. GitHub Actions run 10 (`38208175150`) passed all 110 browser fixtures and 239 distinct code regression tests. The UI agent reviewed final screenshots: desktop width 1440px, mobile width 390px, all five populated report charts visible after normal tour dismissal. These are fixture results, not certification of all financial outputs.

All five changed frontend assets matched the tested source in production. Anonymous private-options requests returned 401 and watchlist requests 403. The sitemap lists the canonical homepage without the duplicate research alias. Post-deployment probes observed fresh open-session RELIANCE evidence with WAIT, and closed-session SPY WAIT. An earlier provider429 was retained as a real availability finding; one successful check is not guaranteed continuity.

India public options remained unavailable. Dhan/Tradier private-feed credentials and verified-email delivery/enforcement remained unconfigured. Do not treat existing email-tier compatibility mode as verified identity. Actual device voice playback and independent strategy performance remain unverified. Scheduled QA retains new failures; it does not silently rewrite or deploy code.
