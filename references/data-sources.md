# Data Acquisition and Governance Protocol (v0.15)

This protocol covers read-only research acquisition. It does not authorize an order, portfolio
mutation, background daemon, notification, webhook, automatic retry, or external publication.
Provider availability is environment-dependent; a successful HTTP response is not evidence that a
claim is true.

Provider scripts respect the host proxy configuration by default. Set
`TRADE_NOTHING_DISABLE_PROXY=1` only when the user explicitly authorizes bypassing configured
proxies for a bounded request.

## 1. Source order

Use the strongest source that directly supports the claim:

| Priority | Source class | Typical use | Admission rule |
|---|---|---|---|
| P0 | Regulator, exchange, issuer filing, official dataset | legal status, filings, audited figures, permits | exact document URL and date |
| P1 | Customer/counterparty record or named primary-data publisher | orders, qualification, shipment, capacity, physical constraint | claim-aligned passage and publisher identity |
| P2 | Reputable secondary reporting | context and leads | label single-source claims; trace important claims upstream |
| P3 | Forum, social post, search snippet, aggregator | hypothesis/proxy discovery only | never count as independent verification without the underlying document |

Local vault material is a lead unless its original publisher, date, URL, and claim-aligned content
are preserved. Re-publications of one upstream item do not create independent evidence.

## 2. Supported read-only helpers

The following commands fetch or transform research data; none produces a trade instruction:

```bash
# Primary/public data adapters. Availability and rate limits vary by environment.
python3 scripts/tier1_providers.py --fred DGS10
python3 scripts/tier1_providers.py --edgar NVDA --form 10-K
python3 scripts/tier1_providers.py --comtrade 156 0 854143 2023

# Configured macro observations.
python3 scripts/verified_fetcher.py --all

# Event helper.
python3 scripts/catalyst_calendar.py --sector solar

# Explicitly selected, bounded free A-share observations. It never auto-falls back.
python3 scripts/free_market_observations.py --input free-market-request.json \
  --output market-observations.json

# Provider-neutral market snapshot from frozen candidate + benchmark observations.
# The input owns source URLs; the adapter does not fetch or accept model evidence IDs.
python3 scripts/market_snapshot_adapter.py --input market-observations.json \
  --output market-snapshot.json

# Explicitly bind the complete adapter artifact to one registered run.
python3 scripts/deepthink_orchestrator_v2.py --ingest-market-snapshot \
  --run-id RUN_ID --market-snapshot market-snapshot.json

# Read-only radar preview. Persistence requires explicit authorization.
python3 scripts/logic_radar_v2.py
python3 scripts/logic_radar_v2.py --write-evolution  # only after explicit user approval
```

Quotes and trigger thresholds are context fields. They do not become
probabilities, expected returns, target prices, or sizing inputs.

The market snapshot adapter computes 5/20/60-session return and benchmark excess return, 60-session
drawdown, 20-session volume ratio and current turnover when enough observations exist. When the
selected provider supplies them, it also preserves current provider volume ratio, PE(TTM), PB,
total market cap and float market cap with explicit CNY units. Candidate
and benchmark must end on the same observed session. Its receipt binds both the input packet and the
normalized snapshot payload. It proves deterministic transformation, not that the provider is
complete or that the result predicts returns. Content-addressed receipts are integrity and lineage
proofs, not cryptographic signatures from the provider; explicit host ingestion remains the trust
root and must never be delegated to a model role.

At host ingestion, the verified artifact mints candidate-bound canonical evidence for price/relative
strength/valuation and for volume/turnover/activity. Those IDs are outputs of the trusted data plane,
not inputs supplied by a research role. Market and pricing questions may reference those host IDs
directly; they must not recreate the same observation as model-authored evidence.

### Bounded A-share request

The compatibility-named `free_market_observations.py` adapter fetches only one candidate and one
benchmark over a 90–730 calendar-day window. The caller must explicitly select exactly one of
`TUSHARE`, `BAOSTOCK`, `AKSHARE_TENCENT`, or `CSV`; there is no `AUTO` mode. A second provider
attempt is a new bounded acquisition, not an invisible fallback.

```json
{
  "as_of_date": "2026-08-11",
  "lookback_calendar_days": 180,
  "provider": "TUSHARE",
  "candidate": {
    "name": "贵州茅台", "ticker": "600519", "exchange": "XSHG",
    "asset_type": "EQUITY"
  },
  "benchmark": {
    "name": "沪深300", "ticker": "000300", "exchange": "XSHG",
    "asset_type": "INDEX"
  }
}
```

For `CSV`, add `csv_path`, the actual upstream `source_url`, and optional `source` to each asset.
Accepted headers are `date/日期`, `close/收盘/收盘价`, optional `volume/成交量`, and optional
`turnover_rate/换手率`. A local filename is not an upstream citation.

`TUSHARE` reads `TUSHARE_TOKEN` only in the parent acquisition process. For equities it joins
`daily`, `adj_factor`, and `daily_basic`, converts close to forward-adjusted values anchored to the
latest session on or before the research cutoff, and attaches current turnover, valuation, and
market-cap fields. For indices it uses `index_daily`. The token is never written to the request,
receipt, state, prompt, or report. The bounded Antigravity and Claude host adapters strip it before
launching model-role subprocesses; Codex collaboration-process isolation remains host-owned, so its
roles must consume the frozen artifact rather than invoke the provider.

`TUSHARE`, `BAOSTOCK`, and `AKSHARE_TENCENT` are market-data observations, not issuer evidence.
Missing packages, network failures, empty windows and session mismatches return explicit failure
statuses. The acquisition receipt binds provider version, request, market session and normalized
series hashes. `market_snapshot_adapter.py` verifies that receipt before calculating metrics, so
post-acquisition edits fail closed. BaoStock 0.8.9 exposes no total request timeout, so the adapter
isolates it in a child process and enforces a 20-second wall-clock boundary.

The complete adapter artifact—not only its nested `market_snapshot`—must be ingested through the
orchestrator command above. The artifact carries the complete upstream acquisition receipt and binds
the candidate identity plus normalized snapshot in the adapter receipt. Ingestion itself creates the
canonical Agenda evidence; it does not require or accept borrowed model evidence IDs. The snapshot
must contain at least one benchmark-relative return and one volume/turnover metric. Ingestion is
idempotent by receipt and rejects a conflicting artifact for the same candidate and market session.
Model-role payloads cannot invoke this command or expose the Tushare token.

### Replacing or adding a provider

Changing among built-in sources only requires changing the explicit `provider` field. Do not add an
automatic fallback: a second source is a separately visible acquisition attempt with its own receipt.

For a vendor API, database, or MCP service that is not built in, choose one of two boundaries:

1. Export candidate and benchmark observations to the `CSV` contract, including the real upstream
   URL and publisher identity; or
2. Add one collector to `free_market_observations.py` that emits the same normalized packet and
   acquisition receipt as the existing collectors.

Either route must preserve candidate identity, benchmark identity, cutoff date, a shared latest
session, source lineage, and content hashes. The downstream snapshot adapter and research kernel
must remain provider-neutral. An MCP tool response or model summary is transport output, not trusted
evidence, until the host freezes and ingests it through this contract.

## 3. Acquisition rules

1. Freeze `as_of_date` before gathering evidence. Reject documents published after the cutoff.
2. Record a concrete document URL, publisher, publication date, claim, and the relevant number or
   exact content span. A bare domain, search-result URL, or snippet is not a citation.
3. Keep raw acquisition separate from claim admission. The deterministic gate decides whether an
   item is valid, duplicate, independent, and in scope.
4. For decisive web claims, capture immutable content with `scripts/evidence_snapshot.py`, then use
   the independent Claim Verifier contract in `claim-verification-protocol.md`.
5. Never silently replace a failed primary source with a weaker source. Record the failure and label
   the fallback source class.
6. Do not retry a rate-limited or failed provider automatically unless the caller explicitly grants
   another bounded attempt.

## 4. Provider and plugin boundary

`scripts/tier1_providers.py`, `scripts/verified_fetcher.py`, `scripts/verified_crawler.py`, and
`scripts/free_market_observations.py` are
read-only acquisition adapters. A provider response must still
pass the citation and independence gates.

Optional Python providers execute local code and transmit bounded queries to the explicitly selected
service. Secrets belong in environment or host-managed credential stores and must never be written
into a report, state file, prompt, child-model environment, or installation manifest.

## 5. Failure reporting

When data cannot be obtained, return a bounded status such as `SOURCE_UNAVAILABLE`,
`RATE_LIMITED`, `AUTH_REQUIRED`, or `SNAPSHOT_FAILED`, plus the attempted source and safe next
action. Missing data remains missing; it must not be filled with model memory or an uncited number.
