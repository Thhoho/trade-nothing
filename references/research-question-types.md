# Research Question Types and Verdict Semantics

Read this reference when framing a `-deepthink2` question that may contain alternatives,
causal branches, comparisons, or a candidate universe.

## Question types

| Type | Meaning | Global rejection rule |
|---|---|---|
| `CONJUNCTIVE` | Every thesis hinge is necessary | One contradicted necessary hinge may reject the thesis |
| `DISJUNCTIVE` | Two or more paths can independently work | Reject only when every path and the pricing gap are rejected |
| `CAUSAL_CHAIN` | Value depends on an ordered transmission chain | A broken necessary link may reject the chain, but record where value transfers |
| `COMPARATIVE` | The decision is relative among candidates | Require meaningful separation; do not emit a pseudo-global verdict |
| `UNIVERSE_SEARCH` | The task is to find candidates in a broad opportunity set | A failed path never rejects the universe; require path and pricing coverage |

## Crux roles

- `THESIS_HINGE`: a necessary condition in a conjunctive thesis or causal chain.
- `OPPORTUNITY_PATH`: one independent route through which value may accrue.
- `PRICING`: the market-expectation, valuation, crowding, or mispricing check.
- `COMPARISON_AXIS`: one dimension used to separate candidates.

For a researchable `UNIVERSE_SEARCH`, include at least one `OPPORTUNITY_PATH` and one `PRICING`
crux. For `DISJUNCTIVE`, include at least two opportunity paths. For `COMPARATIVE`, include at
least two comparison axes.

## Logic graph

The graph must contain a `QUESTION` root and one `CRUX` node for every candidate crux. Every crux
must have a directed path to the root. Use only these relations:

- `REQUIRED_FOR`
- `ALTERNATIVE_PATH`
- `CAUSAL_PRECEDES`
- `COMPARED_ON`
- `PRICING_FOR`

The graph is a decision contract, not decoration. Do not infer a missing relationship from prose.

## Three-axis verdict

```json
{
  "edge_state": "EDGE_FOUND | NO_EDGE | INSUFFICIENT_EVIDENCE",
  "evidence_direction": "BULL | BEAR | MIXED | UNDETERMINED",
  "actionability": "NONE | MONITOR | READY_FOR_SCREENING"
}
```

- `NO_EDGE` means the run did not establish an exploitable expectation gap. It is not `AVOID`.
- `BEAR` describes evidence direction. It is not a short trade.
- `READY_FOR_SCREENING` requires workflow convergence; an apparent early edge remains `MONITOR`.
- A short may appear only as a separately evidenced `SHORT_CANDIDATE` that passes CandidateScreen.
