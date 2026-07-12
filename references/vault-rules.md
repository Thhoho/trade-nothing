# Workspace & Vault Protocol (v0.9)

Defines physical storage locations for all reports and research data.

## 1. Path Conventions

All paths are configurable via environment variables. See `SKILL.md` Section 4 for the complete table.

| Path | Default | Env Variable |
|------|---------|-------------|
| **Vault Root** | `~/trade-nothing-vault` | `TRADE_NOTHING_VAULT_DIR` |
| **Research Logs** | `<vault>/Research_Log/` | — |
| **Company Deep Dives** | `<vault>/Company_DeepDive/` | — |
| **Fact Anchors** | `<vault>/Facts/` | — |
| **Methodology Evolution** | `<skill_dir>/Methodology_Evolution.md` | `TRADE_NOTHING_EVOLUTION_PATH` |
| **Runtime State** | `~/.trade-nothing/scratch` | `TRADE_NOTHING_SCRATCH_DIR` |
| **Generated Reports/Models** | `~/trade-nothing-outputs` | `TRADE_NOTHING_OUTPUT_DIR` |

## 2. Naming Convention

- **Report files**: `Research_Log/{{DATE}}-{{TOPIC}}-R{{N}}.md`
- **Date format**: `YYYY-MM-DD` (ISO 8601)
- **Topic spec**: English+Chinese/keywords
- **R{{N}}**: Recursive round identifier (e.g., R7 = 7 rounds completed)
- **Example**: `2026-04-09-HJT_Solar-R8.md`

## 3. Report Metadata

Every report must include YAML front matter:

```yaml
---
title: "..."
date: YYYY-MM-DD
topic: "..."
rounds: N
lfi_final: 0.XX
posterior: XX%
verdict: "强力出击 / 沉睡 Alpha / No Edge"
tags: [TradeNothing, VariantPerception]
---
```

## 4. Automated Audit Rules

- Before writing, verify parent directory exists.
- If path contains spaces, use quote escaping.
- After writing, verify Exit Code.
- After each Vault write, append an entry to the research index via `scripts/deepthink_pipeline.py`.
