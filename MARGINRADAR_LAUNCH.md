# MarginRadar on Celesys

Prepared for https://celesys.ai/marginradar/. The public landing and interactive cost calculator run on the existing FastAPI service. The signed-in application, database and native plugin remain at https://marginradar.vjyrcks.chatgpt.site; CTAs disclose this explicitly. This is not a full backend migration and does not proxy authentication.

The existing startup hook now attaches MarginRadar instead of the planner; api.py is byte-for-byte unchanged. /nextstep and every nested planner page redirect to /marginradar/. The legacy sitemap URL redirects to the new XML sitemap, preserving the current robots declaration. Historical planner source remains in Git but is not served. No stock routes, stock UI, market jobs, service start commands, dependencies, credentials or DNS settings change.

## Deployment
Confirm the Render workspace and service branch. Merge this branch only when the live service and repository branch are confirmed. After deployment verify /marginradar, /marginradar/, calculator assets, /nextstep, /nextstep/guides/, /robots.txt, the stock homepage and a stock API. Verify secure-workspace links and sign-in separately. Rollback by reverting this commit; no migrations on Render.

## LinkedIn announcement — publish only after URL verification
I’m opening the free MarginRadar pilot by Celesys for refurbished-laptop resellers.

A cheap supplier quote is not the whole deal. Check shipping, repairs, selling fees and return allowances before you buy.

Try the calculator, then import your own offers, set buying rules and track opportunities in the signed-in workspace.

https://celesys.ai/marginradar/

Looking for five resellers to test it with a real supplier quote and share feedback. No payment required. Estimates are not guaranteed profit; live-data connections are still being configured.

## Commercial boundaries
Do not advertise fully autonomous purchasing, guaranteed earnings, live stock coverage or paid availability. Marketplace/AI credentials, working schedules, paid entitlements, merchant setup, business/support information and provider/browser tests remain required before a paid launch. Advertising is an organic LinkedIn announcement only; no ad budget is assumed and no mass messages are authorized by this file.
