# Path-Led Research v0.12 — The Tracking Track (赔率轨)

## Objective

Trade Nothing must answer two independent questions per research path:

1. **Evidence question** (existing, fail-closed): is the evidence complete enough to
   promote the candidate through the formal gates?
2. **Odds question** (new, fail-open for tracking): even without complete evidence,
   is the payoff structure good enough that this path deserves continued tracking?

The two tracks run in parallel. The evidence track keeps protecting the human from
bad bets; the tracking track keeps protecting the human from missed opportunities.
This is the mechanism for the user's original intent: asymmetric play on limited
evidence toward a relatively certain high-odds path.

## Design invariants

- Tracking NEVER changes the evidence verdict, convergence, screening, promotion, or
  validator contracts. It is a research state, not a recommendation, probability,
  expected-return, or sizing input.
- A tracked candidate is explicitly NOT promotable. Escalation back into the formal
  track requires the existing evidence gates to pass unchanged.
- All tracking decisions are deterministic functions of state; no LLM authority.

## Tracking admission (deterministic)

A seed blocked by the formal gates (candidate_state != READY_FOR_SCREENING and
promotion_eligibility != ELIGIBLE) enters the tracking ledger when ALL hold:

1. **Odds substantive**: `odds_summary(seed)` is not None (qualitative asymmetry
   declared: upside shape / convexity / downside shape / time-to-signal).
2. **Chain complete**: inherited or explicit causal chain with >= 3 nodes.
3. **Checkpoints present**: non-empty catalyst AND falsifier (upgrade / abandon
   events are named).

## Tracking ledger (state)

```
tracking_ledger: {
  "<seed_id>": {
    "entered_round": int,
    "entered_decision_question": str,
    "status": "ACTIVE" | "ESCALATED" | "CLOSED",
    "close_reason": str | null,
    "failure_signal": str | null,        # from Inquisitor odds calibration
    "tracking_until": "YYYY-MM-DD" | null  # horizon-anchored expiry for review
  }
}
```

## Exit rules

- **ESCALATED**: seed reaches READY_FOR_SCREENING (or better) through the normal
  evidence path — the formal track takes it back.
- **CLOSED**: an abandonment signal is recorded (falsifier event observed in a later
  round, or the candidate is REJECTED), with close_reason.
- **Re-review on expiry**: `tracking_until` passes without escalation — the human or
  a later authorized run re-assesses whether the checkpoints still justify tracking.

## Inquisitor odds calibration (Phase 2)

Per seed, the Inquisitor declares:

- `success_enablers`: what must be true for the declared upside to arrive;
- `primary_failure_mode`: the single most likely way the path fails;
- `failure_signal`: the earliest observable, monitorable sign of that failure mode.

This converts destructive energy into monitorable signals. Calibration never affects
judge signals, crux support, or convergence.

## Report rendering (Phase 3)

A new "跟踪清单" (Tracking List) section above candidate cards, one row per tracked
candidate: candidate | odds posture | upgrade checkpoint | abandon checkpoint |
tracking expiry. Visually separated from formal candidates: tracking is not a
recommendation.

## Calibration loop (Phase 4, scaffold only)

The ledger timestamps every admission, escalation, and close. A later `-calibrate`
extension can audit checkpoint hit-rates from this dataset (upgrade events observed?
abandon events observed?) — the long-open judge-signal calibration loop gains a
natural data source without any new live machinery.

## Acceptance boundaries

- Historical states and reports are not rewritten; the ledger only populates on new
  harvest/admission paths.
- No automatic promotion, order, position, or sizing.
- The evidence track's fail-closed gates remain byte-for-byte unchanged.
