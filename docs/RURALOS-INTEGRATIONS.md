# Rural OS integration audit and agent architecture

All 42 services below lack a connected external transaction provider. Public guidance and task preparation work; live quotes, bookings, payments, application submission and provider status tracking do not. A general AI model is not connected to this task assistant. No scalability load test has been performed.

| Service | External provider | Working today |
|---|---|---|
| Loans & financial schemes | Not connected | Guided task preparation and handoff |
| Worker registration & support | Not connected | Guided task preparation and handoff |
| Fraud & online safety | Not connected | Guided task preparation and handoff |
| Ration & food support | Not connected | Guided task preparation and handoff |
| Health cards & care | Not connected | Guided task preparation and handoff |
| School & scholarships | Not connected | Guided task preparation and handoff |
| Farmer support | Not connected | Guided task preparation and handoff |
| Jobs & career support | Not connected | Guided task preparation and handoff |
| Certificates & documents | Not connected | Guided task preparation and handoff |
| Land records & registration | Not connected | Guided task preparation and handoff |
| Flat purchase & registration | Not connected | Guided task preparation and handoff |
| Stocks & investing | Not connected | Guided task preparation and handoff |
| Pension, women & family support | Not connected | Guided task preparation and handoff |
| Government service complaints | Not connected | Guided task preparation and handoff |
| Aadhaar appointments & updates | Not connected | Guided task preparation and handoff |
| Digital documents | Not connected | Guided task preparation and handoff |
| Driving licence & vehicles | Not connected | Guided task preparation and handoff |
| Voter services | Not connected | Guided task preparation and handoff |
| Passport services | Not connected | Guided task preparation and handoff |
| Birth & death certificates | Not connected | Guided task preparation and handoff |
| Disability certificate & UDID | Not connected | Guided task preparation and handoff |
| Rural housing support | Not connected | Guided task preparation and handoff |
| LPG & Ujjwala support | Not connected | Guided task preparation and handoff |
| Legal aid | Not connected | Guided task preparation and handoff |
| Consumer complaints | Not connected | Guided task preparation and handoff |
| Crop insurance information | Not connected | Guided task preparation and handoff |
| Mandi & market information | Not connected | Guided task preparation and handoff |
| Skills & training | Not connected | Guided task preparation and handoff |
| Small business registration | Not connected | Guided task preparation and handoff |
| Talk to a doctor online | Not connected | Guided task preparation and handoff |
| Drinking water support | Not connected | Guided task preparation and handoff |
| Toilets & sanitation support | Not connected | Guided task preparation and handoff |
| Bus & transport services | Not connected | Guided task preparation and handoff |
| Women’s groups & livelihoods | Not connected | Guided task preparation and handoff |
| Anganwadi & nutrition support | Not connected | Guided task preparation and handoff |
| Children’s learning | Not connected | Guided task preparation and handoff |
| Weather & seasonal farm guidance | Not connected | Guided task preparation and handoff |
| Rural job cards & work records | Not connected | Guided task preparation and handoff |
| Railway tickets | Not connected | Guided task preparation and handoff |
| Airplane tickets | Not connected | Guided task preparation and handoff |
| Cab comparison & booking | Not connected | Guided task preparation and handoff |
| Holiday planning & booking | Not connected | Guided task preparation and handoff |

## Implementation
A declarative registry drives all 42 workflows. The pure task engine validates answers, rejects identity numbers and secrets, requires review, records session-local state transitions and fails closed on transaction execution. Voice uses existing browser speech adapters and exact Indian locales. No task answers are persisted or sent to providers. This is a deterministic preparation engine, not a deployed autonomous AI booking agent.

## Production integration contract (not implemented)
Each provider adapter needs capabilities (search, quote, reserve, confirm, cancel, status), country/region scope, credentials held server-side, timeouts, circuit breakers and a sandbox. Quotes must include currency, total, fees, cancellation terms and expiry. Approval must bind to the exact quote and traveller details. Create operations require durable idempotency keys. Ambiguous timeouts must enter reconciliation rather than retrying bookings. Webhooks must be authenticated and deduplicated. Payment/identity checks remain in authorised provider flows.

Run stateless API workers behind a load balancer with a durable task database, queue, per-provider rate limits and partitioning by tenant/provider. Store consent/audit events and redact logs. Pause on stale regional content. Add an LLM only for bounded intent extraction and explanations, validate its outputs against the registry, and never let model text authorize payments or invent completion. Benchmark throughput, reliability, recovery and cost before claiming scale. These are engineering requirements, not deployed infrastructure.

## Provider dependencies
Rail: authorised railway booking integration. Flights/holidays: contracted travel inventory and booking provider. Cabs: provider approval and rider OAuth. Aadhaar: the current UIDAI official flow, including user verification; no independent identity-update API is connected. Other government services: service-specific official or authorised access and state-level rule verification. Financial services remain information only; no trades, insurance or loan origination. Medical services remain navigation only; no diagnosis.

## Broader missing operations
SMS/WhatsApp/push reminders, staffed helpers, payments/receipts, provider status feeds, live weather/market feeds, full local-rule automation, native account integration and signed store builds remain unavailable. Existing secure website record storage is an internal feature, not evidence of provider integration.
