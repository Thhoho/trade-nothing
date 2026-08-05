# Trade Nothing v0.13 — 上下文效率与机会发现能力优化方案

> 设计日期: 2026-08-04 | 基于 v0.12 6轮"中国AI算力中心"实战定量剖面

---

## 一、问题诊断: 数据驱动的剖面

### 1.1 每轮 Token 消耗拆解

基于"中国AI算力中心"真实 state (6轮、35条假说、6个候选种子):

```
                      Detective   Inquisitor   Judge    合计
Prompt (输入)           ~12,500     ~9,400      ~800    ~22,700
Agent 输出 (估计)        ~3,000      ~3,000     ~1,500    ~7,500
每轮合计                 ~15,500     ~12,400    ~2,300   ~30,200
6轮总计                                                        ~181,000 tokens
```

### 1.2 Prompt 成分分析

| 成分 | Token 占比 | 每轮变化? | 优化潜力 |
|------|-----------|----------|---------|
| 探索轨 JSON (35条假说全量) | ~45% | **否** (静态) | 🔴 极高 |
| Crux 状态 (monitor/bull/bear/plan) | ~15% | 是 (bull/bear更新) | 🟡 中 |
| 前提账本 (premise_audit) | ~4% | 否 | 🟢 可移入agent.md |
| 预算/产业链/范围指令 | ~8% | 否 | 🟢 可移入agent.md |
| 决策上下文 (horizon/as_of等) | ~5% | 否 | 🟢 可移入agent.md |
| Landscape 分配 | ~5% | 是 | 🟡 中 |
| 负面先验 + 平庸共识 | ~5% | 否 | 🟢 可移入agent.md |
| 轮次特有内容 (scope/roam) | ~3% | 是 | 低 |
| 角色任务描述 | ~5% | 否 | 🟢 可移入agent.md |
| 硬约束 | ~5% | 否 | 🟢 可移入agent.md |

**关键发现**: 约 **67% 的 prompt token 是跨轮静态内容**。每轮重复发送这些内容相当于浪费了 ~15,000 tokens/轮。6轮累计浪费 ~75,000 tokens——足以多跑 2-3 轮实质性辩论。

### 1.3 根因: 无状态 Agent 调度模型

当前架构的根本假设是: Detective 和 Inquisitor 是**无状态子代理**，每轮从零开始，不携带上轮记忆。这要求每轮 prompt 必须包含完整上下文。这是安全的（真正隔离），但代价高昂。

---

## 二、设计原则

在进入具体方案之前，先确立三条原则，确保优化不损伤核心安全属性:

### 原则 1: 隔离优先于效率
Agent 上下文隔离是辩论质量的基石。任何优化不得让 Detective 和 Inquisitor 共享中间推理。**静态指令可以共享且移入 agent.md，但动态状态必须通过 prompt 传递。**

### 原则 2: 信息密度优先于信息量
Prompt 中每一条信息都应满足 "如果删除它，agent 本轮输出会有可观测的劣化"。当前 prompt 中大量内容是"以防万一"的安全网，它们应该被移到 agent.md 中作为持久指令，而非每轮重复。

### 原则 3: 发现能力是核心 KPI
优化的首要目标不是降低成本，而是提升机会发现效率。省下的 token 预算应该转化为: 更精准的搜索路线、更深的价值链追踪、更多轮的实质性辩论。

---

## 三、分环节优化设计

### 3.1 Framer: 从"盲跑"到"知情立题"

#### 问题本质

Framer 无搜索能力。对于"中国AI算力中心"这类主题，Framer 必须在没有接触任何具体数据的情况下:
1. 定义 2-5 个承重 crux (每个需要 monitor_anchor, falsifier, evidence_plan)
2. 生成 5-7 条 WildHypothesis (每个需要 causal_chain, scenario_paths, asymmetry_case)
3. 规划每条 crux 的 2-3 条 evidence_plan 路线（指定 publisher_class 和 search_query）

这要求 Framer 对该领域有深度预训练知识。对于细分/新兴/中文主题，这是不可靠的。

#### 证据: 算力中心案例的 Framer 质量检查

从实际运行结果回看 Framer 输出:
- ✅ 4条 crux 的选题准确 (C1建设/消耗, C2经济性, C3稀缺/价值, C4价格)——这些确实是该主题的核心争议
- ⚠️ evidence_plan 中的 publisher_class 偏泛化 (REGULATOR_OR_OFFICIAL_DATASET / ISSUER_OR_FILING)。实际运行中，最有价值的证据来自 SMM 价格指数、具体公司公告、政府采购平台——这些不属于 Framer 预设的 publisher_class
- ⚠️ WildHypothesis 中的一部分是"显然的"（瓶颈所有者、替代路径），缺乏真正的非共识洞察

#### 设计方案: 分层立题 (Stratified Framing)

```
Phase -1 (新增): Pre-framing Scout (可选, 用户不提供context时自动触发)
  ┌─────────────────────────────────────────────────────┐
  │ 输入: topic 字符串                                    │
  │ 执行: 2-3 次有界网页搜索 (关键词: topic + "争议/分歧/产能/价格") │
  │      提取: 当前市场争议点、关键参与方、近期催化剂日期      │
  │ 输出: Scout Memo (~500字, 结构化)                     │
  │       { disputes: [...], actors: [...], catalysts: [...] } │
  │ 约束: 不形成观点, 不选择方向, 不评级                    │
  └─────────────────────────────────────────────────────┘
                          ↓
Phase 0 (现有): Framer (增强版)
  ┌─────────────────────────────────────────────────────┐
  │ 输入: topic + Scout Memo + 可选 User Briefing         │
  │ 执行: 内联 (现有约束不变: 无搜索/无子代理)               │
  │ 增强: evidence_plan 可使用 Scout Memo 中的具体          │
  │       publisher 名称 (e.g. "SMM" 而非仅                 │
  │       "REGULATOR_OR_OFFICIAL_DATASET")                 │
  │ 输出: 现有 Framer JSON + scout_attribution             │
  └─────────────────────────────────────────────────────┘
```

**关键设计决策**:
- Scout 不是研究——它不评估证据、不形成观点、不进入证据账本。它只是"告诉 Framer 这个领域的玩家和争议是什么"。
- Scout 结果标记为 `SCOUT_PROVISIONAL`，不在正式报告中出现。
- 如果用户提供了 User Briefing（见下文），则跳过 Scout。

#### 子设计: User Briefing 协议

```
用户可选输入: --briefing "text or URL"
  - 接受: 纯文本 (≤2000字) 或 1-3 个 URL
  - URL 会被抓取并提取正文 (~1000字/URL)
  - Framer 在 framing prompt 中看到: "[USER BRIEFING] ... [/USER BRIEFING]"
  - 用途: 用户在 framing 前告诉系统 "我已经知道这些"
  - 约束: briefing 内容不被当作证据，Framer仍必须将所有premise标记为HYPOTHESIS
```

**预期效果**:
- Framer crux 准确率: 从"依赖模型先验"提升到"有当前市场上下文"
- evidence_plan 精度: publisher_class → 具体 publisher 名称
- WildHypothesis 质量: 基于真实争议而非泛化假设
- Token 成本: Scout 阶段 ~2000 tokens (2-3次搜索 + 提取)，可显著提升后续 6 轮效率

---

### 3.2 辩论 Prompt: 从"全量重发"到"静态/动态分离"

#### 问题定量

当前每轮 Detective prompt ~12,500 tokens，其中:
- **静态部分 (~8,400 tokens, 67%)**: 探索轨JSON、预算指令、产业链指令、前提账本、负面先验、硬约束、任务描述
- **动态部分 (~4,100 tokens, 33%)**: OPEN crux 状态 (bull/bear/plan)、Landscape 分配、轮次策略 (free_roam/new_crux)

当前 Inquisitor prompt ~9,400 tokens，同样 ~67% 静态。

#### 设计方案: Agent.md 持久化 + Prompt 动态层

**第一步: 将静态指令移入 agent markdown 文件**

以下内容从每轮 prompt 中移除，永久写入 `agents/detective.md` 和 `agents/inquisitor.md`:

```
移入 detective.md:
  - 产业链检查规则 (🔗 当前为每轮 5 行)
  - 有界研究预算 (🧮 当前为每轮 8 行)
  - 硬约束: 数据点格式要求 (当前为每轮 3 行)
  - 负面先验检查指令 (结构, 具体先验内容仍保留在 prompt)
  - 平庸共识禁区 (具体内容仍保留在 prompt)
  - 探索轨规则 (规则部分, 数据部分保留在 prompt)
  - OpportunitySeed 收割规则 (规则部分, 不包含每轮crux状态)

移入 inquisitor.md:
  - 同上
  - Free-roam 规则
  - 新 crux 提议规则
  - odds_calibration 字段要求

保留在每轮 prompt:
  - 决策问题 / horizon / as_of (核心上下文)
  - OPEN crux 具体状态 (bull/bear/monitor/catalyst/evidence_plan)
  - 已收敛 crux 上下文
  - 具体负面先验内容 (从 Evolution.md 提取)
  - 具体平庸共识列表
  - 探索轨当前数据 (压缩版, 见下文)
  - Landscape 本轮分配
  - 轮次策略 (free_roam 开关 / new_crux 开关)
  - 本轮调度 crux 列表
```

**第二步: 探索轨 JSON 压缩**

当前: 全量 WildHypothesis JSON (35条 × ~150 tokens/条 = ~5,250 tokens)

优化后: 摘要表 (每条 1 行)

```
✨ 假说探索轨 (无证据评分、候选晋级或交易权限):

现有假说 (引用时使用 hypothesis_id):
| ID | 猜想 (≤15字) | 状态 | 优先级 | ProxyTrail |
|----|-------------|------|--------|------------|
| WH-A1 | 光互联InP衬底锁料 | EVIDENCE_BACKED | HIGH | 2条 |
| WH-A2 | 绿电闭环溢价 | TRACED | MEDIUM | 1条 |
| WH-A3 | 液冷毛利率陷阱 | HYPOTHESIS_ONLY | PARK | — |
...

规则: 每轮最多 3 sparks + 3 trails, 新猜想必须 HYPOTHESIS_ONLY, ProxyTrail 必须有 hypothesis_id。
完整假说详情见 state.json → hypothesis_ledger, 需要时由宿主注入。
```

**Token 节省**: 35条假说从 ~5,250 tokens → ~700 tokens (节省 ~4,500 tokens/轮)

**第三步: 动态上下文渐进增强**

当前 prompt 中每条 crux 展示完整信息 (bull/bear/monitor/falsifier/catalyst/evidence_plan)。对于已有多轮辩论的 crux，bull/bear 是可选的上下文增强——它们帮助 agent 了解"已经讨论过什么"，但 agent 的指令是"找新证据"。

优化: 保留 bull/bear (这是 agent 需要知道的"已有论证")，但压缩 evidence_plan 为仅显示未执行路线。

```
本轮重点质证以下 OPEN crux:

[C1] 建设、交付与消耗鸿沟
  对方最强(bear): 信通院用算占比36.8%(38亿vs14亿卡时)
  我方最强(bull): 并行/行云按Token计费盈利
  监控: 算力中心上架率与Token计费渗透率
  反证: 连续两个季度聚合付费增速<容量增速
  催化: 2026-08-31 并行/行云/奥飞中报 @ 2026-08-31 [REVIEW_CHECKPOINT]
  待查路线: REGULATOR_OR_OFFICIAL_DATASET (行业用算统计), CUSTOMER_OR_COUNTERPARTY (企业付费合同)
```

**Token 节省**: evidence_plan 从完整 JSON → 待查路线摘要行 (节省 ~200 tokens/crux × 4 cruxes = ~800 tokens/轮)

#### 预期总效果

| 指标 | 优化前 (每轮) | 优化后 (每轮) | 节省 |
|------|-------------|-------------|------|
| Detective prompt | ~12,500 tokens | ~6,000 tokens | **-52%** |
| Inquisitor prompt | ~9,400 tokens | ~5,500 tokens | **-41%** |
| Judge prompt | ~800 tokens | ~800 tokens | 不变 |
| **每轮合计** | **~22,700 tokens** | **~12,300 tokens** | **-46%** |
| **6轮合计** | **~136,000 tokens** | **~74,000 tokens** | **-62,000 tokens** |

**省下的 62,000 tokens 可以做什么**:
- 多跑 3-5 轮辩论 (当前每轮 ~12,300 tokens prompt)
- 运行完整的 CandidateScreen (Analyst + Skeptic, ~8,000 tokens)
- 让 Detective/Inquisitor 做更深入的搜索 (当前每 crux 2 次搜索)

---

### 3.3 Report 渲染: 从"重复计算"到"单一数据源"

#### 问题

`build_report_view_model()` 和 `_render_audit()` 各自独立调用 `refresh_candidate_states()`、各自建立引用注册表 (ref_no)、各自计算候选评估。这在功能上不产生错误（两者看到相同 state，且 state 在 render 后不保存），但:
1. 浪费 CPU 周期（对 6 候选 × 35 假说的 state，重复计算约 0.1s——小但无意义）
2. 为未来 bug 埋下伏笔（两个函数中的计算逻辑可能漂移）
3. 代码可维护性差（_render_audit 是 1400+ 行的单一函数）

#### 设计方案: View Model 作为唯一真相源

**核心变更**: `build_report_view_model()` 产生**所有**渲染函数需要的全部数据。渲染函数变为纯模板——它们只做格式化，不做计算。

```
cmd_report()
  │
  ├─ 1. refresh_candidate_states(state)     ← 只调用一次
  ├─ 2. tracking_engine.sync_tracking_ledger(state)
  │
  └─ 3. view_model = build_report_view_model(state)
       │
       ├── render_facts_box(view_model)      ← 纯模板 (现有)
       ├── _render_candidate_cards(view_model) ← 纯模板 (现有)
       ├── _render_insight_cards(view_model) ← 纯模板 (现有)
       ├── _render_decision_brief(view_model) ← 纯模板 (现有)
       └── render_audit(view_model)          ← 改为从 view_model 取值
```

**view_model 扩展**: 在现有字段基础上增加:
- `audit.citation_registry`: 预计算的引用去重表 (ref_no)
- `audit.crux_refs`: 每条 crux 的引用编号列表
- `audit.opportunity_refs`: 每条候选的引用编号列表
- `audit.citation_quality`: 证据质量统计
- `audit.screen_dimension_refs`: 筛选维度的引用编号

**代码变化量**: 
- `report_v2.py`: `_render_audit` 从 1400 行缩减到约 600 行（去掉所有计算逻辑，只保留格式化）
- `build_report_view_model`: 增加约 150 行（预计算引用注册表等）
- 净效果: 代码总量基本不变，但结构更清晰，未来修改更安全

---

## 四、系统级改进: 机会发现能力的提升

以上三个环节优化解决了"效率"问题。但还有一个更根本的问题需要设计:

### 4.1 问题: 当前系统缺乏"发现反馈环"

当前流程中:
- Framer 生成假说花园 (一次性, framing 时)
- Detective/Inquisitor 每轮最多 3 sparks + 3 trails (受预算约束)
- 假说通过 ProxyTrail 逐步升级 (HYPOTHESIS_ONLY → TRACED → EVIDENCE_BACKED)
- 但升级后的假说**没有反馈到正式轨**——它们必须在某轮被 agent 以 OpportunitySeed 形式重新提交，且必须通过完整的 evidence admission (同 agent/同轮/同 crux 证据)

**这意味着**: 一条在第 2 轮被标记为 EVIDENCE_BACKED 的假说，如果 agent 没有在第 3-6 轮主动将其作为 OpportunitySeed 重新提交，它永远不会进入候选筛选管线。

### 4.2 设计: 假说→种子自动晋升管道

```
假说成熟度           晋升条件                          动作
──────────         ──────────                        ────
HYPOTHESIS_ONLY    —                                 仅在探索轨可见
TRACED             2 条不同 publisher 的 ProxyTrail   可在探索报告中展示
EVIDENCE_BACKED    2 条 SUPPORTS ProxyTrail +         自动生成候选种子草稿
                   因果链≥3节点 + 替代解释已声明       (OS-DRAFT-xxx)
                                                        ↓
OS-DRAFT           满足 seed_contract_blockers +       → 自动转为正式
                   2个独立来源                         OpportunitySeed
                                                        ↓
正式 OS            通过现有的 assess_seed 闸门         → 进入候选管线
```

**关键安全约束**:
- 自动晋升**不绕过** seed contract blockers（经济暴露、预期差、定价锚、催化、反证）
- 自动晋升的种子标记 `source: "hypothesis_escalation"`，与 agent 提交的种子区分
- 如果晋升的种子缺少必需字段（如 pricing_anchor），它进入 EVIDENCE_BACKED 状态并触发 CandidateGapTask
- 用户可在报告中看到哪些种子来自自动晋升

**实现复杂度**: 中等 (~200 行新代码在 `opportunity_engine.py` 中增加 `escalate_mature_hypotheses()`)

### 4.3 设计: 发现率仪表盘

在当前报告的证据仪表盘 (A.2) 中增加:

```
发现效率:
  假说生成: 35 条 (Framer 7 + 辩论28)
  假说升级: HYPOTHESIS_ONLY 25 → TRACED 8 → EVIDENCE_BACKED 2
  种子转化: 6 条 (Agent提交 5 + 假说晋升 1)
  转化率: 2/35 = 5.7%
  平均每轮新发现: 1.0 条种子
```

这个仪表盘让用户和系统都能感知到"发现引擎是否在正常工作"——如果转化率持续 <3%，可能说明 framing 的假说花园质量差或辩论预算不足。

---

## 五、实现路线图

### Phase 1: Prompt 瘦身 (工作量: 3-4h, 预期 Token 节省: 46%)
1. 将静态指令从 dispatch_prompts() 移入 detective.md / inquisitor.md
2. 实现探索轨 JSON 压缩 (摘要表 → 全量按需注入)
3. 压缩 crux scope 中的 evidence_plan 展示
4. 更新测试以反映新的 prompt 格式

### Phase 2: Framer 增强 (工作量: 2-3h, 预期: Framer crux 准确率提升)
1. 实现 User Briefing 协议 (--briefing 参数)
2. 实现 Pre-framing Scout (可选, 无 briefing 时自动触发)
3. Framer prompt 增加 briefing/scout 上下文
4. 增加 framing 质量审计字段 (scout_attribution)

### Phase 3: 假说晋升管道 (工作量: 3-4h, 预期: 种子发现率 +20-50%)
1. 实现 `escalate_mature_hypotheses()` 
2. OS-DRAFT → 正式种子自动转换逻辑
3. 晋升来源标记 (source: "hypothesis_escalation")
4. 发现率仪表盘

### Phase 4: Report 重构 (工作量: 2-3h, 预期: 代码可维护性提升)
1. 将引用注册表计算移入 build_report_view_model
2. 将 refresh_candidate_states 移出渲染函数
3. _render_audit 简化为纯模板

---

## 六、预期效果总结

| 维度 | 当前 (v0.12) | 优化后 (v0.13) | 改善 |
|------|-------------|---------------|------|
| 每轮 prompt tokens | ~22,700 | ~12,300 | **-46%** |
| 6轮总 prompt tokens | ~136,000 | ~74,000 | **节省 62k tokens** |
| 可额外运行的辩论轮次 | 0 | 3-5 轮 | 更深收敛 |
| Framer crux 准确率 | 依赖模型先验 | 有当前市场上下文 | 提升 |
| 假说→种子转化 | 仅 agent 手动提交 | 自动晋升 + 手动 | **+20-50% 种子** |
| Report 渲染代码行数 | ~2200 (含重复计算) | ~1800 (纯模板) | **-18%** |
| 隔离安全性 | 完全隔离 | 完全隔离 (不变) | 不降级 |

---

*设计由 Claude (deepseek-v4-pro) 基于 v0.12 实战 token 剖面 + 产品哲学对标完成。Phase 1 可在确认后立即实施。*
