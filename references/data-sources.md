# Data Acquisition and Governance Protocol (v0.13)

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

# Read-only radar preview. Persistence requires explicit authorization.
python3 scripts/logic_radar_v2.py
python3 scripts/logic_radar_v2.py --write-evolution  # only after explicit user approval
```

Quotes and trigger thresholds are context fields. They do not become
probabilities, expected returns, target prices, or sizing inputs.

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

`scripts/tier1_providers.py`, `scripts/verified_fetcher.py`, and `scripts/verified_crawler.py` are
read-only acquisition adapters. A provider response must still
pass the citation and independence gates.

Custom providers or Python plugins are not part of the published bundle. They execute local code and
may transmit credentials or queries, so a host may load one only through a separately reviewed and
explicitly authorized integration. Secrets belong in environment or host-managed credential stores
and must never be written into a report, state file, prompt, or installation manifest.

## 5. Failure reporting

When data cannot be obtained, return a bounded status such as `SOURCE_UNAVAILABLE`,
`RATE_LIMITED`, `AUTH_REQUIRED`, or `SNAPSHOT_FAILED`, plus the attempted source and safe next
action. Missing data remains missing; it must not be filled with model memory or an uncited number.
