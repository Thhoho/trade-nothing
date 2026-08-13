# Data Sources and Replacement Contract

Trade Nothing does not make one vendor authoritative for conclusions. A provider supplies an
observation; the Lead turns only source-bound observations into EvidenceItems. Official disclosures
remain the fact gate for company events.

## Recommended A-share stack

| Need | Default | Free fallback | Boundary |
|---|---|---|---|
| Announcements and company events | exchange / issuer official disclosure | CSRC or issuer mirror | enumerate the official index first |
| Trading calendar and stable structured fields | Tushare Pro when configured | BaoStock | provider row is contextual until source/date are recorded |
| Daily OHLCV / adjustment factors | Tushare Pro | BaoStock; AKShare as bounded fallback | never infer company exposure from price alone |
| Fast public snapshots / concept exploration | AKShare | public web source | unstable endpoints may degrade; record provider and cutoff |
| Overseas macro / filings | official central bank, statistics agency, SEC/issuer | public data portal | primary source preferred |

BaoStock is the zero-cost baseline. AKShare is useful but its upstream endpoints change, so warnings
and empty frames must be treated as typed provider failure rather than silently accepted data.
Tushare is the preferred optional structured source after the user configures a token.

## Configure Tushare Pro

Set one host environment variable; do not edit Skill files and do not configure each agent copy
separately:

```bash
launchctl setenv TUSHARE_TOKEN "YOUR_TOKEN"
```

For the current terminal session:

```bash
export TUSHARE_TOKEN="YOUR_TOKEN"
```

Restart Codex, Claude or Gemini after changing the launch environment. Verify presence without
printing the secret:

```bash
python3 -c 'import os; print("configured" if os.getenv("TUSHARE_TOKEN") else "missing")'
```

The token is host-only. It must never enter a prompt, TaskSpec, EvidenceStore, RunLedger receipt,
report, installed Skill file, Git commit or diagnostic excerpt. Model subprocess environments are
sanitized; a tool that needs the provider should execute through a narrow host-side adapter.

## Provider adapter contract

Any replacement source should return a bounded observation object with:

```json
{
  "provider": "provider name",
  "dataset": "exact endpoint/table",
  "symbol": "canonical identity",
  "as_of": "YYYY-MM-DD",
  "retrieved_at": "ISO datetime",
  "source_url": "concrete documentation or record URL",
  "rows": [],
  "adjustment": "none|qfq|hfq|not_applicable",
  "calendar": "exchange calendar identity",
  "status": "READY|NO_RESULT|DEGRADED",
  "limitation": "bounded limitation"
}
```

Requirements:

- normalize ticker, exchange, dates, units, currency and adjustment mode before comparison;
- freeze an explicit as-of and reject future rows;
- distinguish `NO_RESULT` from provider failure;
- use bounded timeout and row limits;
- record endpoint and provider version when available;
- never auto-fallback in a way that merges incompatible adjustment or calendar semantics;
- do not convert an API success into `FACT` without a concrete source/date boundary.

To replace a provider, implement this observation contract and map the output into canonical
EvidenceItems/SourceChecks. The research core does not need a new state machine or vendor-specific
decision logic.

## Active bounded market path

The installed Skill includes a three-step host-side path:

```bash
python3 scripts/free_market_observations.py \
  --input market-request.json --output market-observations.json
python3 scripts/market_snapshot_adapter.py \
  --input market-observations.json --output market-snapshot.json
python3 scripts/research_market_input.py \
  --input market-snapshot.json --entity-id E1 --claim-id MV-MARKET-1 \
  --output research-input.json
python3 scripts/research_loop.py ingest-host \
  --run-id "RUN-..." --fragment research-input.json
```

`market-request.json` names one explicit provider (`TUSHARE`, `BAOSTOCK`, `AKSHARE_TENCENT`, or
`CSV`), one candidate, one benchmark, an as-of date, and a 90–730 day bounded lookback. There is no
automatic provider fallback. The first adapter freezes source rows and a content-addressed
acquisition receipt; the second calculates as-of relative returns, drawdown, volume/turnover and
available valuation/liquidity fields without making a recommendation. The third requires both
receipts and emits one security-bound EvidenceItem/SourceCheck fragment. `ingest-host` appends it to
EvidenceStore/RunLedger, consumes no model budget, writes no conclusion, and recompiles any unspent
Lead dispatch.

Run credentialed acquisition in the host: child-model environments deliberately do not receive
`TUSHARE_TOKEN`. The converter maps the observation into `SINGLE_SOURCE`,
`fact_surface=MARKET_PRICE_LIQUIDITY`, `security_ids=["ticker@MIC"]`, semantic roles and typed
measures. Every metric comes from the controlled registry and carries raw value, canonical unit,
explicit `subject_id`, as-of, period and registered basis; the kernel supplies its definition.
`number` stays JSON `null`. The receipt-bound SourceCheck and full EvidenceItem content are hashed
into host-input lineage. Structured-provider success is market context, not proof of company
economic exposure.

## Installation

The deterministic Skill has no mandatory third-party dependency. Optional local providers can be
installed independently after approval:

```bash
python3 -m pip install baostock akshare tushare
```

Provider installation and token configuration are host concerns. `make install` synchronizes Skill
code to agent environments but never copies credentials or changes Python packages.
