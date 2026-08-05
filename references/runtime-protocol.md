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
   role, but must leave the failed role missing. Process adapters start a new session and terminate
   the entire process group on timeout so CLI/tool descendants cannot survive the parent.
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

## Host runner selection

The resumable runner supports `--runtime antigravity` and `--runtime claude-code`. Auto-detection
is conservative and preserves Antigravity compatibility when both CLIs are installed, so a Claude
Code parent should pass `--runtime claude-code` explicitly. The Claude adapter uses separate CLI
processes and structured JSON output; it does not use Claude Code's parent-session `Task` tool and
does not parse terminal prose. It removes only the parent-session guard markers from each bounded
child process so Claude's CLI does not mistake the isolated role for an interactive nested session;
authentication and unrelated environment settings remain inherited. A runtime change may complete a payload-free failed checkpoint, but
it may not combine a changed prompt with a previously successful payload.

The default CLI limits match the table: Detective/Inquisitor use `--timeout-seconds 480`, Judge is
capped by `--judge-timeout-seconds 240`, and CandidateScreen/Claim Verifier use 480 seconds. When a
loop stops because it converged, reached the maximum, used its round budget, or paused before a
CandidateScreen, the host runner calls `--report` and returns a content-addressed graded report.
A runtime-process failure remains a failure envelope and never fabricates a report-stage payload.

CandidateScreen and Claim Verifier process adapters support both Antigravity and Claude Code.
Codex uses explicit collaboration-agent receipt builders. Gemini, Hermes, and OpenHands are manual
protocol mappings in this release; see `references/runtime-compatibility.md` before claiming support.
