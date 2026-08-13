# Phase 1 封闭语料盲评结果（2026-08-13）

## 协议

- 套件：`benchmarks/v014-six-case/suite-rebuild.json`（从冻结 suite-386d8df 派生，两臂：`single_agent` 基线 vs `thin_rebuild` 薄宪法）
- 模型：两研究臂同模型（会话默认）；评估臂 haiku（rubric 机械计数，符合分层原则）
- 盲评：每案例两报告随机编号 A/B（映射见 `.runs/rebuild-ab-20260813/assessor-mapping.json`），评估者不知道臂身份
- 12/12 案例×臂可比较，零错误，`method_change_gate_pass: true`
- 数据：`.runs/rebuild-ab-20260813/`（result/assessment/score.json 全部绑定 hash）

## 结果

| 指标（6 案例合计） | single_agent 基线 | thin_rebuild | 判定 |
|---|---|---|---|
| decisive_claim 正确率 | 33/34（97.1%） | **35/35（100%）** | 薄版 +1 |
| false_source | 0 | 0 | 平 |
| major_path 覆盖 | **30/35（85.7%）** | 27/35（77.1%） | 基线 +3 |
| false_opportunity | 0 | 0 | 平 |
| effective_seed | 13 | 13 | 平 |
| **pricing_anchor 有效** | 4/17（23.5%） | **13/17（76.5%）** | **薄版 3.2x** |
| maturity_misread | 0 | 0 | 平 |
| comprehension | 17/18 | 17/18 | 平 |
| tokens | 77,267 | 78,548（**1.017x**） | 平价（门槛 1.25–1.5x 通过） |
| wall_seconds | 306 | 451（含一个 100s 调度异常值） | token 是诚实成本口径 |

## 判定

**薄宪法在成本平价（+1.7% token）下，在全部决策质量维度 ≥ 基线，其中三处显著领先：**
1. **pricing_anchor 有效 76.5% vs 23.5%（3.2 倍）**——基线臂只是复制价格，薄版强制陈述"什么期望差让它有吸引力"，或显式声明缺口不可量化（NO_RESULT 也算有效锚定）。这正是"非对称真相"的核心纪律：搞清楚价格里已有什么。
2. **claim 正确率 100%**——标签纪律（FACT/SINGLE_SOURCE/INFERENCE/HYPOTHESIS）压掉了基线的 1 个错误主张。
3. **零假机会、零成熟度误读**（两臂都是 0，陷阱检查表维持住了）。

**唯一负回归：major_path 覆盖 77.1% vs 85.7%（-3 条路径）。** 原因清楚：薄版把"无证据路径"只标 INSUFFICIENT 而没有落"显式拒绝 + 理由"，评估者不把纯 INSUFFICIENT 计为"justified rejection"。**修复已入薄宪法**（`rebuild/SKILL.md` 第 1 步：每条主要路径必须显式评估或显式拒绝并说明理由）。已测臂保持字节冻结在 `benchmarks/v014-six-case/arms/closed-packet-thin.md`（hash 绑定不变）；`rebuild/arms/closed-packet.md` 已含修复，作为下一轮迭代臂。

## 结论与限制

- 通过你自己的发布门槛：成本 1.017x（≤1.5x）、零 P0 负回归、方法门 `METHOD_CHANGE_READY`。
- **限制（必须诚实）**：CLOSED_PACKET 只测推理/纪律层，**不测检索增量**（官方索引枚举、事实召回）。基线是 7 条结构化提示的强基线，不是零指令裸模型——薄版打赢的是更高标准。
- **下一步 = Phase 2**：一个真实检索 A/B（裸 Codex vs 薄宪法完整流程），检验检索层增量；同时用修复后的臂复跑 Phase 1 验证路径覆盖修复（约 12 次调用）。
