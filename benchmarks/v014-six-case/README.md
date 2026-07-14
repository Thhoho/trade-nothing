# v0.14 Six-case Frozen Benchmark

This directory is the reproducible input contract for the initial 6 x 3
`CLOSED_PACKET_REASONING` comparison.

It measures whether an arm can reason from the same frozen facts, control maturity, avoid false
opportunities, and produce a usable report. It does **not** measure source discovery, full-universe
coverage, proprietary insight, or alpha. Those require a separate searchable frozen-corpus suite.

- A research arm may receive only a generated single-case dispatch packet. Do not hand it this
  repository or the benchmark directory.
- `assessor/answer-key.json` is evaluator-only. Never place it in a research context.
- `results/` is intentionally absent until real arm executions are frozen.
- Evidence extracts are curator-frozen summaries of sources available on or before each case as-of.
  They are not a substitute for the linked source body in production claim verification.
- Extracts intentionally omit evaluator conclusions, but their source selection still embeds curator
  judgment. Treat path coverage as closed-packet reasoning coverage, not treasure-finding recall.
- Market observations are unadjusted closes captured for the stated session. They are pricing
  anchors, not recommendations and not future-return labels.

Validate before dispatch:

```bash
python3 scripts/benchmark_harness.py validate-suite \
  --suite benchmarks/v014-six-case/suite.json
```

Materialize one arm input into a separate runtime directory:

```bash
python3 scripts/benchmark_harness.py materialize-case \
  --suite benchmarks/v014-six-case/suite.json \
  --case-id ai_power_infrastructure_2025 \
  --output /private/tmp/ai_power_infrastructure_2025.dispatch.json
```

The command refuses to write inside this suite directory and refuses to overwrite an existing
packet. The resulting file binds the suite contract hash, exactly one case, and only that case's
frozen evidence. The evaluator answer key remains physically separate.

Installed skill copies also contain this benchmark for reproducibility. A benchmark research arm
must run without filesystem/tool access or external search and receive only the generated dispatch
file; merely telling
an agent not to open `assessor/` is not blind isolation.

The suite deliberately contains traps that a useful method should expose: demand is not necessarily
mispricing; proposed regulation is not final law; a higher freight rate is not automatically higher
equity value; one bank's governance and threshold effects do not prove sector-wide insolvency; and
power availability is not investable without delivery, customer-credit, financing, and valuation.
