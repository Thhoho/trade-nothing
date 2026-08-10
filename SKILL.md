---
name: trade-nothing
description: >
  Topic-led, iterative investment-research skill for standard Q&A, -deepthink2
  deep research, experimental -scan, historical -calibrate, and symmetric
  -premortem work. It decomposes a topic into a Research Agenda, searches and
  challenges each question over bounded rounds, surfaces new blind spots, maps
  industry value transfer into economic-exposure and market-carrier universes,
  interprets market phases by horizon, and delivers an evidence-labelled Deep
  Research Report with cross-sectional conditional recommendations. Hypotheses are optional
  analysis tools. The skill does not own orders, positions, portfolios,
  publication workflow, or downstream handoff.
---

# Trade Nothing v0.15.0 — The Sovereign Alpha Hunter

> **从一个课题出发，拆清问题，逐轮搜索与质证：回答旧问题，也发现新盲点；最终形成
> 有市场判断、有具体载体、有前瞻性且证据边界清楚的报告与建议。**

**Skill Root:** `./`
**Product baseline and acceptance target:** `docs/topic-led-research-product.md`

## 0. Product boundary

Trade Nothing 的主产品是围绕一个投资课题展开的迭代深度研究，终点是供人判断的
**Deep Research Report（深度研究报告与建议）**。

范围内：

- 课题目标、待回答问题、搜索路线和逐轮研究进展；
- 现实变化、主题、事件和产业链研究；
- 因果机制、替代解释与证伪条件；
- 市场叙事、资金路径、具体证券、价格、流动性和筹码；
- 事件弹性与经济兑现的分轨比较；
- 每轮解决的问题、未解决的问题、新盲点与新问题；
- 条件性 setup、明确的研究/市场建议和下一验证动作；
- 带 URL、来源、日期和证据标签的完整深度报告。

范围外：

- Thesis、Decision、Paper Trade、订单、仓位、组合、归因；
- 提醒、外部发布审批和跨产品 handoff；
- 为尚未建设的下游流程预设状态、权限或收据。

旧代码中出现的上述对象只作历史兼容，不能进入默认运行、默认报告或产品承诺。
任何外部副作用仍需宿主和用户另行明确授权。

## 1. Core method

### 1.1 Topic and Research Agenda first

默认研究顺序：

```text
研究课题与最终要回答的判断
  -> Research Agenda（事实/因果/市场/载体/定价/风险/前瞻问题）
  -> 有界搜索与正反质证
  -> 本轮已回答 / 部分回答 / 争议 / 未回答
  -> 新盲点与新问题
  -> 重排下一轮研究优先级
  -> 价值转移路径 -> 经济暴露池 × 市场交易池 -> 分时间视野的具体证券比较
  -> 事件/产业情景与条件性建议
  -> Deep Research Report
```

不得从主题直接跳到正式候选，也不得先强造“大胆假说”再让整个研究围着它运行。
假说只在不确定机制需要对照检验时使用；没有假说花园不等于没有研究或机会。

### 1.2 Every round must advance the topic

每轮必须同时交付：

- 哪些待回答问题获得了什么答案；
- 当前研究方向/待质证论点是被支持、被挑战还是仍未决；
- 该方向足以回答、值得续挖，还是由反证/盲点产生了一个可判别的新观点；
- 答案的证据边界与最强反证；
- 仍缺哪一项关键事实；
- 新出现的盲点及其潜在影响；
- 由答案或盲点产生的下一问题。

新盲点可以改变下一轮优先级，但不能仅凭叙述改变正式 crux 信号、候选晋级或外部动作。

对显式 Research Agenda 的新运行，Agenda 是控制平面：只调度 `OPEN / PARTIAL /
DISPUTED` 问题，过滤 `ANSWERED`，并按“阻塞当前建议 -> 决策影响 -> 新盲点/新观点 ->
不确定性 -> 研究成本”排序。研究方向必须链接回原始问题；crux 是其中需要对称质证的
承重方向，可以改变论点判断和下一轮注意力，但不能覆盖 Agenda、阻止报告或变成晋级权限。
正式证据先进入统一 `evidence_items`，普通事实无需借 crux 才获得可引用身份。
共享确定性内核只统一证据、答案合并、标的身份和 setup 完整性；它不拥有轮次、调度、授权
或生命周期。实现与 P1 收益目标见 `docs/research-kernel-v0.15.md`。

### 1.3 Market mechanics is mandatory

机会问题必须分析：

```text
现实事件 -> 市场叙事 -> 预期变化 -> 增量资金 -> 可用证券载体
        -> 辨识度/流动性 -> 筹码拥挤 -> 事件兑现 -> 二次分化
```

技术成功、题材上涨和公司利润兑现是三件事。一个标的可以是高事件弹性、低经济确定性，
也可以是低短线弹性、高产业承接。

不得把“属于某产业概念”当成映射。先建立最短 `ValueTransferPath`：事实变化、约束变化、
利润池转移、兑现时间和证伪；再分别建立经济暴露池和市场实际交易池。每个候选必须说明
资金为什么选择它、当前价格反映什么、为什么此时优于最接近替代标的，以及何时切换。

市场阶段按 `EVENT_DAYS / TACTICAL_WEEKS / EARNINGS_QUARTERS / STRUCTURAL_YEARS`
分别解释；它是带 as-of 的报告投影，不是固定天数推进的状态机。产业时钟（验证、订单、收入、
利润、现金）和市场时钟（预期、载体、扩散、验证、重置）必须分开。

### 1.4 Concrete candidate rule

- Hypothesis 可以实体无关，但永远不能自动变成 OpportunitySeed。
- OpportunitySeed 必须是具体公司、资产、商品或技术；上市证券必须同时有公司名和 ticker。
- 抽象句子、产业环节、筹码机制和“若……则……”命题不是候选。
- 没有具体证券时保留假说，并说明搜索覆盖或“无上市载体”；不得伪造实体。

### 1.5 Two kinds of setup

- `EVENT_SETUP`：主题辨识度、载体稀缺性、流动性、相对强弱、筹码和事件窗口；
- `ECONOMIC_SETUP`：客户、订单、收入、利润、产能和定价传导。

研究注意力排序和条件性 setup 建议允许出现在 Deep Research Report 中，但必须同时给出
触发条件、失效条件、拥挤风险和证据边界。报告可以明确“优先关注/继续观察/当前回避”，
但不能自动生成订单、仓位、目标收益或外部执行。

`SETUP_READY` 只表示字段和字段证据完整，不表示产业吸引力、市场强势或推荐顺位。只有
Market Bridge 同时具备价值路径、时间视野、市场快照、有效替代比较、当前优先理由和切换条件，
才能形成分视野条件性优先项；`WATCH_ONLY / FAILURE_HEDGE` 永远不能因字段齐全变成推荐。

### 1.6 Evidence labels, not early suppression

正文可使用四档：

- `FACT`：来源直接支持；
- `SINGLE_SOURCE`：真实单一来源，尚未交叉验证；
- `INFERENCE`：从事实推导，来源不直接陈述；
- `HYPOTHESIS`：尚未验证的机制、映射或线索，待最低成本验证。

证据较弱不是违规，去掉标签把假说写成事实才是违规。数字必须带具体 URL、来源和日期；
重复 URL + claim + number 不得重复计算。

## 2. Agent roles

- **Framer**：把课题变成研究目标、4—8 个待回答问题、搜索路线与承重研究方向；新运行
  默认不要求 crux/logic graph，旧 crux 只由兼容审计适配器内部承载。
- **Detective**：推进 Research Agenda，搜索事实与产业机制，把路径落到市场与具体证券。
- **Inquisitor**：质证当前答案、提出替代解释，并发现足以改变结论的新盲点与替代标的。
- **Judge / evidence audit**：只核对结构化证据和事实边界；不得决定一个探索假说是否值得存在。
- **Parent**：综合逐题答案、市场运行逻辑、候选比较、新盲点和证据边界，输出完整报告与建议。

Detective 与 Inquisitor 在宿主支持时使用隔离上下文；不能验证隔离时标记
`unverified` 或 `degraded`。隔离是工程保证，不是用户价值或 Alpha 证据。

## 3. Modes

### Standard Q&A

直接回答问题，必要时浏览当前资料。明确事实截止日、关键假设和不确定性。不要为了
普通问题启动完整状态机。

### Mode C: `-scan` — Experimental Macro Radar

只读取当前雷达配置。现有脚本不是完整证券扫描器，不得把输出包装成全市场排序。

### Mode D: `-calibrate` — Historical Audit

核对历史断言；只有用户明确要求持久化时才写 Evolution。校准研究方法，不自动创建
新研究、候选或任何交易状态。

### Mode E: `-premortem` — Symmetric Pre-mortem

构造 `BULL_SURPRISE / BASE / BEAR_FAILURE`，列触发、传导、监控和失效条件。不得预设
目标价、暴跌幅度或伪概率。

### Mode F: `-deepthink2` — Agenda-Native Adversarial Research (v0.15.0, recommended)

`-deepthink2` 是 topic-led 的深度研究入口。当前 Python v2 运行时提供 Research Agenda、
有界调度、逐轮问答/盲点账本、引用账本、市场映射、恢复和报告数据；旧 CandidateScreen、
claim promotion 和下游 handoff 不属于默认流程。

在任何模型研究开始前，先确定且只选择一种执行模式：

- `ORCHESTRATED_VERIFIED`：当前 method identity、注册 run、state，以及每轮三角色的
  prompt/payload/宿主收据全部匹配；只有此模式可以声称“完成 N 轮”和“角色隔离”；
- `STATE_ONLY_UNVERIFIED`：state 中有提交记录，但收据缺失/不完整，或没有可验证的注册 run；
  只能称“未验证状态更新”，不得称研究轮次；
- `HISTORICAL_REPLAY`：state 的 method identity 与当前方法不同；只能称历史回放，禁止写成
  “使用最新 skill 重跑”；
- `INLINE_DEGRADED_RESEARCH`：宿主能力不足时由当前模型直接研究；不创建/借用 run_id，不模仿
  Detective/Inquisitor/Judge，不使用 Round/第 N 轮叙事，并在报告中嵌入：

```bash
python3 scripts/execution_integrity.py inline-marker --topic "TARGET" --as-of YYYY-MM-DD
```

执行模式是结果真实性标签，不是新状态机。不得把失败的注册 run 与随后内联撰写的报告拼成
一次完成运行；失败 run 保持暂停，内联研究是独立结果。

执行原则：

1. 先通过执行网关完成 runtime/host capability preflight；不得因为本机存在 `claude` 就默认
   选择 Claude Code，也不得在 preflight 失败前创建 run。Framer 再内联建立 Research Agenda；
   假说花园可选，只有显式完整 Landscape 才要求 5—7 条路径。
2. Detective 与 Inquisitor 每轮必须推进待回答问题，并分别提供证据、反证、新盲点和下一问。
   每个模型调用必须收到物理嵌入的完整 `WORK WINDOW` 与角色/protocol 正文；只在 prompt 中
   引用一个隔离进程看不到的文件名，不算交付上下文。
3. 引擎保留答案变体并标记 `OPEN / PARTIAL / ANSWERED / DISPUTED`，再重排下一轮问题。
4. 两个研究角色同时形成 ValueTransferPath、市场阶段、经济暴露池和市场交易池，并对候选与
   最近替代项作横向比较；发现机会不以正式晋级证明为前提。
5. Judge 只处理正式 crux 证据；Agenda 答案、探索假说和 CandidateMap 不参与支持度评分。
6. 新运行的停止条件是当前用户问题是否可回答、是否仍有低成本高影响盲点；crux
   convergence、`MIN_ROUNDS` 和 dry rounds 只保留为兼容审计，不得阻止交付。
7. 每轮结束保留新事实、反证、候选、盲点和负知识；新 URL 本身不等于决策推进。
8. 无论当前问题已可回答、授权预算耗尽或用户停止，都输出 Deep Research Report；未决项
   进入正文而非隐藏。预算耗尽时只建议续研，等待用户显式授权。
9. 报告可以给出条件性建议，但到此结束；不得自动进入交易或其他下游生命周期。

支持且已显式配置 Antigravity / Claude Code 时使用注册运行器；先预检，再启动：

```bash
python3 scripts/deepthink_host_runner.py preflight --runtime antigravity
python3 scripts/deepthink_host_runner.py start --topic "TARGET" \
  --frame-json '<framer_output>' --run-purpose PRODUCTION_RESEARCH \
  --runtime antigravity --round-budget 1
python3 scripts/deepthink_host_runner.py resume --run-id "RUN-..." \
  --runtime antigravity --round-budget 9 --stop-after-dry-rounds 3
python3 scripts/deepthink_host_runner.py status --run-id "RUN-..."
```

Codex collaboration 宿主使用注册的手动提交链。先创建 run 并用 `--run-id` 初始化；把初始化
返回的三个完整 prompt 原样交给三个不同的独立 agent。Judge 必须看到密封的 Detective 与
Inquisitor JSON；必须用确定性工具生成 Judge 的最终 prompt，不要手工拼接。保存 dispatch 与
三份 payload 后生成收据，再提交（init envelope 的 `artifact_paths.result_path` 即 dispatch）：

```bash
python3 scripts/deepthink_orchestrator_v2.py --create-run --topic "TARGET" \
  --run-purpose PRODUCTION_RESEARCH
python3 scripts/deepthink_orchestrator_v2.py --init --run-id "RUN-..." \
  --frame-json frame.json --round-budget 1
python3 scripts/execution_integrity.py seal-judge-prompt --dispatch dispatch.json \
  --detective detective.json --inquisitor inquisitor.json --output judge-prompt.txt
python3 scripts/codex_deepthink_round_receipt.py --round 1 --dispatch dispatch.json \
  --detective detective.json --inquisitor inquisitor.json --judge judge.json \
  --detective-agent-id "/root/detective" --inquisitor-agent-id "/root/inquisitor" \
  --judge-agent-id "/root/judge" --output round-1-receipt.json
python3 scripts/deepthink_orchestrator_v2.py --submit --run-id "RUN-..." \
  --det detective.json --inq inquisitor.json --judge judge.json \
  --round-receipt round-1-receipt.json
python3 scripts/deepthink_orchestrator_v2.py --report --run-id "RUN-..."
```

默认一轮预算是安全边界。继续研究需要用户授权额外预算；429、超时、无效 JSON 或单侧
失败必须保留收据和成功载荷，不得自动重试。

每次注册运行交付时必须消费 `stage_envelope.artifact_paths.report_path` 与证据附录路径；不得只在
聊天中另写一份无法回指 state 的“最终报告”。用同一 state 运行：

```bash
python3 scripts/validate_report_v2.py --report REPORT.md --state STATE.json
python3 scripts/execution_integrity.py inspect --state STATE.json
```

若校验结果不是 `ORCHESTRATED_VERIFIED`，报告必须使用对应降级/历史标签；不得人工改写 marker。

## 4. Deep Research Report contract

正文优先级固定为：

1. 核心结论与明确的条件性建议；
2. 研究课题、Research Agenda 和总体进展；
3. 已回答问题、最强质证、尚缺信息；
4. 研究方向的支持/挑战/未决判断，以及由质证产生的新观点；
5. 产业价值如何转移、市场在各时间视野如何运行；
6. 经济暴露池 × 市场交易池、替代比较与条件性优先级；
7. 短线事件 setup 与产业链兑现 setup；
8. 新盲点、二阶影响与前瞻推演；
9. bull/base/bear 或事件树、触发、失效与筹码风险；
10. 未回答问题、活跃方向和下一轮最低成本验证；
10. 事实、单一来源、推断、假说与方法限制。

执行模式、状态字段、来源计数和隔离收据只能进入附录；只有完整执行收据允许使用“研究轮次”。
`FORMAL` 只描述旧证据流程完整，
不能作为机会发现成功的徽章。零候选只有在完成具体证券、替代、价格和筹码搜索后才是
有效研究结论。

完整基准见 `docs/topic-led-research-product.md`。操作 OpportunitySeed 时读
`references/opportunity-protocol.md`；生成报告时读 `references/report-contract.md`；
研究产业到市场映射时读 `references/market-bridge-contract.md`；采集公开或已配置市场数据时读
`references/data-sources.md`。A 股行情只做课题所需候选和基准的有界采集：用兼容命名的
`scripts/free_market_observations.py` 显式选择 Tushare Pro、BaoStock、AKShare 腾讯或 CSV，
再用 `scripts/market_snapshot_adapter.py` 生成带内容回执的可回放相对强弱快照。只有宿主通过
`--ingest-market-snapshot` 把完整 adapter 产物写入当前 run 后，它才进入推荐可信数据平面；
模型载荷里的自报行情只保留为上下文。Tushare token 只能存在于宿主父进程环境，不能进入角色
prompt、state、回执、报告或 Skill 安装目录。不要默认加载未被当前任务使用的旧协议。

## 5. Guardrails

1. 支持度和工作流分数不是概率、收益、目标价或仓位输入。
2. 没有具体 URL、来源和日期的数字不得写成事实。
3. Hypothesis、Observation、Candidate 和 Setup 必须物理区分。
4. 抽象 hypothesis 永远不得自动晋升为 OpportunitySeed。
5. 上市证券候选没有 ticker 时不得进入 seed 或验证队列。
6. `NO_EDGE`、`NO_USABLE_SETUP`、`AVOID` 和 `SHORT` 不得互相替代。
7. 研究枯竭只表示当前搜索没有新增，不证明市场没有机会。
8. 条件性排序必须展示触发、失效、拥挤和替代解释。
9. 不得强制凑股票；无上市载体必须给出搜索边界。
10. 报告必须产出，未完成部分用标签表达，不得因不完美而隐藏探索价值。
11. 任何新研究预算、外部写入或副作用必须遵守宿主授权边界。
12. 假说是可选工具，不得成为所有课题的强制入口或收敛前提。
13. 每轮新盲点必须说明对结论或建议的潜在影响，不能变成无边界发散。
    新问题必须有父问题、决策变化和有界成功条件；续研由剩余信息价值驱动，而不是对象数量。
14. Skill 到 Deep Research Report 与建议为止，不创建或管理任何下游业务流程。
15. 不得用一个全局股票排序覆盖事件、战术、财报和长期产业四种时间视野；不得用字段完整度
    或工作流状态替代“为什么是它、为什么是现在、为什么不是替代项”的横向判断。
16. 条件性优先建议必须同时依赖非 `HYPOTHESIS` 的价值路径、双角色同阶段读数，以及带上游
    采集回执、相对强弱和成交/换手维度的宿主快照；任一缺失都只能保留研究优先级。

## 6. Engineering verification

```bash
python3 scripts/version.py
python3 scripts/benchmark_current.py --check --source-repo .
make test
```

工程通过只证明合同与回归门工作，不证明机会召回率、Alpha、收益或风险调整收益。
产品有效性必须用真实主题回放和人工盲评验证。

---

*Trade Nothing v0.15.0 — Hunt Alpha, Not Consensus.*
*Product target: topic-led iterative research, forward-looking report and advice as the boundary.*
