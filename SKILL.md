---
name: trade-nothing
description: >
  Value-first investment research for standard Q&A and -deepthink2. It first
  discovers what materially changed for the named subject, then answers a
  bounded Research Agenda, maps industry economics into market carriers by
  horizon, invokes an independent challenger only for load-bearing claims, and
  delivers an evidence-labelled Deep Research Report. Use for company, event,
  industry, thematic, A-share, commercial-space, AI-chain, photovoltaic, and
  similar research. It does not own orders, positions, portfolios, publication,
  or downstream handoff.
---

# Trade Nothing v0.16.0 — Value-First Research

> 先找全会改写结论的当期事实，再解释产业与市场，最后才做质证和审计。

**Skill root:** `./`

## 1. Product promise

Trade Nothing 的产品不是“跑完一个复杂流程”，而是比同模型裸研究更稳定地交付三种增量：

1. **Current truth**：主体最近发生了什么，哪些旧事实已被取代；
2. **Decision gain**：这些变化如何改变产业逻辑、市场载体、时点和条件性建议；
3. **Trust boundary**：事实、单一来源、推断和假说清楚分开，重大遗漏不能藏在脚注。

默认研究路径：

```text
问题与 as-of
  -> Primary Entities
  -> Current Reality Scan（主体级近期事实面）
  -> Material Change Gate（重大变化 / 已知重大线索）
  -> Research Agenda（只研究仍会改变判断的问题）
  -> Lead synthesis
  -> Targeted Challenge（仅在承重结论需要时）
  -> Current Truth projection
  -> 产业价值转移 × 市场载体 × 时间视野
  -> Deep Research Report
```

不得把流程完成、收据齐全、报告更长或候选更多当成产品价值。若同模型单次研究找到了关键
事实而 Skill 没找到，Skill 就失败了。

## 2. Boundary

范围内：事实变化、因果机制、替代解释、产业价值转移、经济暴露池、市场交易池、价格与
拥挤、具体证券、条件性 setup、风险、下一验证和报告。

范围外：Thesis/Decision 状态、订单、仓位、组合、收益承诺、提醒、自动发布和跨系统 handoff。
任何外部副作用仍需用户另行授权。

报告可写“条件性优先关注 / 继续观察 / 当前回避”，但必须给触发、失效、最接近替代项、
价格/筹码边界和证据标签；不得生成目标价、仓位或执行指令。

## 3. Research rules

### 3.1 Reality before Agenda

Framer 必须输出 1–4 个 `primary_entities` 和 4–8 个 Research Agenda 问题。Framer 不浏览；
实体和前提只是检索范围，不是证据。

首个 Lead 调用先完成每个实体的 `required_route_kinds`。每条覆盖必须保存实际 query、至少一个
具体 checked URL，以及 `FOUND / NO_RESULT / INSUFFICIENT`。对公司至少检查：

- 官方披露索引；
- 最新定期报告；
- 合同、客户、订单、产销与经营里程碑；
- 融资、资本、股权、治理、监管与诉讼。

项目、事件和主题使用运行时给出的等价路线。`INSUFFICIENT` 不算完成；真实查过的
`NO_RESULT` 是有效负结果。

已核实、会改变承重结论的事件进入 `material_change_items`。搜索中已经看到但尚未核实的
潜在重大变化进入 `material_change_leads`，不能只写进“局限性”。任何开放的 HIGH lead，或
任何未完成的主体事实面，令交付状态成为 `MATERIAL_FACT_GAP`：报告仍可交付，但不得输出
decision-ready 推荐。

### 3.2 Agenda is a question ledger, not a ceremony

问题状态为 `OPEN / PARTIAL / ANSWERED / DISPUTED`。每个答案显示当前证据边界、最强反例、
缺失数据和下一测试可用性：`SEARCH_NOW / WAIT_FOR_DATE / WAIT_FOR_EVENT /
NEEDS_USER_DATA / UNKNOWN`。

只在低成本、高影响且 `SEARCH_NOW` 时建议下一轮。等待事件或用户数据不消耗研究预算。
旧报告中的关键发现最多提取 8 条作为 `baseline_findings`；本轮必须逐条标为
`REVERIFIED / SUPERSEDED / OUT_OF_SCOPE / UNRESOLVED`，不得继承旧证据等级。

### 3.3 Adaptive roles

- **Framer**：定义问题、实体与检索范围；不研究。
- **Value Lead（兼容名 Detective）**：先扫 Current Reality，再回答 Agenda，并把产业逻辑映射
  到市场和具体载体。
- **Targeted Challenger（兼容名 Inquisitor）**：只攻击已形成的承重答案，或补齐用户显式要求
  的 Landscape 第二侧探测；不重做全题扫描，不重复 CandidateMap。
- **Judge**：只服务显式 legacy crux audit。Agenda-native 默认不调用。
- **Parent**：只消费确定性 Current Truth、Agenda、Market Bridge 与证据账本生成报告。

运行器返回的 `required_roles` 是本轮唯一调用计划：首轮通常只有 Lead；事实门未清时继续
Lead；事实门已清但承重答案只有单侧研究，或显式 Landscape 尚缺第二侧覆盖时，才调用
Challenger；Judge 不得空转。省略角色必须
用 `SKIPPED` payload 表示，执行收据只绑定真实调用的角色。

隔离和收据证明“调用确实发生”，不证明研究有效或有 Alpha。

### 3.4 Industry-to-market mapping

严格区分：

```text
工程/政策事实 -> 约束变化 -> 利润池转移 -> 公司经济暴露
                                   ↓
事件与叙事 -> 增量资金 -> 市场交易载体 -> 拥挤/验证/分化
```

先写最短 `ValueTransferPath`，再分别固定经济暴露池与市场交易池。每个具名候选必须有公司名、
ticker（上市证券）、时间视野、最近替代项、为何现在优先、切换条件、触发和失效。

市场按 `EVENT_DAYS / TACTICAL_WEEKS / EARNINGS_QUARTERS / STRUCTURAL_YEARS` 分开解释。
技术成功、股价弹性和利润兑现不是一件事；不得用一个全局股票顺序覆盖四种视野。

`SETUP_READY` 只表示字段完整。没有价值路径、宿主行情回执、替代比较和时点理由时，候选只能
作为研究线索。`WATCH_ONLY / FAILURE_HEDGE` 不能变成推荐。

### 3.5 Evidence language

- `FACT`：来源直接支持；
- `SINGLE_SOURCE`：只有一个真实来源；
- `INFERENCE`：从已引事实推导；
- `HYPOTHESIS`：待验证机制或映射。

数字必须带具体 URL、发布者和日期。重复来源不重复计数。假说可以启发搜索，但不得冒充事实、
候选、价格证据或推荐权限。

## 4. Modes

### Standard Q&A

直接回答，必要时浏览当前资料；说明截止日和不确定性。普通问题不要启动完整运行器。

### `-deepthink2` — recommended deep research

1. 读取本文件；如用户说“最新 Skill 重跑”，先用当前 source method identity 创建新 run，
   不继承旧结论。
2. Framer 内联生成 frame；不浏览，不调用子代理。
3. 初始化后读取 `required_roles`，只执行列出的 prompt。
4. 提交角色 JSON 与执行收据；引擎更新重大变化、Agenda、Market Bridge 和 Current Truth。
5. 预算允许且引擎仍识别出高价值缺口时继续；否则立即报告。
6. 始终交付 `deep_research_report_markdown` 与 Evidence Ledger。

注册运行器（Antigravity / Claude Code）会自动执行自适应计划：

```bash
python3 scripts/deepthink_host_runner.py start --topic "TARGET" \
  --frame-json '<framer_output>' --run-purpose PRODUCTION_RESEARCH \
  --runtime antigravity --round-budget 1
python3 scripts/deepthink_host_runner.py resume --run-id "RUN-..." \
  --runtime antigravity --round-budget 2
python3 scripts/deepthink_host_runner.py status --run-id "RUN-..."
```

Codex collaboration 手动运行时，先创建/初始化 run；读取 dispatch 的 `required_roles`。只给实际
角色派发 prompt。对省略角色用下列命令生成 typed empty payload；收据命令只传实际角色的
payload 与 agent ID：

```bash
python3 scripts/deepthink_orchestrator_v2.py --empty-role inquisitor --round-number 1
python3 scripts/deepthink_orchestrator_v2.py --empty-role judge --round-number 1
python3 scripts/codex_deepthink_round_receipt.py --round 1 --dispatch dispatch.json \
  --detective detective.json --detective-agent-id "/root/lead" \
  --output round-1-receipt.json
```

只有 dispatch 明确包含 Judge 时才运行 `execution_integrity.py seal-judge-prompt`。提交命令仍提供
Lead、Challenger、Judge 三个 JSON 文件，其中省略者为 typed empty payload。

默认一轮是授权边界；额外轮次必须由用户明确给预算。429、超时、权限失败和无效 JSON 保留
checkpoint，不自动重试。宿主不足时可做 `INLINE_DEGRADED_RESEARCH`，但不得借用失败 run、
伪造角色或声称完成 N 轮。

执行真实性标签：

- `ORCHESTRATED_VERIFIED`：当前 method identity、注册 run、state 与每轮 adaptive receipt 匹配；
- `STATE_ONLY_UNVERIFIED`：有状态更新但没有完整收据；
- `HISTORICAL_REPLAY`：state 来自不同方法版本；
- `INLINE_DEGRADED_RESEARCH`：当前上下文直接研究，无可声明轮次。

### Other modes

- `-scan`：实验性雷达，不得包装成全市场扫描；
- `-calibrate`：历史断言审计，仅在用户要求时持久化；
- `-premortem`：对称构造 bull/base/bear、触发、传导和失效，不编概率或幅度。

## 5. Report order

1. 核心判断与明确边界；
2. Current Reality gate、重大变化、开放重大线索；
3. Research Agenda 答案、最强质证与缺口；
4. 产业价值转移和各时间视野的市场运行；
5. 经济暴露池 × 市场交易池、具体证券和最近替代项；
6. 条件性事件/经济 setup，或明确说明为何不能给；
7. 新盲点、情景、风险、下一最低成本验证；
8. Evidence Ledger、执行真实性与方法边界。

原始角色 payload、状态机字段和收据留在审计视图，不能占据首屏。零候选只有在完成具名证券、
替代、价格、筹码和失败路径搜索后才是有效结论。

## 6. Data sources

研究公开事实时优先一手官方来源。A 股行情按当前课题有界采集：

```bash
python3 scripts/free_market_observations.py --help
python3 scripts/market_snapshot_adapter.py --help
```

可选 Tushare Pro、BaoStock、AKShare 腾讯或 CSV。宿主用 `--ingest-market-snapshot` 摄入完整
adapter 产物后，行情才进入可信数据平面。`TUSHARE_TOKEN` 只存在于宿主父进程环境，不得进入
prompt、state、收据、报告或 Skill 安装目录。详细替换方式见 `references/data-sources.md`。

## 7. Product acceptance

工程验证：

```bash
python3 scripts/version.py
python3 scripts/benchmark_current.py --check --source-repo .
python3 scripts/product_value_benchmark.py --help
make test
```

首次建立盲评文件时读 `references/product-value-assessment.md`；它给出最短 key、assessment
和真实报告文件绑定示例，不进入日常研究上下文。

方法变更只有在同模型、同问题、同 as-of、可比预算下同时满足以下条件才值得保留：

- 加权重大事实召回不低于 single-agent baseline；
- 决策可用性更高，且无事实/假说洗白；
- 在尚未证明增益前，总成本不超过 baseline 的 1.5 倍；
- 若连续真实课题无收益，删除冗余角色或模块，不用更多流程掩盖失败。

工程测试、固定 fixture、`ORCHESTRATED_VERIFIED` 和报告成功渲染都不证明研究效果、Alpha
或收益。产品效果必须由真实主题对照与盲评决定。

## 8. Hard guardrails

1. 已知 HIGH 重大线索未处置时，不得写 decision-ready 结论。
2. 旧事实被新事实取代时，Current Truth 只能展示新版本；历史版本留审计。
3. 不得强制凑股票；无上市载体必须给搜索边界。
4. `NO_EDGE / NO_USABLE_SETUP / AVOID / SHORT` 不得互相替代。
5. 新 URL、来源数、轮次数、候选数和报告长度不是成功指标。
6. 预算、外部写入、安装、推送、发布和交易动作均需当前明确授权。
7. Skill 到 Deep Research Report 为止，不创建下游业务状态。

---

*Trade Nothing v0.16.0 — Current truth first. Decision gain over process theatre.*
