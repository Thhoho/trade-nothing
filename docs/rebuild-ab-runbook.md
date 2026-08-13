# 决定性 A/B 运行手册

目标：用已有冻结套件，一次跑出「薄宪法 vs 裸基线」的盲评结论。同模型、同 as-of、同预算。
通过标准沿用你自己的门槛（v0.17 文档）：成本 ≤1.25–1.5x、重大事实召回 ≥ 基线、5 题中 ≥4 题
决策可用性更优；未通过就删除模块，不加轮次掩盖失败。

## Phase 1：封闭语料盲评（便宜、确定、不烧配额、无 as-of 泄漏）

1. **基线臂**：`benchmarks/v014-six-case/arms/single_agent.md`（已存在——就是"裸模型 + 7 条结构化提示"）
2. **候选臂**：把 `rebuild/SKILL.md` 的"封闭语料模式"节 + 流程第 1/3/4 步存成 arm 指令文件
   `rebuild/arms/closed-packet.md`
3. 跑 6 个 case × 2 臂（同一模型）：

   ```bash
   python3 scripts/benchmark_harness.py dispatch \
     --suite benchmarks/v014-six-case/suite-386d8df.json \
     --case-id <case_id> --variant <single_agent|候选臂> --output <run_dir>
   ```

   然后 `verify`、`score`（assessor 用 `assessor/rubric.md` + `answer-key-386d8df.json`，盲评：评分者不知哪份报告来自哪臂）。
4. **决策线**：
   - 薄版在 `decisive_claim_correct` / `major_path_found` / `false_opportunity_count` /
     `maturity_misread_count` / `comprehension_question_correct` 上 ≥ 基线，且无 P0 负回归 → 进 Phase 2
   - 薄版 < 基线 → 推理层没有增量：个人 skill 退役，内核留给线上服务定位

   注意：CLOSED_PACKET 只测推理/决策压缩，**不测检索增量**；检索增量靠 Phase 2。

## Phase 2：真实检索 A/B（Codex 里）

1. 选 1 个真实问题（你自己关心的、最好含上市公司——能检验官方索引枚举的增量；模糊一点最好——检验"可能性探索"）
2. 冻结 as-of 与预算；同模型跑两遍：裸 Codex vs `rebuild/SKILL.md` 完整流程
3. 计量：耗时、token、material 事实召回（跑前冻结事实 key，不泄露给运行模型）、报告可读性
4. 决策线：成本 ≤1.25x、召回 ≥ 基线、决策可用性更优 → 薄版正式接班；否则退役个人路径

## 冻结纪律

- 评分者拿到报告前拿到冻结事实 key
- 两臂的模型、as-of、工具权限完全相同
- 跑前记录各臂实际成本（轮数、调用数、token），成本也是评分项
