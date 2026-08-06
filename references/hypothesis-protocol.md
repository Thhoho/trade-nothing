# Hypothesis Garden and ProxyTrail Protocol

This protocol defines Trade Nothing's exploration ledger. It preserves bold,
testable conjectures without weakening the evidence, candidate-admission, or
human decision gates.

The exploration ledger is deliberately non-promotional. It cannot create an
`OpportunitySeed`, invoke `CandidateScreen`, write a thesis or decision, recommend
a trade, or size a position. An exploration item that reaches
`EVIDENCE_BACKED` is still only a researched hypothesis. A separately emitted
and independently validated object must pass the existing promotion workflow.

## Public engine contract

`scripts/hypothesis_engine.py` exposes these stable entry points:

```python
issues = validate_frame(frame)
ledger = initialize(frame)                   # ledger or None
state["hypothesis_ledger"] = ledger
audit = ingest_round(state, round_num, detective, inquisitor)
counts = summary(state)
next_probe = exploration_action(state)
threshold = break_even_threshold(upside, downside)
projection = report_view(state, limit=5)
```

The state key is exactly `hypothesis_ledger`. The engine accepts either the
enclosing state or a ledger where appropriate. It is deterministic and has no
network, promotion, or execution side effects.

## Research intent and compatibility

`frame.research_intent` is one of:

- `THESIS_CHALLENGE`
- `OPPORTUNITY_DISCOVERY`
- `HYBRID`

New callers should always set it explicitly. For legacy frames, a Landscape map
or an `OPPORTUNITY_PATH` crux implies `HYBRID`; otherwise the engine infers
`THESIS_CHALLENGE`.

A valid legacy `landscape_map.paths` array is deterministically projected into
the exploration ledger when no explicit garden exists. Legacy paths may retain
`hypothesis_status=HYPOTHESIS` and need only their historical Landscape fields;
the projection does not invent missing scenarios, proxy routes, or evidence.
Projected paths start at `HYPOTHESIS_ONLY` and retain their path/crux context.

`OPPORTUNITY_DISCOVERY` and `HYBRID` require an initial hypothesis garden.
`THESIS_CHALLENGE` may omit it. If a challenge frame includes a garden, the
garden must satisfy the same complete contract; a smaller, looser garden is not
a compatibility path.

## Framer garden contract

The Framer writes:

```json
{
  "hypothesis_garden": {
    "wild_hypotheses": []
  }
}
```

The garden contains 5–7 entity-agnostic paths and covers all five archetypes:

- `DIRECT_CAPTURE`
- `BOTTLENECK_OWNER`
- `ENABLER_OR_INPUT`
- `SUBSTITUTE_OR_AVOIDANCE`
- `ADVERSE_EXPOSURE`

Every path carries:

- unique `hypothesis_id` and `path_id`;
- an existing `linked_crux_id`;
- `hypothesis_status=HYPOTHESIS_ONLY`;
- `hypothesis`, `archetype`, `surprise_if_true`, and the
  `strongest_alternative_explanation`;
- symmetric, non-empty `scenario_paths.bull`, `.base`, and `.bear`;
- a 3–6 node `value_transfer_chain`;
- `economic_capture_test`, `pricing_question`, and
  `cheap_discriminating_test`;
- 1–3 `proxy_plan` routes;
- `falsifier`; and
- an ISO `expiry_date` after the frame's `as_of_date`; and
- exactly two distinct bounded `search_queries`.

Each Framer `proxy_plan` route carries `proxy`, `why_diagnostic`,
`publisher_class`, and `bounded_query`.

### A plan is not a trace

`proxy_plan` describes where a role might look. It is not an observed clue and
does not advance maturity. The engine preserves it separately and initializes
every Framer path as `HYPOTHESIS_ONLY`.

Framer `proxy_trails` are forbidden and are physically ignored during
initialization even if a caller bypasses frame validation. Only a dispatched
Detective or Inquisitor may add an observed ProxyTrail.

Only a Detective or Inquisitor that encounters an observation may emit a
top-level `proxy_trails` item. Suggested queries, publisher classes, and
unexecuted routes never count as evidence.

## Role payload contract

Both research roles may return:

```json
{
  "hypothesis_sparks": [],
  "proxy_trails": []
}
```

A role spark uses:

```json
{
  "spark_id": "HS-D-1-1",
  "origin_crux": "C1",
  "landscape_path_id": "L1",
  "status": "HYPOTHESIS_ONLY",
  "observation": "cited observation or explicit unverified clue",
  "hypothesis": "bold causal conjecture",
  "surprise_if_true": "how the map changes",
  "causal_chain": "A -> B -> C",
  "strongest_alternative_explanation": "best ordinary explanation",
  "disconfirming_observation": "what kills the conjecture",
  "cheap_discriminating_test": "next bounded test",
  "evidence": []
}
```

The engine keeps observation separate from inference, maps
`surprise_if_true` to `why_nonconsensus` when the latter is absent, and maps
`disconfirming_observation` to `falsifier` when needed. A submitted state or
status cannot self-promote the hypothesis.

A role trace uses:

```json
{
  "trail_id": "PT-D-1-1",
  "spark_id": "HS-D-1-1",
  "origin_crux": "C1",
  "status": "HYPOTHESIS_ONLY",
  "proxy": "observed indirect datum",
  "why_diagnostic": "causal link it separates",
  "next_source_class": "primary publisher class",
  "bounded_query": "one bounded next query",
  "stop_condition": "when to abandon this trail",
  "evidence": []
}
```

For compatibility, `causal_link` is accepted in place of `why_diagnostic`.
Missing direction defaults to `AMBIGUOUS`; explicit directions are limited to
`SUPPORTS`, `CONTRADICTS`, and `AMBIGUOUS`. Both `spark_id` and canonical
`hypothesis_id` resolve a trace. Sparks are ingested before standalone traces,
so a trace may bind a new spark emitted in the same role payload.

The engine derives a statement-stable canonical hypothesis ID while retaining
role and Framer IDs as aliases. Repeated statements, aliases, traces, and
citations merge deterministically. Conflicting directions on the same proxy
become `AMBIGUOUS` rather than creating two artificial traces.
The merged trace also preserves `direction_variants`,
`direction_contested`, and `direction_bindings`. Each binding keeps the
direction, evidence IDs, source agent, round, origin crux, route, and any
authorized action ID, so the summary never erases the underlying tension.

## Maturity states

The active state machine is:

`HYPOTHESIS_ONLY -> TRACED -> EVIDENCE_BACKED`

- `HYPOTHESIS_ONLY`: no observed ProxyTrail is attached.
- `TRACED`: at least one ProxyTrail exists, with or without accepted evidence.
- `EVIDENCE_BACKED`: all three requirements below hold:
  1. at least two distinct evidence-bearing ProxyTrails;
  2. accepted citations span at least two independent publisher domains; and
  3. `strongest_alternative_explanation` remains explicit.

One cited proxy never reaches `EVIDENCE_BACKED`. Two pages from the same
publisher never establish independence. Two publisher domains attached to one
proxy do not replace the second causal trace. Evidence may support, contradict,
or leave the mechanism ambiguous; maturity measures research depth, not thesis
direction or truth.

Spark-level observation evidence is retained for audit but does not bypass the
two-ProxyTrail requirement.

## Citation integrity

Proxy citations use the same integrity rules and identities as the Crux engine:

- claim, source, date, and a concrete HTTP(S) page are mandatory;
- homepages, placeholder/test/local hosts, and hidden redirect wrappers are
  rejected;
- search and grounding wrapper URLs must resolve to the final publisher before
  submission;
- evidence identity is derived from normalized URL, claim, and number; and
- publisher independence is derived from the final URL domain, never from the
  agent-written source label.

The ledger freezes the frame's `as_of_date`. Day-precise evidence must be on
or before that date. A month-only date is treated as an interval ending on the
month's last day and is accepted only if that upper bound is on or before the
frozen date. This fail-closed rule applies to role ProxyTrails, spark
observation evidence, and scenario evidence. Authorized exploration documents
require exact `YYYY-MM-DD`.

Invalid evidence is dropped without deleting the trace. The hypothesis remains
`TRACED`, making the failed source attempt visible without turning a soft source
into a promotion route.

## Exploration priority and payoff threshold

`exploration_priority` ranks research queue order using deterministic
information-gap, testability, declared non-consensus, and payoff-shape
components. Exact same-unit payoff magnitudes are preferred. When they are
unknown, an optional qualitative `asymmetry_case` can declare
`upside_shape`, `convexity`, `downside_shape`, `time_to_signal`, and a visible
basis. The queue subtracts downside friction and uses the result only to
allocate research attention. A substantive cross-role conflict is contested
and contributes zero. None of these fields is evidence, a calibrated
probability, expected return, recommendation, trade instruction, or sizing
input.

“Asymmetric evidence” means **discriminating evidence**, not evidence selected because it is bullish.
The cheapest test should state two incompatible or materially different expected observations: one
under the variant mechanism and one under consensus or the strongest alternative explanation.
Evidence that both mechanisms predict is background context. It may mature a ProxyTrail when it is
a real observation, but it does not deserve directional crux credit merely because the page is new.
The formal Judge and evidence-exhaustion engine enforce that distinction separately from this
exploration queue.

When comparable upside and downside magnitudes are explicitly supplied,
`break_even_threshold` computes:

`p* = downside / (upside + downside)`

Missing, invalid, non-finite, negative, or jointly zero inputs return
`UNKNOWN`. The engine never invents payoff magnitudes and never estimates the
probability that belongs on either side of `p*`.

`exploration_action` returns one bounded research-only next action. It exposes
both `action_code` and its compatibility alias `action_type`, requires explicit
human authorization for an actionable probe, and caps the action at one bounded
query, three document reads, one new ProxyTrail, and one new publisher domain with no automatic
follow-on. It may ask for an alternative explanation, a second causal trace, an
independent publisher, or disconfirming replication. It cannot promote or
execute anything.

Every actionable proposal is `PROPOSED_NOT_AUTHORIZED`, has a null execution
receipt, and states one question, source class, bounded query, success condition,
and stop condition. The orchestrator does not place that proposal into automatic
round prompts. Roles may only record clues encountered while executing their
already-authorized formal crux/Landscape work; a dedicated exploration search
requires a new explicit user authorization and run receipt.
If any route field is absent, the action is `NEEDS_ACTION_DESIGN`, is not
authorization-ready, and cannot execute. A complete Framer proxy plan may produce
`COLLECT_FIRST_PROXY_EVIDENCE`; an unplanned clue first produces
`DESIGN_PROXY_TRAIL`.

The optional host adapter is deliberately four-phase:

1. typed design, when needed, binds `design_target_id`, exact
   `expected_state_revision`, hypothesis, action code, and either an
   alternative/discriminator or exactly two distinct SUPPORTS/CONTRADICTS
   proxy routes for `DESIGN_PROXY_TRAIL`;
2. planning freezes one `EA-...` attempt and writes no authorization;
3. authorization accepts only a user receipt bound to that exact ID and emits
   one bounded dispatch;
4. result submission verifies the route, origin crux, query, source class,
   causal link, stop condition, one search, at most three documents, no
   follow-on, and exact read-receipt evidence binding.

Two-sided design payloads use `proxy_plan`, not `routes`. Each route carries
`direction`, `proxy`, `causal_link`, `publisher_class`, `bounded_query`,
`stop_condition`, and—when the hypothesis spans multiple cruxes—an explicit
valid `origin_crux`. The two routes must differ in both execution diagnostic
and causal-maturity identity. A contested alternative may be resolved only by
choosing a preserved variant with `resolve_contested=true` and a rationale.
Other route-design action codes accept exactly one route; a
`SEEK_DISCONFIRMING_PROXY` route must be `CONTRADICTS`.

Planning is idempotent while an exact action is open. An unapproved
`PLANNED_NOT_AUTHORIZED` attempt may be closed only with
`--cancel-exploration-action --reason ...`; an authorized attempt cannot use
that command. Authorization is labelled
`CALLER_ATTESTED_NOT_HOST_VERIFIED`: the caller receipt is procedural evidence,
not cryptographic proof of a host UI event.

The submit path may append one ProxyTrail or a terminal
exhausted/falsified receipt. Its formal digest includes frame/as-of, question,
logic, Landscape/scenario state, cruxes, rounds, decisions, seeds, screens,
snapshots, and claim verification; a second digest binds the full hypothesis
ledger. A change after planning prevents authorization. A change after
authorization closes the attempt as `STALE_RESULT_NOT_RECORDED`, stores only
the submitted result SHA-256, ingests no evidence, and forbids automatic retry.
Cancellation or stale closure permits a fresh attempt ID.

If dispatch fails before any query, submit
`EXECUTION_FAILED_NO_SEARCH` with `query_executed=null`, `search_count=0`,
empty documents and proxy, a failure reason, and
`automatic_follow_on=false`. It releases the action but neither closes the
route nor creates negative market knowledge. `EXHAUSTED` means the bounded
query actually ran but produced no admissible document.
If the query began but the runtime failed before a usable observation, submit
`EXECUTION_FAILED_DURING_QUERY` with the exact query, `search_count=1`, zero to
three concrete documents already read, no proxy, and a failure reason. It is
also non-evidentiary, closes no route, and never auto-retries.

## Report projection

`report_view(state, limit=5)` is the compact reporting surface. It returns:

- `summary`;
- the current `exploration_action`; and
- `research_allocation`, a ranked research-attention comparison that preserves qualitative
  upside/downside shape, signal timing, cheapest test, bounded validation cost, and stop condition;
  it has no investment-ranking or sizing semantics; and
- priority-ranked hypotheses with ID, state, hypothesis, context, causal chain,
  non-consensus rationale, value transfer, falsifier, catalyst, payoff,
  break-even threshold, priority, and compact ProxyTrail summaries.

Hypotheses expose canonical fields plus compatibility aliases:
`hypothesis_id/id`, `break_even_threshold/break_even`, and
`exploration_priority/priority`. Proxy summaries likewise expose
`proxy_id/id` and `causal_link/why_diagnostic`.
Each ProxyTrail preserves `origin_crux/origin_cruxes`; repeated observation of
the same diagnostic trail across cruxes merges provenance and does not count as
a second causal trace.
The projection also retains direction variants and their
direction/evidence/source-agent/round/crux/action bindings.

The projection labels each top-level observation as `CITED_OBSERVATION` only
when at least one normalized citation still passes the shared evidence gate;
otherwise it is `UNVERIFIED_CLUE`. Spark-level observation evidence remains
separate from ProxyTrail maturity and cannot create `TRACED` or
`EVIDENCE_BACKED`.

Proxy summaries include the diagnostic link, direction, bounded route, evidence
count, publisher domains, and only normalized citations that still pass the
shared Crux citation gate. They omit raw role payloads and rejected evidence.
The projection contains no candidate-promotion, trade, execution, or
position-sizing instruction.

## Capability boundary

The exploration engine must never:

1. relabel a hypothesis as an `OpportunitySeed`;
2. count exploration evidence toward CandidateScreen eligibility;
3. infer economic exposure, pricing, catalyst dates, or instrument identity
   that a role did not supply;
4. write a Thesis, Decision, Paper Position, order, or position size; or
5. weaken any citation, source-diversity, snapshot, or human approval gate.

When a hypothesis is worth pursuing, the legal next step is more bounded
research or a separately authored object that passes the existing admission
protocol from zero.
