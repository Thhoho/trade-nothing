# Trade Nothing

Evidence-bound investment research that finds current material facts first, connects industry
economics to market behavior by horizon, and produces one auditable decision snapshot.

[中文](README_zh.md) · [Architecture](docs/architecture.md) ·
[v0.18.0 release](docs/release-v0.18.0.md) · [Data sources](references/data-sources.md)

> **Current daily-use method: the thin constitution (`rebuild/SKILL.md`).** It is a one-page
> prompt-level skill (zero mandatory Python) validated by two blind A/B gates — closed-packet
> reasoning (6 cases, [`docs/rebuild-ab-phase1-results.md`](docs/rebuild-ab-phase1-results.md)) and
> a live retrieval A/B ([`docs/rebuild-ab-phase2-results.md`](docs/rebuild-ab-phase2-results.md)) —
> at 0.91–1.02x baseline token cost. Cognitive anchors persist in [`anchors/`](anchors/). The v0.18
> kernel below remains the auditable engine reserved for a future online service.

## What it is

Trade Nothing is a Skill and a small deterministic harness for company, event, industry, thematic,
A-share, commercial-space, AI-chain and photovoltaic research.

It is designed around a simple product test: under the same model, as-of and comparable budget, the
Skill must find more decision-changing truth and produce a more useful answer than an unassisted
run. More roles, more URLs and a longer report are not value.

The active v0.18 kernel persists only:

- `TaskSpec`: what must be answered;
- `EvidenceStore`: what was actually observed and checked;
- `DecisionSnapshot`: the only user-facing semantic truth;
- `RunLedger`: what the runtime actually executed.

One Value Lead writes the complete Snapshot. An optional child Challenger attacks exact
load-bearing claims in a separate context but cannot write conclusions. Deterministic code validates
coverage, evidence lineage, append-only transitions, budget and execution receipts. The report
renderer creates user and audit views from the same validated Snapshot.

Scope ends at a Deep Research Report and conditional advice. It never owns orders, positions,
portfolios, target prices, publication or downstream handoff.

## v0.18.0: harness-first, portable semantic core

v0.18 keeps the four-object semantic kernel from v0.17 and removes the remaining runtime mismatch:
inside Codex, native tools and one native child agent are the default execution path. External model
CLIs are optional adapters, not a hidden prerequisite. Research follows one bounded Agent Loop:

```text
WorkingSet -> one ActionIntent -> evidence/tool/optional Challenger
           -> atomic DecisionSnapshot -> validation -> stop or next action
```

The important product changes are:

- official disclosure/status index enumeration precedes thematic keyword search; potentially
  material titles such as loss, impairment, borrowing, incentives, pledges and unlocks cannot be
  dismissed with a template title reason;
- every HIGH fact must reach the report, remain an explicit gap, or receive a reasoned disposition;
- a committed Snapshot is validated against its own evidence frontier; later host or Challenger
  appends create pending obligations instead of retroactively invalidating or rewriting history;
- every paid research loop must add an observation and produce a real semantic Snapshot delta;
- all TaskSpec questions survive in every full Snapshot replacement;
- evidence can carry several honest roles; market carriers describe what capital is trading while
  qualified candidates separately express recommendation stance and company reality coverage;
- opaque numeric strings are rejected. Typed measures own unit, scale, period, basis and display,
  while a controlled metric registry, explicit subject and registered basis prevent a value from
  being borrowed across facts or securities;
- material titles require host-extracted body excerpts with locators and a SourceCheck-bound
  document hash before the Lead can choose one exclusive outcome; event families are derived rather
  than freely invented;
- a named closest alternative must be a canonical security with its own market evidence;
- frozen Tushare/BaoStock/AKShare/CSV observations now convert directly to canonical host input;
- Codex uses a native child Challenger by default. Reports distinguish `HARNESS_REPORTED`,
  caller-observed `PROCESS_REPORTED` and `UNVERIFIED` rather than overclaiming one generic verified mode;
- the optional CLI adapter cannot mint strong process proof. A future strong attestation must come
  from an application host that owns process creation, waiting and result capture;
- user and audit reports are pure, content-addressed, read-only views; a verifier recomputes their
  complete run/RunLedger, state, method, renderer and content bindings before delivery;
- timeouts, quota, permission and JSON failures stop once and never auto-retry;
- old engines are excluded from the active method allowlist and installed Skill bundle.

**Calibration status:** v0.18.0 is implemented and deterministic regression gates pass. It remains
`UNBENCHMARKED_METHOD_CHANGE`: engineering correctness is not evidence of research effectiveness or
alpha. Blind same-model forward comparisons are still required.

The [v0.10 foundation design](docs/hypothesis-led-research-v0.10.md) and later historical engines
remain available for archaeology and replay, not as active semantic authority.

## Use

### Standard Q&A

Ask a normal investment-research question. The Skill answers directly, uses current sources when
needed, and states as-of and evidence boundaries. It does not create a registered run for simple
questions.

### `-deepthink2`

Give an exact 0–10 round budget. A round is a ceiling, not a quota. The loop stops early when no
currently executable action can materially change the decision.

Before start, the parent agent compiles explicit `primary_entities` and research questions in the
same work window. Topic-only deep runs are rejected rather than silently choosing generic fact
surfaces.

In Codex, use the native harness path:

```bash
python3 scripts/research_loop.py start \
  --topic "your question" --task-spec-json task-spec.json --round-budget 3 \
  --execution-mode HARNESS_ORCHESTRATED
```

Follow the returned WorkingSet with native tools. If it requests `CHALLENGER`, give that exact
bounded prompt to one Codex child agent, record a `HARNESS_REPORTED` receipt, submit its JSON, and
let the parent Lead resolve it. Resume or inspect by immutable run ID:

```bash
python3 scripts/research_loop.py status --run-id "RUN-..."
python3 scripts/research_loop.py dispatch --run-id "RUN-..."
python3 scripts/research_loop.py verify-report --run-id "RUN-..." --bundle "/path/report-bundle-....json"
```

The exact packet and receipt workflow is in
[the research-loop contract](references/research-loop-contract.md). A manual parent receipt proves
prompt/payload lineage but remains `SELF_DECLARED / UNVERIFIED`. The optional
`research_host_runner.py` adapter is only for an explicitly chosen external process runtime; Claude
CLI authentication or permission failure cannot block the native Codex path. Its receipt is
`PROCESS_REPORTED`, not independent execution proof, and its output must be explicitly ingested by
the host to satisfy official-index or document-body gates.

## Install

### Natural-language installation for an agent

Use this short instruction:

> Install or update the `trade-nothing` Skill from the latest reviewed `main` commit. Verify the
> commit and source sync. Do not start a research run.

The agent should use a temporary checkout, record `git rev-parse HEAD`, detach it with
`git switch --detach`, and run:

```bash
git clone --branch main --depth 1 https://github.com/Thhoho/trade-nothing.git <checkout>
python3 <checkout>/scripts/install_skill.py --source <checkout> --targets <target>
```

For this development checkout, sync Codex, Claude and Gemini together:

```bash
make install DEV_DIR="<checkout>"
```

Installation copies only the active allowlisted bundle. Retired managed code in a target is moved
to a recoverable quarantine; runtime state and credentials are untouched.

## Tushare Pro configuration

Configure one host environment variable, not each agent directory:

```bash
launchctl setenv TUSHARE_TOKEN "YOUR_TOKEN"
```

For one terminal session, use `export TUSHARE_TOKEN="YOUR_TOKEN"`, then restart the relevant app.
Tushare credentials never enter role prompts, state, receipts, reports, Git or installed Skill
files. BaoStock is the free baseline and AKShare is a bounded fallback. See
[data sources](references/data-sources.md) for the replacement contract.

## Validate

```bash
python3 scripts/test_research_core.py
python3 scripts/test_research_loop.py
python3 scripts/test_current_reality_regression.py
python3 scripts/test_research_host_runner.py
python3 scripts/test_research_market_input.py
python3 scripts/version.py
make test
```

These gates prove contracts and execution behavior, not market usefulness. The forward product gate
requires zero frozen P0 omissions, no false challenge provenance, no semantic contradiction, usefulness
above baseline in at least four of five diverse cases, and cost no greater than 1.5 times baseline.

## Daily topic selection

`make daily` produces one market observation and one dynamic topic proposal with a 0–10 round
budget. It does not start deep research, retry, publish, deploy or trade:

```bash
make daily
```

## License

MIT. Research output is not investment advice or an execution authorization.
