# Deep Research Report Contract

The default user artifact is a **Deep Research Report**. It explains what the topic needed answered,
what each round established or disputed, which blind spots emerged, how the market may trade the
result, which concrete instruments carry each path, and what would upgrade or kill the setup.
It is a research artifact, not a Thesis, Decision, order, position, portfolio record, publication
approval, or downstream handoff.

## 1. Product truth and audit truth

Keep two layers:

- **Research and opportunity layer**: question answers, challenges, blind spots, market mechanism,
  concrete securities, conditional recommendations, risks and next observations. This is the main
  user product.
- **Audit appendix**: citations, evidence labels, source counts, runtime limits, convergence and
  isolation receipts. This supports trust but must not dominate the first page.

Process completion is not opportunity quality. `FORMAL`, when retained by the compatibility
renderer, means only that its evidence workflow completed. It must never be presented as proof that
the opportunity search was broad, useful, actionable, or profitable.

## 2. Required report order

1. **Core judgment and conditional recommendations**;
2. **Research objective and Agenda progress**;
3. **Answered, partial, disputed and open questions** with strongest challenge and missing datum;
4. **Industry value transfer and market time structure** — constraint -> profit pool, plus phase by horizon;
5. **Economic-exposure × trading-carrier map** — company, ticker, closest alternative and evidence boundary;
6. **Conditional EVENT_SETUP and ECONOMIC_SETUP advice**;
7. **New blind spots and forward-looking implications**;
8. **Scenario tree and candidate risks** — trigger, invalidation, price and crowding;
9. **Open questions and cheapest next tests**;
10. **Evidence and method boundary**.

If concrete CandidateMap rendering is not yet available, the report must say so explicitly. It may
not replace the missing product surface with additional state-machine detail.

## 3. Claim labels

- `FACT`: the cited source directly establishes the statement;
- `SINGLE_SOURCE`: one real source, not independently corroborated;
- `INFERENCE`: reasoning based on cited facts; the source does not say it directly;
- `HYPOTHESIS`: an unverified mechanism worth testing.

Weak evidence is allowed with its label. Hypothesis laundering—removing the label and writing the
idea as fact—is forbidden. Numbers require concrete URL, publisher and date.

## 4. Candidate and setup language

The report may compare named securities and give explicit conditional research or market
recommendations before high-confidence verification. The wording must match the evidence boundary
and include the conditions under which the recommendation should be abandoned. It is not an order,
position, target return or automatic downstream action.

`SETUP_READY` is field completeness, not recommendation authority. A cross-sectional conditional
priority additionally needs:

- a question-linked `ValueTransferPath` with realization horizon and falsifier;
- grounded economic-exposure strength and a source-bound market snapshot;
- one explicit horizon: event days, tactical weeks, earnings quarters or structural years;
- the closest mapped alternative;
- why the candidate is preferred now and what would switch the preference;
- a non-counterexample role: `WATCH_ONLY` and `FAILURE_HEDGE` cannot become recommendations.

Every complete setup still needs:

- concrete candidate and ticker for listed securities;
- setup type (`EVENT_SETUP` or `ECONOMIC_SETUP`);
- causal mechanism;
- trigger and catalyst window;
- invalidation or kill condition;
- current price/position/crowding information or explicit `UNKNOWN`;
- strongest alternative explanation;
- evidence label and missing data.

A stock may rank highly for event beta while failing economic capture. The report must display the
disagreement instead of averaging it away.
Do not reuse one global stock order across different horizons. A long-term economic carrier may be
short-term crowded, while an event leader may have weak profit exposure.

## 5. Zero-setup reports

`NO_USABLE_SETUP` is acceptable and must not be converted into `AVOID` or `SHORT`. Before using it,
the brief must show that research covered:

- concrete securities or an explicit no-listed-vehicle result;
- direct, bottleneck, second-order, substitute and failure paths where relevant;
- current price, liquidity and crowding for plausible event carriers;
- the declared catalyst window;
- the strongest surviving hypothesis and the missing observation.

上述覆盖还必须显式显示经济链、市场载体、竞争/替代、失败/逆向和股权/资本关系五种候选
构造路径。`INSUFFICIENT` 不算完成覆盖。四个搜索字段全为 true 但缺少任一候选路径时，结果仍是
`EXPLORE`，不能写成 `NO_USABLE_SETUP`。

Bibliographic or process exhaustion alone cannot justify a zero-opportunity claim.

## 6. Research Agenda and blind spots

The report must preserve question states `OPEN`, `PARTIAL`, `ANSWERED`, and `DISPUTED`. It must not
hide an unresolved conflict by displaying only the last agent answer. Every answered question shows
its evidence boundary; every open or partial question shows the missing datum or success condition.

The progress header distinguishes fully answered questions from evidence-bounded partial or
disputed answers. The default body shows all initial questions plus only the most decision-relevant
derived questions, directions, blind spots and candidates. The exhaustive append-only history stays
in the explicit audit view; omission from the default body is counted and disclosed.

Within one round, role variants are reconciled symmetrically. Across rounds, the report displays the
latest temporal projection: an old `OPEN` does not remain a permanent dispute against a later
evidence-backed answer. Historical variants remain auditable. Candidate prose alternatives are not
Agenda disputes; a material contradiction must be recorded on the linked question or direction.
When a candidate field is refined or replaced, the current report may cite only evidence bound to
that current field value; evidence attached to a challenged variant remains audit-only.

Every unresolved next test displays `SEARCH_NOW`, `WAIT_FOR_DATE`, `WAIT_FOR_EVENT`,
`NEEDS_USER_DATA`, or `UNKNOWN`. Only an explicit low-cost, high-impact `SEARCH_NOW` test may justify
another research round; waiting and user-data dependencies remain visible without consuming budget.

同题重跑且提供旧报告时，正文必须显示既有关键发现处置表。旧结论不继承证据等级：每条必须
用本轮证据重新验证、推翻，或明确判为无关/未决。静默消失属于报告回归。

Blind spots belong in the main report when they could change the conclusion, timing, candidate map,
pricing/crowding judgment, or advice. Each blind spot names the cheapest discriminating test. A
blind spot can reprioritize research, but it cannot directly alter a crux signal or promote a
candidate.

## 7. Deterministic facts

Existing deterministic fields may remain in a compatibility Facts Box, but the narrative must not
rewrite them. Agenda-native source counts come only from the canonical `evidence_items` plane;
legacy crux counts must be separately labelled compatibility audit metrics and may never replace
the product count. Round counts, coverage, run status and engine labels come only from stored state.
The Deep Research Report may explain that those fields measure audit completeness, not product value.

Every Trade Nothing report carries one deterministic `TRADE_NOTHING_EXECUTION_INTEGRITY` marker.
Only a current registered state whose every stored round has a valid three-role prompt/payload/host
receipt may say that N research rounds completed or that roles were isolated. A state-only artifact
must say "unverified state updates"; method-identity drift must say `HISTORICAL_REPLAY`; an inline
fallback must say `INLINE_DEGRADED_RESEARCH` and must not use numbered-round or named-role theatre.
Never attach an inline report to a paused registered run or reuse that run ID.

Raw Detective, Inquisitor and Judge payloads stay out of the default report. Preserve them only for
explicit audit.

## 8. Boundary

The brief ends with research conclusions and next observations. It must not create, request or
imply:

- Thesis or Decision state;
- order, position or portfolio action;
- automatic retry, monitoring or notification;
- publication permission;
- cross-system promotion or handoff.

If legacy report data contains those fields, treat them as compatibility metadata and omit them
from the new default narrative.

## 9. Persistence and validation

When the user requests a saved artifact, persist the Deep Research Report and a separate Evidence
Ledger rendered from the same canonical evidence plane. The ledger enumerates every canonical ID,
binding, source/date, alias, and accepted host-market receipt; the legacy crux audit is not the
evidence ledger. Validate:

- every concrete security identity;
- citation URL/date/source completeness;
- FACT versus inference wording;
- presence of trigger and invalidation for ordered setups;
- presence of Research Agenda progress, disputes, new blind spots and next questions;
- alignment between recommendation strength and evidence boundary;
- value-path, market-phase, horizon and closest-alternative visibility for every conditional priority;
- absence of any recommendation derived from setup completeness alone;
- absence of downstream workflow objects;
- first-page visibility of market mechanics and concrete candidates;
- exact alignment of the execution-integrity marker with the supplied state and registered run;
- absence of numbered-round claims when complete execution receipts are unavailable.

Engineering validation never establishes opportunity recall, Alpha, return, or risk-adjusted
performance. Those require real-theme replay and human blind assessment.
