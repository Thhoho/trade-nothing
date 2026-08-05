# Contributing to Trade Nothing

Thank you for your interest in contributing to Trade Nothing! This project aims to be the gold standard for adversarial multi-agent investment research.

## Development Setup

```bash
git clone https://github.com/Thhoho/trade-nothing.git
cd trade-nothing
pip install -r requirements.txt
```

## How to Contribute

### Adding a New Data Source

1. Create a new script in `scripts/` following the existing patterns.
2. Use `utils.clean_proxy_env()` if the data source is domestic (China).
3. Always output structured JSON to stdout.
4. Add error handling with multi-source fallback.
5. Update `references/data-sources.md` with the new source.
6. Add detailed usage to the relevant protocol under `references/`; keep `SKILL.md` concise.

### Extending Agent Runtime Compatibility

1. Add or update the row in `references/runtime-compatibility.md`.
2. Document the exact dispatch, timeout, process cleanup, output parsing, and receipt profile.
3. Add deterministic failure-injection tests before marking an adapter implemented. A persona-file
   mapping alone is documentation-only support.

### Improving the DeepThink Engine

1. Orchestration and report routing live in `scripts/deepthink_orchestrator_v2.py`.
2. Crux support scoring and deterministic convergence live in `scripts/crux_engine.py`; the
   legacy LFI/Bayesian pipeline was retired in v0.13.0.
3. Test with `make test`; use `deepthink_orchestrator_v2.py --selftest` only as the bounded wiring
   fixture, not as effectiveness evidence.

## Pull Request Standards

- **No hardcoded personal paths**. All paths must use `utils.py` helpers or environment variables.
- **No secrets or credentials** in code or commit history.
- **Version semantics**: The current source version is `v0.13.0`. Use it on active runtime, agent,
  CLI, and README surfaces; preserve explicit historical versions in design notes, compatibility
  branches, frozen benchmarks, and old tags. Run `python3 scripts/version.py` before submitting.
- **Bilingual support**: Keep Chinese comments/terms where they add domain-specific clarity.
- **Test before submitting**: Run the verification commands from the README.

## Code Style

- Python: PEP 8, with `#!/usr/bin/env python3` shebang on all scripts.
- Markdown: GitHub Flavored Markdown with Mermaid diagrams where helpful.
- JSON: 2-space indentation, `ensure_ascii=False` for CJK characters.

## Reporting Issues

Use GitHub Issues. Include:
- Your agent runtime (Claude Code, Gemini CLI, Antigravity, etc.)
- Python version
- OS and platform
- Relevant error output

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
