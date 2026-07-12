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
6. Add usage examples to `SKILL.md` Section 3 (Toolbox Quick Reference).

### Extending Agent Runtime Compatibility

1. Add a new row to the **Agent Runtime Compatibility** table in `SKILL.md`.
2. Document the specific dispatch mechanism for your runtime.
3. Ensure both `agents/detective.md` and `agents/inquisitor.md` persona files work with your runtime.

### Improving the DeepThink Engine

1. Convergence logic lives in `scripts/deepthink_engine.py`.
2. The LFI formula and Bayesian update rules are documented in `SKILL.md` Phase 3.
3. Test with: `python3 scripts/deepthink_engine.py --start --topic "Test" --no-timer`

## Pull Request Standards

- **No hardcoded personal paths**. All paths must use `utils.py` helpers or environment variables.
- **No secrets or credentials** in code or commit history.
- **Version consistency**: Use `v0.9.4` across all files.
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
