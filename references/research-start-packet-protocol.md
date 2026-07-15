# Research-start packet protocol

`tradenothing-next` may return an `ACTIVE` Lesson to a future `trade-nothing` run only through
`trade-nothing.research-start-packet.v1`.

The product creates the packet after a human selects one to ten `ACTIVE` Lessons and writes a
specific reason for each. The packet contains immutable Lesson snapshots, a question contract,
an explicit no-inheritance policy, and a SHA-256 checksum. It contains no prior verdict, support
score, candidate state, actionability, or prior evidence.

Validate before framing:

```bash
python3 scripts/research_start_packet.py /path/to/RSP-....json
python3 scripts/deepthink_orchestrator_v2.py --frame \
  --topic "EXACT PACKET TOPIC" --start-packet /path/to/RSP-....json
```

The Framer must copy the emitted `research_start_binding` into its JSON, and `--init` verifies that
binding against the supplied packet. The Framer may use each Lesson only as a challenge constraint: turn it into a premise audit,
falsifier, comparison axis, or explicit failure mode. A Lesson is never evidence for the new
question and must not pre-decide any crux or verdict. `--init` must receive the same packet so the
checksum and bounded context are persisted in the new state.

If validation, checksum, topic, or frame binding fails, stop with `start_packet_rejected`. Never
repair the packet or copy fields by hand. Generate a new packet in the product.
