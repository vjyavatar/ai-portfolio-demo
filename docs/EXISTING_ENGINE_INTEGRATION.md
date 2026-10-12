# Existing-engine presentation integration

The five-part research workbench now calls the established stock-dashboard,
decision-engine and options-quick functions through dependency injection.
No scoring formulas or trade thresholds change. Additional paid AI remains opt-in.

Stock briefs retain the original verdict (including insufficient-data blocks),
quality/valuation scores, growth calculations, qualitative engine results,
risks and invalidation conditions. Trading briefs retain market assessment,
signal, trend metrics and modelled levels. Confidence is labelled as an engine
rating, not a calibrated probability.

The explorer now reads /api/existing-option-chain, a presentation adapter over
options-quick: the existing connected Upstox/NSE flow for India and Yahoo for US.
Only the actual returned expiry is offered. Spot-only failures remain unavailable.
Per-contract quote times are absent in legacy responses: freshness stays unverified.
Ambiguous legacy zero/missing fields remain null; modelled Greeks and placeholder
OI changes are not published as source facts. Expired/invalid expiry rows are withheld.
The dedicated /api/option-chain adapter and its public-provider opt-in gates remain.
No credentials, new entitlements, or provider permissions are changed.

A concrete production failure in _algo_signal_impl was repaired: len(volumes)
replaces ambiguous NumPy truth evaluation, and _safe_int replaces a misspelled helper.
A regression test executes the actual production expression with an array that
rejects boolean evaluation. Adapter tests cover original verdict preservation,
missing timestamps, absent chains, real expiry selection and error redaction.

Provider availability is independent of integration. Do not advertise streaming
or guaranteed real-time data. A response retrieval time is never a quote timestamp.
