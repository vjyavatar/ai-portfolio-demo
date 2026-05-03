# Celesys v4.63.20 — Fix: r63.18 sections invisible on OLD render path

You showed me a screenshot of a full DD report — Earnings Move, Institutional Summary, Insider Activity, Institutional Ownership, Risk-Adjusted Returns — and **NONE of the 4 new sections appeared anywhere.**

Real bug. Found the root cause. Fixed it.

---

## What was wrong

Your codebase has **TWO different DD render paths**:

1. **NEW path** (Aladdin redesign at line 12466): `id="sec-verdict-strip"` with `cs-dd-verdict` classes  
2. **OLD path** (legacy at line 1905): `id="sec-verdict"` inside `.sc` cards with tab/subtab structure

I built r63.18 against ONLY the NEW path. My polling looked for `#sec-verdict-strip`. That ID doesn't exist on the OLD path. Your DD report renders via the OLD path → my polling never finds an anchor → never injects.

Your screenshot is unmistakably the OLD path (sections like "Earnings Move Intelligence", "Insider Activity" with the `.sc` card visual style — those are old-path components).

---

## The fix — handle both paths

**Polling now tries both selectors:**
1. First checks for `#sec-verdict-strip` (new Aladdin path)  
2. If not found, checks for `#sec-verdict` (old legacy path)
3. Walks up to find the containing `.sc` card on old path
4. Extracts ticker from `.cs-dd-verdict__sym` (new) OR `window._ddLastSymbol` (old)
5. Inserts after the verdict element regardless of which path

**Elevator pitch reads from both:**
- New path: `.cs-dd-verdict__score` / `__pill` / `__name`
- Old path: parses from card text + falls back to `window._lastReportData`
- Last resort: regex match for "STRONG BUY / 92/100" patterns in card text

---

## Pre-ship verification

- ✅ Dual-path detection (8 references in code: both `sec-verdict-strip` and `sec-verdict`)
- ✅ r63.20 markers present in 3 places
- ✅ All Python compiles, JS syntax OK, app.min.js byte-identical
- ✅ Version v4.63.20 across all files

### Behavioral test passes BOTH paths
| Path | Anchor | Symbol Source | Result |
|---|---|---|---|
| NEW (Aladdin) | `#sec-verdict-strip` | `.cs-dd-verdict__sym` | ✅ detected, sym=MU |
| OLD (legacy) | `#sec-verdict` → walk up to `.sc` | `window._ddLastSymbol` | ✅ detected, sym=SNDK |

---

## Deploy

```bash
unzip celesys_v4_FINAL_DEPLOY.zip
cd celesys_v4_FINAL_DEPLOY/
git add -A
git commit -m "v4.63.20: Fix r63.18 sections — handle BOTH render paths (old + new)"
git push
```

Wait ~3 min, **HARD-REFRESH** (Ctrl+Shift+R / Cmd+Shift+R).

---

## Verify after deploy

1. `curl https://celesys.ai/api/version` → `"version": "v4.63.20"`
2. Hard-refresh https://celesys.ai
3. Generate Deep DD for any ticker (try **MU** or **SNDK**)
4. **Within 1 second of the report appearing**, the 4 sections should now show:
   - Either right after the green "STRONG BUY CANDIDATE / 92/100" verdict strip (new path), OR
   - Right after the "Verdict" section card (old path)
   
5. Sections to appear:
   - 🎯 **Elevator Pitch** (navy gradient — auto-shows immediately)
   - 🧠 **Deep Insights** (white card with "Generate insights →")
   - 📈 **12-Month Scenarios** (white card with "Run scenarios →")
   - 🏛️ **Competitor Benchmark** (white card with "Compare peers →")

---

## Honest accountability

This is bug #6 in the pattern today: **I shipped a feature, the feature had a bug, I fixed it.**

Same root cause as the others: **I wrote integration code without verifying the actual DOM structure I was integrating with.** I assumed `#sec-verdict-strip` was the canonical verdict element. I never checked if there were multiple render paths. There were. There are. r63.18 only worked on one of them.

This is the SECOND time today I assumed a single canonical element/variable when the codebase actually had multiple (the first was `_authedEmail` vs `_verifiedEmail` for login). Same lesson, different shape: **read the actual code structure before integrating, don't guess from one example.**

For the next session: I'll grep for ALL occurrences of similar IDs/elements and confirm which path renders for which user, before writing code that depends on a specific path.

---

## Files changed

| File | Change |
|---|---|
| `static/app.js` | Polling rewritten to handle both paths (~50 lines). Inject function accepts anchor info. Elevator pitch reads from both paths. |
| `static/app.min.js` | Synced |
| `api.py` | Version stamp v4.63.20 |
| `index.html` | Cache-bust + version stamps |

No backend changes. The 3 endpoints from r63.18 are unchanged and ready.

---

## After this verifies

If 4 sections appear → r63.18 feature is done, sleep, real users tomorrow.

If sections still don't appear → tell me:
1. Which ticker did you try?  
2. Do you see EITHER `#sec-verdict-strip` OR `#sec-verdict` if you Inspect Element on the verdict area?
3. Any console errors?

That gives me precise data to fix without more guessing.
