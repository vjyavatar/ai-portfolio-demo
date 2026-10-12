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
