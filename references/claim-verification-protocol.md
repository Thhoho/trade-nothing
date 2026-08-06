# Snapshot-Bound Claim Verification

This protocol verifies that decisive CandidateScreen claims are anchored to
retrieved page content. It narrows the gap between a plausible citation and a
source-supported claim; it still does not prove that the source itself is true.

## Trust boundary

- evidence_snapshot.py retrieves or imports a page/PDF, extracts normalized
  text, and computes immutable raw/text hashes.
- Claim Verifier receives the citation claim plus a deterministic excerpt from
  that snapshot. It returns SUPPORTS, CONTRADICTS, or INSUFFICIENT.
- claim_verification_engine.py accepts a decisive verdict only when the short
  exact quote occurs verbatim in the hashed snapshot.
- The engine stores the snapshot manifest and short quote, not the full page.

Each `(claim_id, snapshot_id)` accepts at most one verifier submission. An exact replay is
idempotent. A different payload for the same claim and snapshot is a conflict and must leave the
stored verification unchanged. A new assessment requires a genuinely new content-hashed snapshot;
deleting or rewriting the old result is forbidden.

Snapshot content must come from the host fetcher or evidence_snapshot.py, not
from the Claim Verifier. Run the verifier in a context isolated from Candidate
Analyst and Candidate Skeptic.

## Isolation receipt

A `--verifier-isolation verified` string is only caller attestation and cannot unlock a decisive
verdict. SUPPORTS and CONTRADICTS become effective only with a validated
`claim-verifier-isolation.v1` receipt binding the stored dispatch, exact verifier prompt, exact
submitted payload, claim IDs, and snapshot IDs. Missing, mismatched, or invented receipts reduce
the effective verdict to INSUFFICIENT.

- Antigravity and Claude Code: run `scripts/claim_verifier_runner.py --runtime ...`; it launches one
  bounded, non-persistent process and submits the process receipt.
- Codex collaboration: after one independent agent context completes, use
  `scripts/codex_claim_verifier_receipt.py` with the host-returned canonical agent ID. The helper
  binds host facts supplied by the caller; it does not launch an agent or prove a UI event.
- Other/manual runtimes remain `unverified` until they implement and test a supported receipt
  profile.

```bash
python3 scripts/claim_verifier_runner.py --topic "TARGET" \
  --snapshots snapshots.json --runtime claude-code

python3 scripts/deepthink_orchestrator_v2.py --submit-verification \
  --topic "TARGET" --snapshots snapshots.json --verifier verifier.json \
  --verifier-isolation verified \
  --verifier-isolation-receipt claim-verifier-receipt.json
```

## Snapshot schema

~~~json
{
  "snapshots": [
    {
      "snapshot_id": "SS-...",
      "status": "OK",
      "source_url": "https://issuer.example.invalid/specific-page",
      "final_url": "https://issuer.example.invalid/specific-page",
      "retrieved_at": "YYYY-MM-DDTHH:MM:SSZ",
      "http_status": 200,
      "content_type": "text/html",
      "title": "<page title>",
      "raw_sha256": "<sha256>",
      "text_sha256": "<sha256>",
      "text_length": 12345,
      "text": "<normalized extracted page text>"
    }
  ]
}
~~~

The `.invalid` values above are schema placeholders and are never admissible evidence.
The engine recomputes text_sha256 and snapshot_id. A mismatch rejects the
snapshot. Source and final URLs must be concrete public HTTP(S) URLs.

## Claim Verifier schema

~~~json
{
  "claim_verifications": [
    {
      "claim_id": "CL-...",
      "snapshot_id": "SS-...",
      "verdict": "SUPPORTS|CONTRADICTS|INSUFFICIENT",
      "exact_quote": "<verbatim snapshot span, at most 160 characters and 30 words>",
      "locator": "<section, table, page, or paragraph hint>",
      "reason": "<why the exact span supports or contradicts the attached claim>"
    }
  ]
}
~~~

SUPPORTS and CONTRADICTS require an exact quote and reason. Use INSUFFICIENT
when the excerpt is ambiguous, the claim overstates the source, the relevant
table is missing, or the snapshot extraction is unusable.

## Candidate verification state

- PENDING: no decisive claim has a verified supporting span.
- PARTIALLY_VERIFIED: some required Analyst/Skeptic sides have support spans.
- VERIFIED: every SUPPORTED CandidateScreen dimension has at least one
  snapshot-bound SUPPORTS result for both Analyst and Skeptic evidence, with no
  contradiction.
- CONTRADICTED: any required evidence claim has a snapshot-bound contradiction.

A THESIS_CANDIDATE promotion packet remains DRAFT_REQUIRES_SOURCE_VERIFICATION
until VERIFIED. VERIFIED changes it to DRAFT_REQUIRES_HUMAN; CONTRADICTED changes
it to BLOCKED_CLAIM_CONFLICT.

Claim verification is a candidate-promotion gate only. The absence of snapshots or verification
records cannot lower `report_grade`, and a `PENDING`, `PARTIALLY_VERIFIED`, or `CONTRADICTED`
candidate does not invalidate an otherwise `FORMAL` root research report. Reports must expose that
candidate state without describing it as `VERIFIED_FOR_HUMAN`.

This state means source-content alignment, not objective truth. A source can be
wrong, stale in substance, or misleading despite an exact supporting sentence.
