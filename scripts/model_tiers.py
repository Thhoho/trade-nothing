# -*- coding: utf-8 -*-
"""
Trade Nothing v0.13.1 — Model Tiering Policy

分层调用模型，但绝不牺牲核心质量：只把"机械的、规则约束的"任务下放给小模型，
研究/对抗推理/综合写作始终用 deep 模型。

Tier assignment (task -> tier):
  DEEP  : detective, inquisitor, candidate_analyst, candidate_skeptic, claim_verifier,
          crux_extraction, judge_scoring,
          battle_log_synthesis (Judge directly controls the formal-report gate)
  FAST  : optional non-authoritative formatting tasks only. Evidence de-duplication
          and citation normalization are implemented deterministically in Python.

Override via env:
  TRADE_NOTHING_MODEL_DEEP   (default: inherit host default / 'opus')
  TRADE_NOTHING_MODEL_FAST   (default: 'haiku')
Set TRADE_NOTHING_MODEL_FAST = TRADE_NOTHING_MODEL_DEEP to disable tiering entirely.
"""
import os

_DEEP = os.environ.get("TRADE_NOTHING_MODEL_DEEP", "opus")
_FAST = os.environ.get("TRADE_NOTHING_MODEL_FAST", "haiku")

# task -> tier label
TASK_TIER = {
    "detective":            "deep",
    "inquisitor":           "deep",
    "candidate_analyst":    "deep",
    "candidate_skeptic":    "deep",
    "claim_verifier":       "deep",
    "crux_extraction":      "deep",
    "battle_log_synthesis": "deep",
    "judge_scoring":        "deep",
    "dedup_novelty":        "fast",
    "citation_normalize":   "fast",
}


def model_for(task: str) -> str:
    """Return the model id the host runtime should use for a given task."""
    tier = TASK_TIER.get(task, "deep")   # unknown task -> deep (never silently downgrade)
    return _FAST if tier == "fast" else _DEEP


if __name__ == "__main__":
    import json
    print(json.dumps({t: model_for(t) for t in TASK_TIER}, ensure_ascii=False, indent=2))
