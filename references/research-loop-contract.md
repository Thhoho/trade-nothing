# Research Loop Contract v0.18

Use this reference only when implementing, inspecting or repairing packets. The generated dispatch
prompt remains authoritative for the current Snapshot version and base hash.

## Four persistent objects

- `TaskSpec`: question, as-of, 0–10 budget, entities, mandatory fact surfaces and questions.
- `EvidenceStore`: canonical EvidenceItems and auditable SourceChecks.
- `DecisionSnapshot`: the only user-facing semantic truth.
- `RunLedger`: method identity, semantic-object hashes, dispatches, receipts, failures and budget.

No role may create another persistent thesis, Agenda, CandidateMap or report conclusion.

## Atomic LeadPacket

A LeadPacket contains one ActionIntent, new evidence/checks, one complete Snapshot replacement, an
optional challenge request, `continue_research`, and a stop reason.

ActionIntent is a call-scoped declaration in runtimes that do not expose tool hooks.
`target_snapshot_field` is a likely destination for the information gain, not a prediction that one
exact field must change. Acceptance requires two observable deltas: every `LEAD_RESEARCH` call adds
at least one new canonical EvidenceItem or SourceCheck, and the full Snapshot has a real semantic
change. An empty or semantic no-op packet is rejected without consuming a research loop.

The Snapshot version is previous + 1. `base_snapshot_sha256` equals the WorkingSet value. A failed
packet changes no persistent object. `consumed_evidence_ids` equals the exact union of all Evidence
IDs visible anywhere in the Snapshot; every HIGH EvidenceItem is additionally used as a material
change, exposed as a material gap, or explicitly disposed as non-material.

On acceptance, RunLedger binds the ActionIntent to the Lead receipt, exact submission payload hash,
base Snapshot hash, resulting Snapshot version/hash and a `snapshot_frontier` covering the evidence,
checks and Challenges visible at commit. Persisted versions form one replay-checkable chain
beginning at the deterministic empty Snapshot. Later host/Challenger appends create pending
obligations but do not retroactively invalidate that committed Snapshot. Hidden fields, destructive
history edits, broken bindings and partial hash updates fail closed before resume or rendering.

All TaskSpec questions appear exactly once in `agenda_answers`. A decision-ready HIGH question may
not remain OPEN or DISPUTED.

`continue_research` is runtime intent. It does not require the user-facing
`lowest_cost_next_validation` to say `SEARCH_NOW`; that field describes real-world validation value,
not control flow.

## EvidenceItem and typed measures

Every EvidenceItem binds one source observation to entities, optional canonical `ticker@MIC`
securities, claim IDs, a fact surface and one or more semantic roles:

```json
{
  "evidence_id": "EV-...",
  "claim": "factual prose without a second numeric rendering",
  "number": null,
  "measures": [{
    "measure_id": "MEASURE-...",
    "metric": "a_share_turnover",
    "value": 2167.1641,
    "unit": "CNY_BN",
    "dimension": "CURRENCY",
    "subject_id": "300001@XSHE",
    "as_of": "YYYY-MM-DD",
    "period": "SESSION",
    "basis": "PROVIDER_REPORTED",
    "definition": "A股市场成交额"
  }],
  "roles": ["MARKET_STATE", "TECHNICAL_STATE"],
  "source": "publisher",
  "url": "https://concrete-document",
  "date": "YYYY-MM-DD",
  "source_tier": "STRUCTURED_MARKET_DATA",
  "boundary": "SINGLE_SOURCE",
  "decision_impact": "MEDIUM",
  "entity_ids": ["E1"],
  "security_ids": ["300001@XSHE"],
  "fact_surface": "MARKET_PRICE_LIQUIDITY",
  "claim_ids": ["MV-MARKET-1"]
}
```

`number` accepts JSON `null` only. Every structured value uses `measures`; metric, value, unit,
dimension, subject, as-of, period and basis are mandatory. Metrics and bases come from the
WorkingSet registry, and the kernel supplies the canonical definition; a model may omit definition
or repeat it exactly, but cannot invent an alias. An EvidenceItem binds at most one security, and a
measure subject equals one listed `entity_id` or that single `security_id`. The deterministic
formatter owns scale and display. Model-authored literals with a monetary, percent, ratio, point,
share, duration or count unit are rejected after Unicode and Markdown canonicalization; the
renderer alone turns typed measures into user-visible values. Full normalized
EvidenceItem and SourceCheck content hashes bind host
input lineage; a dedupe signature is never treated as a content attestation.

## SourceCheck

```json
{
  "source_check_id": "SC-...",
  "entity_id": "E1",
  "security_id": "300001@XSHE or empty",
  "fact_surface": "CAPITAL_ACTIONS",
  "origin": "assigned by the runtime, not the model",
  "window_start": "YYYY-MM-DD",
  "window_end": "YYYY-MM-DD",
  "window_basis": "",
  "latest_periodic_report_date": "",
  "index_item_count": 0,
  "index_entries": [{
    "title": "announcement title",
    "url": "https://concrete-announcement-document",
    "date": "YYYY-MM-DD",
    "disposition": "OPENED_RELEVANT|REVIEWED_NOT_MATERIAL|DISMISSED_BY_TITLE",
    "reason": "why this title was opened or dismissed"
  }],
  "queries": ["actual query"],
  "official_index_url": "https://concrete-index",
  "checked_document_urls": ["https://concrete-document"],
  "acquisition_receipt_ids": ["optional SHA-256 adapter receipts"],
  "enumeration_complete": false,
  "outcome": "FOUND|NO_RESULT|INSUFFICIENT",
  "evidence_ids": [],
  "negative_scope": "required for NO_RESULT",
  "limitation": "required for INSUFFICIENT"
}
```

`FOUND` requires canonical evidence whose entity, fact surface and URL match the check. `NO_RESULT`
cannot bind evidence and requires a bounded negative scope.

For a listed company's `OFFICIAL_DISCLOSURE_INDEX`, use
`window_basis=LATEST_PERIODIC_REPORT_OR_120D`, record the latest periodic-report date and full index
item count, and begin no later than both that date and 119 days before the cutoff. Enumeration must
be complete unless the outcome is honestly `INSUFFICIENT`. A completed enumeration includes the
full title/URL/date/disposition/reason manifest; its length must equal `index_item_count`, and every opened document
must come from that manifest. The persistent EvidenceStore retains the manifest while later
WorkingSets carry only its count and SHA-256, avoiding repeated context cost. Evidence found while
enumerating the index may belong to another mandatory fact surface, but its URL must still appear
among the opened documents.

Every manifest title also has a disposition and reason. `OPENED_RELEVANT` requires both an opened
document URL and a bound EvidenceItem; `REVIEWED_NOT_MATERIAL` requires the document to have been
opened; `DISMISSED_BY_TITLE` remains auditable as a title-level exclusion. A completed official
index cannot originate from an ordinary Lead assertion. It is accepted only from `HOST_INPUT`, a
`CONTROLLED_FIXTURE`, or a caller-reported result that the host has independently reconciled and
ingested as `HOST_INPUT`. A process label alone grants no acquisition authority. This proves
acquisition lineage and classification completeness, not truth beyond the cited official source.

Loss, impairment, related-party borrowing, equity incentives, pledges, unlocks, guarantees,
financing, contracts, litigation and control changes are material-title markers. They cannot use
`DISMISSED_BY_TITLE` or generic `REVIEWED_NOT_MATERIAL`; they must be `OPENED_RELEVANT` with a
bound EvidenceItem. LOW evidence may later receive an explicit Snapshot disposition. This is a
recall gate, not a claim
that every marked document is ultimately HIGH.

For each marker EvidenceItem, the host first stores body extraction on the EvidenceItem itself:

```json
{
  "document_facts": [{
    "fact_id": "DF-...",
    "fact_type": "COUNTERPARTY|STATUS|TERMS|ECONOMIC_EFFECT|...",
    "locator": "page/section/paragraph locator",
    "excerpt": "body excerpt beyond the title",
    "document_sha256": "64 lowercase hex",
    "event_type": "controlled event type",
    "event_anchor": "host-stable transaction/event anchor"
  }]
}
```

There must be at least two substantive facts with distinct types, and `docsha256:<document_sha256>`
must be present in the binding SourceCheck's `acquisition_receipt_ids`. Lead and Challenger packets cannot
mint these facts. The Lead then selects exactly one outcome: `material_changes`,
`open_material_gaps`, or the following non-material disposition:

```json
{
  "evidence_id": "EV-...",
  "decision_dimension": "EARNINGS|CASH_FLOW|DILUTION|CONTROL|LIQUIDITY|ECONOMIC_EXPOSURE|LEGAL_REGULATORY|OPERATIONS|OTHER",
  "reason": "why those facts do not change the current decision",
  "reversal_condition": "what new fact would reverse this assessment"
}
```

A generic reason is invalid. The kernel derives and persists `event_family_id` from subject,
event type and host anchor; the Lead does not submit it and cannot assign one EvidenceItem twice.
Documents in one derived family share one aggregate `material_changes` or `open_material_gaps`
entry rather than being counted as separate events. A non-material family shares one assessment;
the user report groups that family while preserving every claim and source ID.

## Industry-to-market binding

`market_carriers_by_horizon` and `candidates_by_horizon` answer different questions. The former
names observed trading carriers, market role, why traded, closest alternative and switch condition;
it may be populated when every candidate stance is `WATCH` or `NO_SETUP`. The latter is the
recommendation boundary.

`WATCH` and `EXPLORE` are non-recommendation research states. A `WATCH` row is still useful only when
it has a concrete security, economic exposure, market role, why-now, trigger, invalidation,
crowding boundary, security-bound exposure evidence and security-bound market evidence. `NO_SETUP`
is represented by an empty candidate list or a completely empty sentinel; it cannot name or borrow
evidence for an alternative security.

A priority security does not stand alone. It binds:

- at least one `value_path_id` describing constraint → profit pool → economic exposure → carrier;
- a market view for the same horizon;
- non-empty `exposure_evidence_ids`;
- non-empty `market_evidence_ids`;
- total `evidence_ids` containing both sets.

Each security-specific EvidenceItem carries canonical `security_ids` such as `300001@XSHE` and
semantic roles. Exposure references require `ECONOMIC_EXPOSURE`; market references require
`MARKET_STATE` or `TECHNICAL_STATE`. One evidence item may honestly carry several roles, so the two
sets need not be artificially disjoint. Every item in both sets binds the candidate security. At
least one exposure item intersects the bound value path and at least one market item intersects the
same-horizon market view.

`closest_alternative` is either `UNKNOWN` with no alternative references, or a canonical
`ticker@MIC`. A named alternative requires non-empty `alternative_evidence_ids`; every referenced
item binds only that alternative security and carries `MARKET_STATE` or `TECHNICAL_STATE`. Those
references are also included in the carrier/candidate's total `evidence_ids`.

This prevents an industry story from silently becoming a stock recommendation and prevents price
action alone from masquerading as economic exposure.

If `CONDITIONAL_PRIORITY` introduces a security that was not a primary listed-company entity, the
kernel derives the full listed-company coverage set for its canonical `ticker@MIC`. Checks are keyed
by security as well as fact surface. Missing company disclosure, financial, operating, ownership,
capital, legal or market reality becomes `CANDIDATE_COVERAGE:<security>:<surface>` and blocks
`DECISION_READY`; TaskSpec is not mutated and no candidate lifecycle is added.

## ChallengePacket

```json
{
  "challenge_id": "CH-...",
  "target_claim_ids": ["CORE-1"],
  "evidence_items": [],
  "source_checks": [],
  "attacks": [{
    "target_claim_id": "CORE-1",
    "argument": "strongest evidence-bounded countercase",
    "evidence_ids": [],
    "severity": "LOAD_BEARING"
  }],
  "strongest_countercase": "single clearest countercase"
}
```

Every new Lead, seed or Challenger EvidenceItem must be bound by a SourceCheck submitted in the same
packet. The receipt binds exact prompt and payload hashes. Challenger provenance is fail-closed:

- native Codex child: `HARNESS_SUBAGENT`, `SEPARATE_CONTEXT_REPORTED`,
  `HARNESS_REPORTED`, a distinct child ID and a parent ID equal to the latest accepted Lead;
- optional external process: `HOST_PROCESS`, `PROCESS_CONTEXT_REPORTED`,
  `PROCESS_REPORTED`, matching a caller-observed host-invocation record;
- deterministic test only: `CONTROLLED_FIXTURE`;
- manual parent: `SELF_DECLARED / UNVERIFIED`, which cannot satisfy Challenger.

`HARNESS_REPORTED` and `PROCESS_REPORTED` record caller observations; neither proves context
separation, model diversity or cryptographic process attestation. The following Lead Snapshot records
`challenge_packet_sha256` from the WorkingSet and
resolves the attack as `ACCEPTED`, `PARTIAL`, `REJECTED` or `UNRESOLVED`. Target claims and evidence
may not drift from the original packet.

In Codex, start the run with `--execution-mode HARNESS_ORCHESTRATED`. When dispatch returns
`call_mode=CHALLENGER`, spawn exactly one native child with the returned prompt, save its JSON, then
build and submit the receipt:

```bash
python3 scripts/codex_research_receipt.py \
  --dispatch dispatch.json --payload challenge.json \
  --agent-id "child-agent-id" --parent-agent-id "parent-agent-id" \
  --harness-subagent --output receipt.json
python3 scripts/research_loop.py submit-challenge \
  --run-id "RUN-..." --packet challenge.json --receipt receipt.json
```

Do not invoke Claude CLI from inside Codex merely to obtain isolation. The optional
`research_host_runner.py` adapter is for an explicitly selected external-process runtime.
It is deliberately labelled caller-reported and cannot satisfy host-only official-index or body-
extraction gates by itself. The repository exposes no function that turns a caller-supplied process
dictionary into strong proof. Such proof requires an application host that owns spawn, wait, exit
status and payload capture.

## Host evidence input

Host-acquired data can be appended between Lead calls without changing DecisionSnapshot or budget:

```bash
python3 scripts/research_loop.py ingest-host --run-id "RUN-..." \
  --fragment research-input.json
```

The runtime withdraws only an unspent pending Lead dispatch, appends the host input, records its
content hash, and recompiles the prompt. For market data, generate the fragment with:

```bash
python3 scripts/research_market_input.py --input market-snapshot.json \
  --entity-id E1 --claim-id MV-MARKET-1 --output research-input.json
```

This converter requires both the upstream acquisition receipt and adapter receipt. It creates a
security-bound `MARKET_PRICE_LIQUIDITY` EvidenceItem and SourceCheck; it does not score strength,
economic exposure or recommendation stance.

Host ingest appends EvidenceStore and RunLedger only. It never writes or repairs the Snapshot. A
pending Lead dispatch is recompiled against the new evidence; an already committed Snapshot remains
valid at its recorded frontier until the next Lead replacement.

## Report views

`research_loop.py report` validates one run and emits three content-addressed, read-only derived artifacts:

- `report-user-<content-sha-prefix>.md`: concise decision view;
- `report-audit-<content-sha-prefix>.md`: the same decision body plus full evidence and execution audit;
- `report-bundle-<content-sha-prefix>.json`: hashes binding both views to the complete research run
  and RunLedger as well as run ID, state revision, TaskSpec, EvidenceStore, DecisionSnapshot, method
  identity and exact renderer source.

Before delivery, `report` runs the same verifier available for later checks:

```bash
python3 scripts/research_loop.py verify-report \
  --run-id "RUN-..." --bundle "/absolute/path/report-bundle-....json"
```

Deliver the user artifact exactly. Do not prepend a second conclusion, replace a formatted measure,
or manually repair copied Markdown; that would create a second, unaudited report truth.

## Stop, failure and resume

`REPORT` is the only final-render state. `authorize --extra-loops N` works only from that stopped
state, is the only budget extension, and cannot raise total authorization above ten.

After a recorded runtime failure with unconsumed budget, an explicit
`authorize --extra-loops 0` restores that exact failed call mode. It is authorization to retry, not
a budget increase; zero is invalid for every other stopped state.

Timeout, quota, authentication, permission and JSON failures clear the pending dispatch, record one
failure and stop the current invocation. Never replay automatically. State resume revalidates
TaskSpec, EvidenceStore, DecisionSnapshot and their RunLedger hashes before creating another call.

A hash-verified model response that violates the packet contract is recorded separately as a
`rejection`: it changes no EvidenceStore or DecisionSnapshot, consumes no research loop, clears the
spent dispatch, and places its bounded error list in the next WorkingSet. Only an explicit resume
creates the repair call. Invalid or mismatched receipts are not accepted as execution truth.
