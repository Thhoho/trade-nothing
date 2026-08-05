# Run Identity and Resume Protocol

Use this protocol for Antigravity or Claude Code deepthink2 runs and for adopting older state files
after a host failure. The deterministic research state remains authoritative; the registry only
adds immutable identity, stage checkpoints, and bounded continuation.

## Invariants

1. Create one `RUN-YYYYMMDD-...` id and select one explicit `run_purpose` before initialization,
   or adopt one exact existing state path without inventing a missing purpose.
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
9. Every non-runtime terminal stop materializes a report. Convergence, maximum rounds, round-budget
   exhaustion, candidate gaps, and stop-before-screen may change the grade or next action, but they
   do not erase the report artifact.
10. Method drift is fail-closed. `status` remains read-only and returns
    `paused_method_contract_drift` with pinned/current identities; `resume` returns the same
    structured state and cannot append to or rewrite the old run.

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
  "artifact_paths": {"state_path": "...", "result_path": "..."},
  "artifacts": {
    "result": {
      "schema": "trade-nothing.artifact-envelope.v1",
      "artifact_sha256": "...",
      "read_policy": {"parent_context": "ENVELOPE_ONLY"}
    }
  },
  "budget": {"round_budget": 1, "rounds_used": 0},
  "result": {"status": "paused_runtime_failure", "reason": "resource_exhausted_429"}
}
```

For a registered run, the complete stage result is content-addressed on disk and `result` contains
only routing/control fields. Read `references/artifact-envelope-protocol.md` before loading a full
result artifact. Consumers should branch on top-level `status`. A
failure envelope is not a report and cannot authorize CandidateScreen, claim verification, thesis
creation, or a trade.

## Commands

```bash
# New run after inline Framer output
python3 scripts/deepthink_host_runner.py start --topic "TARGET" \
  --frame-json '<json>' --run-purpose PRODUCTION_RESEARCH --round-budget 1

# Existing legacy state
python3 scripts/deepthink_host_runner.py adopt --state-path "/.../v2_state.json"

# Inspect and resume
python3 scripts/deepthink_host_runner.py status --run-id "RUN-..."
python3 scripts/deepthink_host_runner.py resume --run-id "RUN-..." --round-budget 1

# Claude Code: separate OS processes + --output-format json/--json-schema parsing
python3 scripts/deepthink_host_runner.py resume --run-id "RUN-..." \
  --runtime claude-code --round-budget 9 --stop-after-dry-rounds 3

# After convergence, continue an EVIDENCE_BACKED candidate without reopening root debate
python3 scripts/deepthink_orchestrator_v2.py --plan-candidate-gaps --run-id "RUN-..."
python3 scripts/deepthink_orchestrator_v2.py --submit-gap-evidence --run-id "RUN-..." \
  --task-id "CGT-..." --supplement '<json>'
```

Candidate-gap histories follow the same run identity and method identity. A method-drifted run may
not append a new task or supplement. Resume never retries a gap search automatically: every attempt
consumes the task's frozen search budget and must be an explicit host action.

`--allow-agent-tools` passes the selected host's non-interactive permission bypass and therefore
requires explicit authorization. Without it, the selected CLI's normal permission policy remains
authoritative. Role working directories live under the run scratch directory, not inside the skill
source tree. Claude Code results are accepted only from its JSON result envelope's
`structured_output` (or an exact-JSON `result` compatibility field); prose is not scraped into a
payload.

Legacy files under an installed `scripts/.state/` directory are never auto-loaded. Register an old
state only through `adopt --state-path` so the exact file and method identity remain visible.
