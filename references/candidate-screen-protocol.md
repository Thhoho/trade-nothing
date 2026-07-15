# CandidateScreen Protocol

CandidateScreen is a two-sided pre-screen for OpportunitySeed. It asks whether
a discovered lead is strong enough to become a new, independent research thesis.
It does not rank candidates, estimate returns, or authorize a trade.

The deterministic engine verifies citation structure, dates, freshness, and
source diversity. It cannot fetch a URL or prove that page content supports the
claim. The host and human reviewer must spot-check source fidelity before
promoting a draft.

## Runtime

1. Only screen a stateful `READY_FOR_SCREENING` path: seed evidence alone is insufficient;
   the origin crux must be healthy, the root thesis converged, and the structured catalyst must
   fall inside the root horizon. Default dispatch screens one representative path per exact entity.
2. Run Candidate Analyst and Candidate Skeptic in isolated contexts. For Antigravity, use
   `scripts/agy_candidate_screen_runner.py`; it launches two distinct OS processes concurrently.
   Codex hosts may use two distinct collaboration-agent contexts and emit a
   `codex_collaboration_v1` receipt containing the host-returned canonical agent IDs. After both
   payloads are sealed, use `scripts/codex_candidate_screen_receipt.py` to bind the dispatch,
   payloads, and those IDs; the helper does not launch agents or invent host events.
3. Give both the same seed packet, as-of date, and eight fixed questions.
4. Submit both JSON payloads to candidate_screen_engine.py.
5. Preserve disagreement. Do not ask an LLM Judge to average it away.

Use an agent-local cheap-first order for each seed. Both roles first answer
ECONOMIC_EXPOSURE, EXPECTATION_GAP, TRADABILITY, and CATALYST. If either role finds any of its core
dimensions NO or UNKNOWN, that role stops expanded research for the seed and fills all remaining
dimensions with UNKNOWN and empty evidence. It must still return the complete eight-dimension
schema. Only a role with four core YES answers researches valuation, governance, crowding, and
falsifier. The deterministic combination rule is unchanged; this saves cost without weakening a
gate or treating missing work as support.

The host must submit screen isolation as verified, degraded, or unverified. A claimed value of
`verified` is insufficient. Only verified physical isolation with a validated
`candidate-screen-isolation.v1` receipt is eligible for THESIS_CANDIDATE. The receipt binds the
stored dispatch and exact role prompt hashes to the exact submitted payload hashes. The
`agy_separate_process_v1` profile additionally requires successful exits and distinct process and
invocation IDs. The `codex_collaboration_v1` profile requires completed independent agent contexts,
distinct host-returned agent IDs, and distinct invocation IDs. A missing, mismatched, or invented
receipt caps the result at WATCHLIST.

The receipt is an auditable process-integrity control, not a cryptographic trust boundary against
a malicious host with filesystem access. A stronger deployment should sign receipts with a
host-held key inaccessible to either role. Antigravity's permission bypass is opt-in: pass
`--allow-agent-tools` only after the caller explicitly authorizes non-interactive tool use.

## Fixed questions

| Dimension | YES means |
|:---|:---|
| ECONOMIC_EXPOSURE | Candidate directly and materially captures the value transfer; it is not merely theme-adjacent. |
| EXPECTATION_GAP | Observable expectations do not yet fully reflect the causal exposure. |
| VALUATION_CONTEXT | Current valuation and embedded expectations are evidenced well enough to challenge. |
| TRADABILITY | A realistic research/trading expression exists without an obvious access or liquidity hard block. |
| GOVERNANCE | No evidence-backed fatal governance, related-party, or capital-allocation problem was found. |
| CROWDING | No evidence-backed fatal crowding, ownership, or reflexivity problem was found. |
| CATALYST | A dated or conditional, observable catalyst exists inside the research horizon. |
| FALSIFIER | A concrete kill condition and recurring monitoring source exist. |

Use only YES, NO, or UNKNOWN. YES and NO require a concise finding and at
least one fresh, concrete citation. Absence of negative evidence is not proof
of YES; use UNKNOWN.

## Payload schema

~~~json
{
  "as_of_date": "YYYY-MM-DD",
  "candidate_screens": [
    {
      "seed_id": "OS-...",
      "questions": [
        {
          "dimension": "ECONOMIC_EXPOSURE",
          "answer": "YES|NO|UNKNOWN",
          "finding": "<short causal finding; blank only for UNKNOWN>",
          "evidence": [
            {
              "claim": "<what the source establishes>",
              "number": null,
              "source": "<organization>",
              "url": "<specific article, filing, dataset, or API URL>",
              "date": "<YYYY-MM-DD or YYYY-MM>",
              "source_tier": "primary|secondary"
            }
          ]
        }
      ]
    }
  ]
}
~~~

Each candidate must contain all eight dimensions exactly once. Each runtime may
screen at most three candidates per batch. For `UNIVERSE_SEARCH` and `COMPARATIVE`, the first
post-convergence batch is selected deterministically from de-duplicated READY seeds using evidence
breadth, causal directness, structured pricing-anchor completeness, and an observable catalyst.
These are research-priority features, not expected return, conviction, position size, or a trade
ranking. Zero selected candidates is valid; do not fill the batch with lower-state leads.

Evidence on `example.com`, `example.org`, `example.net`, `.test`, `.invalid`, localhost, or
loopback hosts is synthetic and must be dropped. Independent source organizations are counted from
publisher domains, not the submitted `source` string. A valid stage-specific receipt can establish
physical CandidateScreen isolation even if the parent research runtime was unverified; without the
receipt, effective isolation is the weaker of run-level attestation and the screen submission.

Search and grounding redirect wrappers (including Vertex grounding redirects, Google `/url`, and
Bing `/ck/`) are not publisher evidence. Resolve them to the final issuer, regulator, filing,
dataset, exchange, or article URL before submission. If the final URL is unavailable, answer
`UNKNOWN`.

## Deterministic combination

For each dimension:

- SUPPORTED: both agents answer YES, with at least two fresh concrete URLs
  from at least two source organizations.
- REJECTED: both answer NO with the same source-diversity minimum.
- CONTESTED: one answers YES, the other NO.
- INCOMPLETE: missing, stale, single-source, or UNKNOWN evidence.

Market-sensitive evidence (VALUATION_CONTEXT, TRADABILITY, CROWDING, CATALYST)
must be no older than 120 days. Other dimensions must be no older than 550 days.

## Candidate status

- REJECTED: a corroborated NO on ECONOMIC_EXPOSURE, EXPECTATION_GAP,
  TRADABILITY, GOVERNANCE, or CROWDING.
- THESIS_CANDIDATE: all eight dimensions are SUPPORTED, with at least six
  unique URLs, two primary-source URLs, four source organizations, and at least
  three URLs from each agent, under host-verified agent isolation.
- WATCHLIST: every other outcome, including disagreement and missing evidence.

THESIS_CANDIDATE creates only a DRAFT_REQUIRES_SOURCE_VERIFICATION promotion
packet. Follow references/claim-verification-protocol.md to bind decisive claims
to content-hashed page snapshots. Only a VERIFIED result changes the packet to
DRAFT_REQUIRES_HUMAN. Human confirmation must then start a fresh -deepthink2
topic; the new thesis must not inherit the original thesis's crux support
scores, verdict, or convergence.
