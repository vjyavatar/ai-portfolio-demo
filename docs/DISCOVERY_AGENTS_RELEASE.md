# Discovery, research agents and option chains

## User-facing release

- Lightweight server-rendered homepage at `/`; existing full research retained at `/research`.
- `/agents`: stock, trading and option-chain modes with the requested five-part brief: Assessment → Evidence → Counterargument → Missing data → Next check.
- Visible Data steward → Research analyst → Skeptical critic → Coordinator trace. The analyst and critic are separate bounded model calls using the existing Anthropic integration, when explicitly enabled. Calculated assessment and evidence remain unchanged. Rejected drafts are not published.
- `/options/india` and `/options/us`: expiry selection, calls/puts, OI, OI change where supplied, bid/ask, IV, delta, volume, timestamps and snapshot PCR only when all returned strikes have both OI values.
- India: NIFTY, BANKNIFTY, FINNIFTY, SENSEX via Upstox. US: provider-supported standard stock/ETF options via Tradier; adjusted and index contracts are outside the validated scope.
- Three educational guides plus methodology, crawlable content, canonical URLs, social metadata, modest WebPage/Article structured data and expanded sitemap.
- Preserved existing GA4 property with `workspace_open` navigation events; no symbols, emails or research payloads in custom events. Analytics collection and Search Console ownership still need production verification. Existing Google verification token is retained.
- Removed unsupported homepage/search marketing and fabricated daily sitemap modification dates; removed API-key prefix from health response.

## Deployment

Use the existing GitHub repository and existing Render service (`start:app`). No new paid infrastructure or dependencies. Preserve all existing env vars. Merge only after reviewing the diff and identifying the correct Render workspace/service. Source branch is `improve/discovery-options`.

Environment switches (default off):

| Variable | Purpose |
| --- | --- |
| `CELESYS_PUBLIC_OPTIONS_IN=true` | Enable public India snapshots only after verifying provider display permissions. |
| `CELESYS_INDIA_OPTIONS_DATA_TOKEN` | Optional dedicated Upstox data token. Otherwise reuse the existing server token supplier. Never put a token in client code. |
| `CELESYS_PUBLIC_OPTIONS_US=true` | Enable public US snapshots only after verifying provider display permissions. |
| `CELESYS_OPTIONS_DATA_TOKEN` | Existing dedicated Tradier data credential. |
| `CELESYS_AGENTS_AI_ENABLED=true` | Enable bounded analyst/critic requests on user-triggered briefs. |
| `ANTHROPIC_API_KEY` | Existing server-only key; no new provider account is required. |
| `CELESYS_AGENT_MODEL` | Optional model override; defaults to the Haiku model already used by the repository. Verify account availability. |

The new option explorer's public display gates are separate from the existing SPY/QQQ option-candidate panel. Existing private account market-data access alone does not establish public redistribution permission. Expired tokens and upstream access failures fail closed.

AI pilot budget is at most 20 review runs (two model calls each) per rolling 24-hour process window, at least 60 seconds between uncached runs, one in-flight review per process. Restarting or adding workers resets/multiplies this in-memory limit. Keep AI disabled for a multi-worker public rollout until distributed quotas/authentication and provider spending limits are configured. This is a pilot workflow, not unattended market surveillance or broker execution.

## Data and trust

India chain schema does not include quote timestamps; do not call snapshots real-time. Fetch time is displayed separately. US quotes are recent only when every displayed side has non-future bid and ask timestamps within five minutes; this does not establish that the exchange is open. OI/Greeks update separately. Unknown OI stays null; zero remains zero. PCR uses returned coverage only.

Stock brief reuses the current stock dashboard, extracts numeric fundamental fields only, and flags mixed reporting periods and missing original filing citations. Do not label those inputs independently verified. AI receives evidence IDs, not arbitrary user prompts. Analyst citations are schema-checked and critic approval is required, but two model calls do not prove factual correctness.

Trading signals and warmup logic are unchanged. No first-105-minute strategy change is included; changing it requires separate historical evaluation.

## Validation

- `python -m unittest discover -s tests -p 'test_discovery.py' -v`
- `python -m unittest discover -s tests -p 'test_trading*.py' -v`
- `npm run build`
- Compile changed Python modules and `git diff --check`.
- Local tests mock provider and AI responses; no credentials or paid API calls used.
- Full rendered browser QA and authenticated live-feed verification remain gates if browser infrastructure is unavailable.

## SEO and acquisition follow-through

1. In the existing Google Search Console property for `https://celesys.ai/`, submit `/sitemap.xml` after deployment. Inspect `/`, `/agents`, `/options/india`, `/options/us` and the guides; request indexing where appropriate. Search-engine indexing is not guaranteed.
2. Verify the existing GA4 property receives `page_view` and `workspace_open`. Do not treat the source measurement ID as proof of a connected analytics account.
3. Review Search Console impressions, clicks, CTR and query relevance alongside guide-to-workspace clicks weekly. Baseline first; no fabricated traffic metrics.
4. Publish original, sourced educational research consistently. Review material claims, dates and data provenance before publication. Avoid templated ticker pages without substantial distinct value.
5. Distribution posts and outreach are not sent by this release. Link to one useful guide and its relevant workspace when the owner authorizes publication.

## Rollback

Revert this release commit. Legacy `index.html` returns to `/`; no data migration. Existing browser-local paper journals remain intact. Environment flags can be disabled independently to stop public feed or AI usage.
