# 废墟清点（2026-08-13 重建）

判断依据：真实运行数据（`.runs/jingang-*`：5.3MB JSON 移动换 10–20KB 真实主张）、
九版 `UNBENCHMARKED_METHOD_CHANGE`、以及唯一被真实运行验证有价值的增量 = P0 事实门
（官方索引枚举找到了关键词搜索漏掉的资本结构事件）。

## 抢救（进入重建版）

| 资产 | 位置 | 抢救后的形态 |
|---|---|---|
| 冻结基准套件：6 案例 + 答案 + 盲评 rubric + single_agent 基线臂 | `benchmarks/v014-six-case/` | 不动。它是重建版的 fitness function；答案里的 `false_opportunity_traps` 就是原始目标"非对称真相"的编码 |
| 发现试点：corpus 网关 + 多角度检索纪律 | `benchmarks/v014-discovery-pilot/` | 检索纪律蒸馏进薄宪法第 2 步 |
| Tier-1 无 key 硬锚（FRED/EDGAR/Comtrade，实测可用） | `scripts/tier1_providers.py` | 可选工具命令，热路径之外 |
| A 股行情观察（免费源 + 快照适配器） | `scripts/free_market_observations.py`、`market_snapshot_adapter.py` | 可选：需要价格锚时用，热路径之外 |
| P0 事实门（官方索引枚举、标签纪律、NO_RESULT 边界、as-of） | v0.17/0.18 SKILL.md + 运行验证 | 蒸馏进薄宪法第 2 步——九版中唯一被真实运行验证过的增量 |
| 最弱环节约束（crux 遗产里唯一数学上成立的思想） | `scripts/crux_engine.py` 概念 | 蒸馏为薄宪法第 1 步一句话 |
| 成熟度诚实（预披露≠法律、计划≠交付、LEAD≠已验证） | rubric 的 `maturity_misread_count` | 蒸馏为陷阱清单 2/4 |
| v0.18 内核（四对象 + ledger + 内容寻址 + 收据） | `scripts/research_core.py`、`research_loop.py`、`research_report.py`、`research_io.py`、`research_registry.py`、`method_identity.py`、`process_control.py`、`codex_research_receipt.py`、`research_host_runner.py`、`model_process_runtime.py` | 不删。保留为**线上服务层**（可审计、跨会话状态是服务化时的差异化）；个人热路径不用 |

## 归档（不再触碰，git 历史保留为考古）

- **27K 行引擎群**：`crux_engine`、`deepthink_orchestrator_v2`、`report_v2`、`hypothesis_engine`、
  `research_agenda_engine`、`landscape_engine`、`opportunity_engine`、`market_bridge_engine`、
  `market_map_engine`、`candidate_screen_engine`、`candidate_gap_engine`、`claim_verification_engine`、
  `material_change_engine`、`tracking_engine`、旧 `research_kernel.py`、`research_output`、
  `deepthink_host_runner`、`run_registry`、`execution_integrity`、`research_start_packet`、
  `framing_feasibility`、`validate_report_v2`、`legacy_crux_audit_adapter`、`evidence_snapshot`、
  `deepthink_pipeline`、各 `codex_*_receipt` 旧构建器、`agy_candidate_screen_runner`、
  `claim_verifier_runner`、以及 `legacy/` 目录
- **角色提示词** `agents/`（detective/framer/inquisitor/judge——v0.17 已删，不再恢复）
- **旧契约** `references/`（report-contract.md 等 v0.16 契约，与当前 renderer 已不一致）
- **运行产物** `.runs/`、`reports/`（历史记录，不再是方法的一部分）
- **`var/`**（daily 功能，与研究技能无关）

## 重建版入口

- 薄宪法：`rebuild/SKILL.md`（一页，零强制 Python，双模式：真实检索 + 封闭语料）
- 决定性 A/B 手册：`docs/rebuild-ab-runbook.md`
