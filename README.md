# Trade Nothing

Trade Nothing is an adversarial investment-research skill. It organizes evidence around
load-bearing cruxes, sends a bull-side Detective and a bear-side Inquisitor to test them,
and uses a deterministic evidence gate to decide whether a formal report is allowed.

It is a research workflow, not a trading system. It does not produce an automatic buy/sell
instruction, target price, expected return, Kelly allocation, or position size.

## What is trustworthy

- A Judge signal cannot move a crux without a concrete citation containing claim, source,
  date, and a specific article/filing/API URL.
- Judge citations must match evidence already present in the isolated agent payloads.
- Repeated evidence (same URL + claim + number) cannot be scored twice.
- Every crux needs at least two distinct concrete sources before it can retire.
- `continue` and `fuse_break` both block formal reporting.
- Reported values are **debate-support scores**, not calibrated market probabilities.
- Runtime state is stored under `TRADE_NOTHING_SCRATCH_DIR`, not inside the skill source.
- OS reminders and webhooks are disabled unless `--notify` or `--webhook` is passed.

## Isolation is a host responsibility

The skill cannot physically isolate agents by itself. A capable host should run Detective and
Inquisitor in separate contexts with no shared intermediate reasoning. If the host uses one
model with role switching, the report must label the run `degraded`; it must not claim physical
or multi-agent isolation.

## Recommended workflow: `-deepthink2`

Read [SKILL.md](SKILL.md) before running the workflow.

```bash
# 1. Frame a falsifiable research question and 2-5 cruxes.
python3 scripts/deepthink_orchestrator_v2.py --frame --topic "TARGET"

# 2. Run agents/framer.md in the host, then initialize.
python3 scripts/deepthink_orchestrator_v2.py --init \
  --topic "TARGET" --frame-json '<framer_json>'

# 3. Run agents/detective.md and agents/inquisitor.md in isolated contexts,
#    run agents/judge.md on their JSON, then submit each round.
python3 scripts/deepthink_orchestrator_v2.py --submit \
  --topic "TARGET" --det '<detective_json>' \
  --inq '<inquisitor_json>' --judge '<judge_json>'

# 4. This succeeds only after convergence and the evidence gate pass.
python3 scripts/deepthink_orchestrator_v2.py --report --topic "TARGET"
```

Possible workflow statuses:

- `dispatch_subagents`: continue only on OPEN cruxes.
- `ready_for_report`: the deterministic convergence and evidence gates passed.
- `blocked_max_rounds`: the fuse fired; no formal report.
- `blocked_unconverged`: unresolved cruxes remain; no formal report.
- `blocked_evidence_gate`: source diversity is insufficient; no formal report.
- `no_edge`: framing found no researchable asymmetric angle; stop early.

The older `-deepthink` single-posterior/LFI pipeline remains for compatibility. Its outputs are
uncalibrated legacy heuristics and must not be presented as real probabilities.

## Evidence schema

The v2 Detective writes per-crux evidence in `crux_evidence`; the Inquisitor writes per-crux
attacks in `crux_attacks`. Citation objects use:

```json
{
  "claim": "what the source establishes",
  "number": "value or null",
  "source": "organization",
  "url": "https://example.com/specific-page",
  "date": "YYYY-MM-DD",
  "source_tier": "primary"
}
```

Bare domains, missing dates, missing sources, and invented Judge citations are rejected.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `TRADE_NOTHING_SKILL_DIR` | auto-detected | Skill installation root |
| `TRADE_NOTHING_SCRATCH_DIR` | `~/.trade-nothing/scratch` | State and issue files |
| `TRADE_NOTHING_OUTPUT_DIR` | `~/trade-nothing-outputs` | Generated artifacts |
| `TRADE_NOTHING_VAULT_DIR` | `~/trade-nothing-vault` | Research vault |
| `TRADE_NOTHING_EVOLUTION_PATH` | `<skill>/Methodology_Evolution.md` | Negative-prior memory |
| `TRADE_NOTHING_MODEL_DEEP` | host default | Quality-critical agents and Judge |

## Maintenance

`~/Documents/trade-nothing` is the single source of truth in the default local setup.

```bash
# Deterministic offline safety gates
make test

# Legacy compatibility tests
make test-legacy

# Non-gating live provider diagnostics
make test-live

# Sync controlled source files to Codex and Gemini installations
make install

# Verify hashes without changing files
make status
```

`make install` does not copy or delete runtime JSON, state, scratch data, or personal research
artifacts.

## License

MIT. See [LICENSE](LICENSE).
