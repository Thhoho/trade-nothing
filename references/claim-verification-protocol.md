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

Snapshot content must come from the host fetcher or evidence_snapshot.py, not
from the Claim Verifier. Run the verifier in a context isolated from Candidate
Analyst and Candidate Skeptic.

## Snapshot schema

~~~json
{
  "snapshots": [
    {
      "snapshot_id": "SS-...",
      "status": "OK",
      "source_url": "https://example.com/specific-page",
      "final_url": "https://example.com/specific-page",
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

This state means source-content alignment, not objective truth. A source can be
wrong, stale in substance, or misleading despite an exact supporting sentence.
