# Run Identity and Resume Protocol

Use this protocol for Antigravity deepthink2 runs and for adopting older state files after a host
failure. The deterministic research state remains authoritative; the registry only adds immutable
identity, stage checkpoints, and bounded continuation.

## Invariants

1. Create one `RUN-YYYYMMDD-...` id before initialization, or adopt one exact existing state path.
2. After registration, address every stage by `run_id`; do not reconstruct topic strings.
3. Keep state under `TRADE_NOTHING_SCRATCH_DIR`. A manifest may not point outside that root.
4. Store structured role JSON, prompt hash, payload hash, process id, invocation id, exit status,
   timeout state, and sanitized error code. Never persist transcript or stdout/stderr tails.
5. Mark a round `submitted=true` only after the deterministic orchestrator saves it.
6. A resumed round reuses a successful hash-matching role and runs only missing or invalid roles.
7. Prompt-hash drift requires manual review whenever any successful payload exists; never combine a
   saved payload with a changed prompt. A checkpoint containing only failed, payload-free attempts
   may be superseded while preserving the old prompt hashes for audit.
8. No automatic retry. `resume` is an explicit new budget authorization.

## Stage envelope

Every registered CLI result uses `trade-nothing.stage-envelope.v1`:

```json
{
  "schema": "trade-nothing.stage-envelope.v1",
  "run_id": "RUN-...",
  "topic": "...",
  "stage": "debate",
  "status": "paused_runtime_failure",
  "next_action": "...",
  "blockers": ["inquisitor", "resource_exhausted_429"],
  "artifact_paths": {"state_path": "..."},
  "budget": {"round_budget": 1, "rounds_used": 0},
  "result": {}
}
```

Consumers should branch on top-level `status` and treat `result` as stage-specific detail. A
failure envelope is not a report and cannot authorize CandidateScreen, claim verification, thesis
creation, or a trade.

## Commands

```bash
# New run after inline Framer output
python3 scripts/deepthink_host_runner.py start --topic "TARGET" \
  --frame-json '<json>' --round-budget 1

# Existing legacy state
python3 scripts/deepthink_host_runner.py adopt --state-path "/.../v2_state.json"

# Inspect and resume
python3 scripts/deepthink_host_runner.py status --run-id "RUN-..."
python3 scripts/deepthink_host_runner.py resume --run-id "RUN-..." --round-budget 1
```

`--allow-agent-tools` passes Antigravity's non-interactive permission bypass and therefore requires
explicit authorization. Role working directories live under the run scratch directory, not inside
the skill source tree.
