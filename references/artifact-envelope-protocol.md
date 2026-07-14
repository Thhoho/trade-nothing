# Artifact Envelope Protocol

Use `trade-nothing.artifact-envelope.v1` whenever an external agent, MCP call, crawler, financial
adapter, or report stage produces content that is not needed verbatim for the parent's next branch.
The artifact remains on disk; the parent receives only a bounded, content-addressed descriptor.

## Contract

```json
{
  "schema": "trade-nothing.artifact-envelope.v1",
  "status": "READY",
  "artifact_kind": "stage-result",
  "producer": "trade-nothing",
  "artifact_path": "/scratch/.../result.json",
  "artifact_sha256": "...",
  "byte_size": 1234,
  "media_type": "application/json",
  "as_of": "2026-07-14",
  "summary": {"control": {"status": "ready_for_report"}},
  "warnings": [],
  "next_action": "consume the persisted report path",
  "usage": {},
  "read_policy": {
    "parent_context": "ENVELOPE_ONLY",
    "full_read_requires_explicit_verification": true,
    "prefer_exact_span": true
  }
}
```

The descriptor may not contain raw payloads, stdout/stderr, transcripts, report Markdown, or a
synthesis packet. Summary data is bounded and must be sufficient only for routing, not for silently
reconstructing the artifact.

## Read policy

1. Branch on the stage envelope's top-level status and compact result.
2. Prefer a final report path or exact span over the generic JSON stage result.
3. Read the full result only when a concrete conflict or audit question cannot be resolved from the
   descriptor. Call `artifact_envelope.load_json(..., explicit=True)`; it verifies size and SHA-256
   before parsing.
4. Never read an artifact merely to restate it in the parent context. Return its path and compact
   decision summary to the user.
5. A missing or hash-mismatched artifact fails closed. Do not refetch and pretend it is the same
   artifact.

## Registered deepthink2 runs

`run_registry.stage_envelope()` automatically persists the complete stage result under the run's
`artifacts/` directory. Formal reports and resolution memos are also materialized as Markdown.
The public `result` contains only control fields, while `artifacts.result` binds the exact full JSON.
This changes the stage envelope from “bounded in typical cases” to “raw bodies excluded by
construction.”

Checkpoints may retain structured role JSON for deterministic resume and Judge input. They are
internal state, not parent-context output; consumers must not read checkpoint payloads as a shortcut
around the envelope policy.
