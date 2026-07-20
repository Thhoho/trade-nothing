# Framing Feasibility Protocol

Use this protocol before `--init` accepts a researchable frame. It prevents the round fuse and
source budget from being structurally incapable of satisfying the later evidence gate. It does not
predict that research will find evidence.

## Per-crux evidence plan

Every initial researchable crux freezes 2–3 routes. Each route contains:

- a unique `plan_id`;
- one allowed `publisher_class`;
- the exact claim or number to support or refute;
- one bounded search query.

At least two publisher classes and two distinct queries are required. Allowed classes are:

- `ISSUER_OR_FILING`
- `CUSTOMER_OR_COUNTERPARTY`
- `REGULATOR_OR_OFFICIAL_DATASET`
- `EXCHANGE_OR_MARKET_DATA`
- `PROJECT_OWNER`
- `CREDITOR_OR_FINANCING_COUNTERPARTY`
- `INDEPENDENT_INDUSTRY_SOURCE`

The plan is not evidence. A planned publisher may have no useful page, and a returned citation must
still pass the normal concrete-URL, date, duplication, and Judge gates.

## Round feasibility

The engine simulates the deterministic scheduler using these capacities:

- at most two cruxes per round;
- at most two Landscape paths per role per round;
- pending Landscape-linked cruxes receive dispatch priority;
- every initial crux must receive at least one dispatch slot;
- opportunity frames reserve two harvest-dry rounds after the final required active round.

If `suggested_max_rounds` is below the computed minimum, init returns:

```text
framing_feasibility_requires_at_least_N_rounds
```

The Framer must then increase the bounded fuse or reduce/restructure the crux and Landscape map. The
caller must not bypass the issue, silently extend a run after fuse-break, or treat the minimum as a
promise of convergence.

## Runtime dispatch

Landscape assignment prefers paths whose `linked_crux_id` is already in the current deterministic
crux dispatch. Research prompts include the frozen evidence routes and instruct both roles to test
different publisher classes before rewriting queries within one publisher. This reduces budget
contention; it does not relax any citation or convergence gate.
