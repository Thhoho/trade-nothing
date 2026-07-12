# Trade Nothing `deepthink2` 输出效果审计与下一轮迭代计划

审计日期：2026-07-12  
当前报告：`power_capacity_infrastructure_analysis.md` / `power_capacity_infrastructure_analysis_zh.md`  
同题旧产物：`framing_gate_report.md`  
旧版完整报告参照：`anthropic_power_to_compute_report.md`

## 一、结论先行

新版有真实进步，但还不能被当成可靠的投资研究系统。

它已经从“冗长、泄露原始代理输出、伪装概率和仓位”的危险旧版，进化为一份短、清晰、像投委会备忘录的产物；然而，**形式可信度提升得比事实可信度快**。本次最关键的空头结论依赖对 FERC 文件的过度解释，时间闸允许已发生事件继续充当未来催化，最终写作层又把 engine 的 `NO_EDGE` 偷换成了 `Short-bias`。

这会制造一种比旧版更隐蔽的风险：旧版一眼就能看出“模型味”和拼接痕迹，新版看起来足够专业，用户反而更容易相信错误结论。

综合评分：

- 同题旧 Framing-only 产物：**2.5/10**，没有完成研究。
- 旧版完整 Anthropic/中国映射报告：**3/10**，信息量大但安全性和事实可靠性很差。
- 当前北美电力报告：**4.5/10**，可读性显著提升，但决策可靠性仍未过线。
- 可进入真实投研工作流的最低目标：**7.5/10**，前提是完成 P0 证据和决策语义修复。

## 二、实际运行状态，而不是成稿给人的印象

从 deterministic state 与正式 renderer 读取到的真实状态：

- 4 轮后收敛，decision=`NO_EDGE / AVOID`。
- 3 条 crux：C1=`RESOLVED_BEAR`，C2/C3=`MONITORABLE`。
- 10 个唯一 URL，但 `n_primary_sources=0`。
- 立题状态为 `PROVISIONAL_UNVERIFIED`。
- 多智能体隔离状态为 `unverified`。
- OpportunitySeed 数量为 **0**，唯一候选数量为 **0**。
- CandidateScreen、snapshot claim verification 均未执行。

当前成稿没有完整披露这些限制，却写出了“建议偏空”。这不是文风问题，而是状态到报告的语义失真。

## 三、相对旧版的真实进步

### 1. 完成度

同题旧产物只停在 Framing Gate；新版完成了 4 轮 Detective / Inquisitor / Judge 循环并得到 engine convergence。这是实质升级。

### 2. 可读性

新版从 200 多行、夹杂 raw agent payload 的拼接报告，缩减为 83 行投资备忘录。执行摘要、三条 crux、价值链和监控锚点都能快速阅读。

### 3. 输出安全

旧版完整报告出现了：

- 把 workflow support 当作概率；
- `Half-Kelly` 仓位；
- 自造四情景收益；
- 把全量 agent 原始输出嵌入报告。

新版基本清除了上述问题，没有暴露 transcript，也没有再给出伪精确收益率。这说明 compact deterministic report 与 raw-output 禁令方向正确。

### 4. 研究聚焦

新版围绕 FERC、PJM 容量市场和核电 COD 三条承重问题展开，明显优于旧版按产业链漫游式堆资料。

## 四、致命缺陷

### P0-1：Citation gate 只验证“像引用”，没有验证“引用支持了什么”

成稿把 FERC 2026-06-18 的 Section 206 show-cause orders 表述为：已经强制终止成本社会化，且 100% 网络升级资本开支直接分配给数据中心。

但 FERC 官方描述是要求六个 RTO/ISO **justify or reform** 现有规则，是程序启动和初步认定，不是已经完成最终费率重构。更直接地，FERC Commissioner See 的同期说明称，当前政策仍将大部分 network-upgrade costs 纳入 transmission customers 的 embedded-cost rate，只是在探索更合适的直接分配和替代方案。

来源：

- [FERC Large Load Show Cause Orders, 2026-06-18](https://www.ferc.gov/news-events/news/ferc-launches-aggressive-targeted-action-speed-large-load-integration)
- [Commissioner See remarks](https://www.ferc.gov/news-events/news/commissioner-sees-remarks-large-load-show-cause-orders-e-7-e-12-june-18-2026-open)

因此，当前 C1 的 `RESOLVED_BEAR` 至少应降级为 `OPEN` 或 `MONITORABLE`。它不是已经验证的“致命一击”。

### P0-2：时间一致性失效

state 中的 P2 与 catalyst 仍把 `PJM 2026/2027 BRA` 当作 2026 年下半年将发生的未来事件；但该拍卖已于 2025-07 完成并在 $329.17/MW-day 的 cap 出清，2027/2028 拍卖也已于 2025-12 完成并在 $333.44/MW-day 出清。

来源：

- [PJM 2025 Annual Report capacity results](https://services.pjm.com/annualreport2025/markets/)
- [PJM 2027/2028 auction result](https://insidelines.pjm.com/pjm-auction-procures-134479-mw-of-generation-resources/)

也就是说，engine 一边引用了历史结果，一边仍把同一事件当未来 falsifier/catalyst。这样的 monitor 不可执行。

### P0-3：NRC 日期与“延期”结论没有被引用支持

报告声称 NRC inspection schedule 延伸至 2027-06-01，并据此判断 COD “实质性推迟”。当前 NRC CCEC 页面没有这个日期；Constellation 在 2024 年初始公告中本来就预计 2028 上线。因此，3–6 个月没有发电现金流是真的，但它并不等于项目最近发生了延期。

来源：

- [NRC Christopher M. Crane Clean Energy Center](https://www.nrc.gov/info-finder/reactors/ccec)
- [Constellation 2024 restart announcement](https://investors.constellationenergy.com/news-releases/news-release-details/constellation-launch-crane-clean-energy-center-restoring-jobs)

这是典型的“结论方向可能合理，证据链却错误”。系统必须拦截，而不是因为结果听起来合理就放行。

### P0-4：`NO_EDGE` 被错误翻译成 `BEAR / SHORT`

`NO_EDGE` 的正确含义是：没有足够经验证的预期差可以进入投资决策。它不等于资产会跌，更不等于存在可做空机会。

当前报告从 `NO_EDGE / AVOID` 跳到了“极不对称下行风险”和“偏空态度”，但 state 中没有 Short OpportunitySeed、没有 CandidateScreen、没有估值和拥挤度证据。最终写作层越权创建了 engine 从未给出的方向性建议。

### P0-5：问题问“是否错价”，crux 却没有价格

三条 crux 都在讨论基本面与制度：监管费率、容量价格、项目时间线。没有一条真正回答：

- CEG/VST/TLN 或相关资产当前估值隐含了什么？
- 市场一致预期是什么？
- 哪个可交付 MW 已经被定价，哪个没有？
- 监管成本变化对应多少现金流、资本回报或融资能力变化？

没有 `mispricing / valuation crux`，系统最多能判断“基本面约束存在”，不能判断“尚未充分定价”。

### P0-6：用 BTM 子路径否定整个基础设施资产宇宙

C1 最多否定 BTM co-location 的部分套利结构，却被用来否定整个“北美可交付电力容量资产机会”。它没有覆盖：

- 已签 FTM 长约的现有发电资产；
- rate-base transmission owners；
- 变压器、开关设备和现场发电；
- 已并网 brownfield sites；
- 受益于 cost-recovery agreement 的资产所有者。

子路径失败不能自动外推成整个候选宇宙 `AVOID`。需要 scope-coverage gate。

### P0-7：形式上的 Evidence PASS 掩盖了 0 个一级来源

正式 renderer 显示 `n_primary_sources=0`，因为所有 citation 的 `source_tier` 都为空。即使 URL 指向 FERC/PJM，engine 也没有形成可审计的一级来源认定。

当前 PASS 只说明 URL、claim、date 等字段齐全，不说明页面存在、精确文本支持 claim、来源层级正确，更不说明数字和引用页面匹配。

### P0-8：隔离状态未验证，却按完整多智能体结果展示

state 中 `isolation_status=unverified`。当前成稿没有披露 degraded/unverified，也没有证明 Detective 与 Inquisitor 物理隔离。Host-enforced isolation 仍只是说明文字，没有成为结果门。

### P0-9：挖宝效果为零

这次 4 轮研究产生 0 个 OpportunitySeed。报告甚至没有诚实地说“没有找到可二次筛选的候选”，反而自行建议对一类模糊的“中小电力开发商”偏空。

对用户的第二个核心目标——从原始想法挖到宝藏——这次运行是失败的。

## 五、当前版与旧版对比

| 维度 | 旧版完整报告 | 当前报告 | 判断 |
|---|---:|---:|---|
| 完整执行 | 3 轮，但控制流与内容混杂 | 4 轮 deterministic convergence | 当前更好 |
| 可读性 | 低，约 250 行且有 raw payload | 高，83 行备忘录 | 当前显著更好 |
| 事实来源 | 大量可疑 URL 与伪精确数字 | 多数 URL 指向真实机构，但语义错配 | 当前略好，仍不过线 |
| 决策诚实 | 概率、R/R、Half-Kelly 越权 | 不再给伪概率，但 `NO_EDGE→Short-bias` 越权 | 当前更好但仍危险 |
| 审计透明 | 原始输出过度暴露 | 关键限制被最终成稿隐藏 | 两者都不合格 |
| 机会挖掘 | 有候选，但证据污染严重 | 0 OpportunitySeed | 当前更差 |
| Token/篇幅 | 浪费严重 | 最终输出紧凑 | 当前更好 |
| 用户误导风险 | 粗糙，容易看出问题 | 专业外观掩盖错误 | 当前可能更隐蔽 |

## 六、新的迭代计划

### Iteration 1 — P0：先让系统不能自信地说错话

#### 1. 把 snapshot verification 前移到 Judge 评分之前

当前 Claim Verifier 位于 CandidateScreen 后，太晚。新增 `EvidenceVerifier`：

1. 抓取 URL 并生成 content hash；
2. 要求 agent 提交支持 claim 的 exact span；
3. 检查 number/date/entity 是否与页面一致；
4. 分类 `SUPPORTS / PARTIAL / CONTRADICTS / NOT_FOUND`；
5. Judge 只能使用 `SUPPORTS` 或受限的 `PARTIAL`。

验收标准：本次 FERC “100% 成本直摊”必须被标为 `CONTRADICTS` 或 `PARTIAL`，C1 不得进入 `RESOLVED_BEAR`。

#### 2. 增加监管动作语义分类器

强制区分：

- `PROPOSAL`
- `SHOW_CAUSE / PRELIMINARY_FINDING`
- `COMPLIANCE_FILING`
- `FINAL_ORDER`
- `EFFECTIVE_TARIFF`

禁止将 show-cause、意见稿、filing deadline 改写成 final decision 或 effective tariff。

验收标准：`2026-08-17` 只能被标记为待核的 filing/response checkpoint，除非 docket snapshot 明确写明 final order date。

#### 3. 增加时间一致性闸

在 `--init` 与每轮 `--submit` 同时校验：

- 已在 `as_of_date` 前完成的事件不得作为 future catalyst；
- source 已给出结果时，相关 crux 必须从“预测事件”改写为“结果解释”；
- monitor date 必须对应尚未发生、可观察的事件；
- 若 agent 引用新事实推翻 framing premise，必须更新 premise status，而不是并存矛盾。

验收标准：2025 年已完成的 PJM 2026/2027、2027/2028 BRA 不得出现在 2026-07 的未来事件表中。

#### 4. 重构最终决策语义

将单字段 verdict 拆为：

```json
{
  "edge_state": "EDGE_FOUND | NO_EDGE | INSUFFICIENT_EVIDENCE",
  "evidence_direction": "BULL | BEAR | MIXED | UNDETERMINED",
  "actionability": "NONE | MONITOR | READY_FOR_SCREENING"
}
```

只有经过独立 Short OpportunitySeed + CandidateScreen，才允许出现 `short`, `做空`, `偏空交易` 等表达。

验收标准：当前 state 最多输出 `NO_EDGE + BEAR_LEANING_EVIDENCE + MONITOR`，不能输出 short recommendation。

#### 5. 强制正式报告只能由 renderer 生成

Narrative enhancer 必须保留以下不可删除区块：

- primary-source count；
- framing provisional status；
- isolation status；
- opportunity count；
- snapshot verification state；
- engine verdict 原文与非交易含义。

增强后的 Markdown 必须再过 `validate_report_v2.py`，并与 state 做字段一致性比较。出现 state 中没有的方向、候选、日期或数字，直接拒绝落盘。

### Iteration 2 — P1：让“找宝藏”成为受控能力，而不是靠文采

#### 1. 强制机会问题包含四类 crux

对于包含“机会、错价、受益、低估”的题目，Framer 至少包含：

1. Physical deliverability；
2. Contract/financing economics；
3. Regulation/cost allocation；
4. Mispricing/valuation/consensus gap。

没有第 4 类，禁止输出 `EDGE_FOUND` 或“已充分定价”。

#### 2. 增加 scope-coverage gate

每个 verdict 必须声明适用范围。例如：

- `BTM co-location arbitrage: NO_EDGE`
- `all North American deliverable-power infrastructure: UNDETERMINED`

单个子路径 crux 不能否定包含多个商业模式的 candidate universe。

#### 3. 增加 deterministic Opportunity Harvest pass

在每条 crux 解决后，仅基于已经验证的证据回答：

- 谁被伤害？
- 谁获得成本回收权？
- 谁拥有不可替代瓶颈？
- 是否存在替代、竞争者、二阶受益者或 short seed？

若 0 seed，报告必须展示“为什么是 0”：没有实体、没有经济暴露、没有催化，还是证据未验证。禁止用模糊行业名替代 seed。

验收标准：当前题至少应明确审计 `TLN/CEG/VST`、regulated transmission owners 与 electrical-equipment bottlenecks；它们可以全部被拒绝，但不能完全不进入候选账本。

### Iteration 3 — P1：把运行时软约束变成物理约束

本次 Codex 侧复跑再次暴露：Framer inline 已修复，但 Detective 超过 8 分钟后，`agy` 父代理不会因为 skill 里写了 timeout 就自动终止。

新增专用 `agy_deepthink2_runner.py`：

- Framer、Detective、Inquisitor、Judge 分别使用独立 CLI subprocess；
- `subprocess.run(..., timeout=N)` 物理终止；
- D/I 并行但分别记时，不被最慢代理无限锁住；
- 每阶段只保存结构化 JSON 与小型 manifest；
- 首次超时立即生成 runtime-failure memo，不自动重试；
- 记录 elapsed time、agent token/cost（若 agy 暴露）和 source delta。

验收标准：模拟 hung Detective 时，480 秒内必须退出并留下可审计 failure receipt，不能等到全局 45 分钟。

### Iteration 4 — P2：建立输出回归基准

把本次报告加入 golden failure fixtures，至少建立以下自动测试：

1. FERC show-cause 不得变成 final cost allocation；
2. 历史 PJM auction 不得成为未来 catalyst；
3. NRC 页面不存在的日期不得进入报告；
4. `NO_EDGE` 不得生成 short recommendation；
5. `n_primary_sources=0` 不得显示 institutional-grade evidence pass；
6. `isolation_status=unverified` 必须出现在成稿；
7. `opportunity_seed_count=0` 必须明确披露；
8. narrative report 的每个数字、日期、候选都必须存在于 verified synthesis packet。

建议长期指标：

- decisive-claim snapshot alignment ≥ 95%；
- resolved crux primary-source coverage = 100%；
- stale/future-event contradiction = 0；
- report/state semantic mismatch = 0；
- raw transcript leakage = 0；
- runtime stage timeout compliance = 100%；
- OpportunitySeed 的 verified-to-screenable 转化率单独统计，不追求强行提高 seed 数量。

## 七、推荐实施顺序

1. **先做 Iteration 1**：证据语义、时间闸、verdict 拆分、report validator。
2. 用当前 state 重放；预期结果应从 `RESOLVED_BEAR / Short-bias` 降级为 `NO_EDGE or INSUFFICIENT_EVIDENCE / MONITOR`。
3. 再做 Iteration 2：补齐 mispricing crux、scope coverage 和机会账本。
4. 再做 Iteration 3：专用 agy runner，解决物理超时和 Token 尾部消耗。
5. 最后跑 10 个固定题目的 benchmark，再决定是否扩展 CandidateScreen 与自动 claim verification。

短期内不要继续优化排版。当前报告已经足够好看，下一美元工程投入必须用于**让错误结论更难通过**。
