# Runtime Compatibility and Installation

This matrix distinguishes an implemented adapter from a manual protocol mapping. A copied
`SKILL.md` is not proof that a framework can enforce isolation, produce a valid receipt, or resume
a run.

## Capability matrix (audited 2026-08-05)

| Runtime | Core Detective/Inquisitor/Judge | CandidateScreen | Claim Verifier | Assurance |
|---|---|---|---|---|
| Antigravity (`agy`) | `deepthink_host_runner.py --runtime antigravity` | two process-bound roles through `agy_candidate_screen_runner.py` | `claim_verifier_runner.py --runtime antigravity` | Implemented and offline contract-tested; live model access remains environment-dependent. |
| Claude Code | `deepthink_host_runner.py --runtime claude-code` | two process-bound roles through `agy_candidate_screen_runner.py --runtime claude-code` | `claim_verifier_runner.py --runtime claude-code` | Implemented and offline contract-tested; CLI structured-output flags were locally verified, but this release audit did not spend a live model call. |
| Codex | Manual collaboration-agent dispatch under the runtime protocol | `codex_candidate_screen_receipt.py` binds two completed canonical agent IDs | `codex_claim_verifier_receipt.py` binds one completed canonical agent ID | Skill loading and receipt contracts are supported; there is no Codex CLI process host runner in this release. |
| Gemini CLI | Manual isolated context/process mapping only | Manual submission remains `unverified` without a supported receipt profile | Manual submission remains `unverified` without a supported receipt profile | Install layout only; no verified isolation adapter in this release. |
| Hermes / OpenHands | Protocol mapping only | Protocol mapping only | Protocol mapping only | Documentation-only and not locally validated for this release. |
| Single-model role switch | Prompt role switch | Prompt role switch | Prompt role switch | Always `degraded`; cannot satisfy a verified-isolation promotion gate. |

Do not upgrade a manual or documentation-only row to “supported” until a deterministic offline
contract test covers command construction, bounded timeout, output parsing, receipt validation,
and failure behavior. A live smoke test is a separate environment check and must not consume user
budget without authorization.

## Install and upgrade

Run from the canonical source repository:

```bash
make install DEV_DIR="$(pwd)"
make status DEV_DIR="$(pwd)"
```

The installer copies the controlled bundle to Gemini, Codex, and Claude skill roots. Paths with
spaces are accepted. Old files on the managed code surface that no longer exist in source are
moved to a recoverable quarantine under `~/.trade-nothing/install-quarantine`; they are not
silently retained as executable code. Runtime JSON, `.state`, scratch data, `.git`, and personal
memory are never deleted.

`make status` requires every controlled file to match and rejects extra managed code. It may report
legacy `.state`, `.git`, or `Methodology_Evolution.md` as preserved, inert extras. Runtime code
does not auto-load skill-local legacy state or memory. Adopt an old state explicitly by exact path;
set `TRADE_NOTHING_EVOLUTION_PATH` explicitly when personal memory lives outside the default vault.

An installed package contains `.trade-nothing-install-manifest.json`. Its benchmark self-check
validates package files and reports `source_variant_verification=NOT_AVAILABLE_IN_INSTALLED_PACKAGE`;
only the canonical Git source checkout can perform pinned Git-object verification.
