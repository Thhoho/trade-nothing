# Runtime Dispatch and Failure Protocol

This protocol separates stages that need adversarial isolation from stages that do not. The host,
not the Python orchestrator, enforces context isolation and wall-clock limits.

| Stage | Dispatch | Isolation | Default wall-clock limit | On timeout |
|---|---|---:|---:|---|
| Framer | Inline parent context | No | 120 seconds | Emit `--runtime-failure`; do not retry |
| Detective | Delegated agent | Yes | 8 minutes | Emit `--runtime-failure`; do not fabricate JSON |
| Inquisitor | Delegated agent | Yes | 8 minutes | Emit `--runtime-failure`; do not fabricate JSON |
| Judge | Independent context where supported | Preferred | 4 minutes | Emit `--runtime-failure`; do not score |
| Candidate Analyst / Skeptic | Two isolated agents | Yes | 8 minutes each | Emit `--runtime-failure`; do not screen |
| Claim Verifier | Independent agent | Yes | 8 minutes | Emit `--runtime-failure`; do not verify |

## Framer rule

The parent must read `agents/framer.md`, generate the strict JSON itself, and immediately call
`--init`. For Antigravity/`agy`, do **not** call `define_subagent` or `invoke_subagent`. For other
runtimes, do not use `Task`, delegation, a context fork, or an equivalent mechanism. Framer does
not browse: every factual seed remains `HYPOTHESIS` or `URL_CLAIMED_UNVERIFIED` for later research.

## Timeout rule

1. Apply a stage-local wall-clock limit; a global CLI timeout is not a substitute.
2. At the first timeout, stop waiting. Do not automatically retry, because a retry silently doubles
   cost and may duplicate evidence. The resumable host runner may checkpoint the successful peer
   role, but must leave the failed role missing.
3. Record a compact receipt:

```bash
python3 scripts/deepthink_orchestrator_v2.py --runtime-failure \
  --topic "TARGET" --stage "STAGE" --reason "BRIEF SANITIZED REASON"
```

4. The receipt is not a research report. It must not contain transcripts, hidden reasoning, search
logs, or invented stand-ins for missing agent JSON.
5. If state already exists, preserve it unchanged. Resume only after the user explicitly authorizes
   more runtime and research budget. For a registered run, call
   `deepthink_host_runner.py resume --run-id RUN-...`; it must validate prompt/payload hashes and
   rerun only the missing role. Do not reconstruct the role output from transcript text.
