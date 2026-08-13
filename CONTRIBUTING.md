# Contributing to Trade Nothing

Trade Nothing optimizes for research value, semantic clarity and evidence integrity. A larger
framework is not automatically a better contribution.

## Development

```bash
git clone https://github.com/Thhoho/trade-nothing.git
cd trade-nothing
make test
```

The deterministic core is standard-library only. Optional providers are installed separately and
must never become an implicit prerequisite for the release gates.

## Architectural rules

- Persist only `TaskSpec`, `EvidenceStore`, `DecisionSnapshot` and `RunLedger` in the active loop.
- The Value Lead is the sole Snapshot writer. Code validates; the renderer formats.
- Add a new state object only if it cannot be represented as evidence, a Snapshot field or execution
  truth—and justify why its ownership cannot conflict.
- A model call must have one bounded WorkingSet, one output product and one expected decision delta.
- Challenger is optional and targeted. Never reintroduce a ceremonial fixed role pipeline or Judge.
- Keep official-index recall, evidence boundaries and industry/market bindings fail-closed.
- Never auto-retry an external call whose outcome or cost may be unknown.

## Data sources

Implement the observation contract in `references/data-sources.md`. Normalize symbol, exchange,
calendar, dates, units and adjustment mode; distinguish no result from provider failure. Credentials
stay in host environment variables and never enter prompts or artifacts.

## Active bundle

The installed Skill and method identity use the explicit allowlist in `scripts/method_identity.py`.
Adding a source file does not activate it. If a new file affects current behavior, add it deliberately
to the allowlist, source-sync tests and architecture documentation. Historical engines remain
outside the installed bundle.

## Pull request standards

- No hardcoded personal paths or credentials.
- The current source version is `v0.18.0`. Use it on active runtime, agent, CLI and README surfaces;
  preserve explicit historical versions in design notes, frozen benchmarks, legacy source and old
  tags. Run `python3 scripts/version.py` before submitting.
- Preserve explicit historical versions; never rewrite history merely to satisfy a string audit.
- Use deterministic failure-injection tests for runtime adapters.
- Add a product regression for any real missed fact or semantic contradiction.
- State separately what engineering tests prove and what forward effectiveness remains unverified.

## Required checks

```bash
python3 scripts/test_research_core.py
python3 scripts/test_research_loop.py
python3 scripts/test_current_reality_regression.py
python3 scripts/test_research_host_runner.py
python3 scripts/version.py
make test
```

Python follows PEP 8. Markdown uses GitHub-flavored Markdown. JSON uses two-space indentation and
`ensure_ascii=False` when generated from Python.

By contributing, you agree that your work is licensed under the MIT License.
