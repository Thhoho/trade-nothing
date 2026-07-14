# Candidate Pricing Gap Protocol

Use this protocol for every OpportunitySeed that may enter CandidateScreen. A strong company,
scarce asset, or plausible catalyst is not a pricing gap by itself.

## Required anchor

Emit one structured `pricing_anchor`:

```json
{
  "as_of_date": "YYYY-MM-DD",
  "anchor_type": "ABSOLUTE_VALUATION|RELATIVE_VALUATION|EMBEDDED_EXPECTATION|CONTRACT_PRICE|CAPACITY_OR_EARNINGS|MARKET_PRICE",
  "metric": "observable metric",
  "current_value": "current price, multiple, or embedded assumption",
  "comparison_value": "peer, historical, contract, or thesis-implied comparison",
  "source": "organization",
  "source_url": "specific URL",
  "source_claim": "what the source establishes"
}
```

The URL must exactly match evidence emitted by the same agent for the same crux in the same round.
Do not use an uncited memory, generic homepage, stale value, or a sentence saying only that the
market underestimates the candidate.

## Interpretation boundary

The seed anchor establishes a falsifiable starting point, not undervaluation. CandidateScreen must
still test EXPECTATION_GAP and VALUATION_CONTEXT bilaterally with fresh independent evidence.
Claim Verification must then bind decisive screen claims to page snapshots before human promotion.

Use `UNKNOWN` or leave the anchor empty when no observable as-of comparison exists. The engine will
preserve the lead as `EVIDENCE_BACKED` and block CandidateScreen rather than inventing precision.
