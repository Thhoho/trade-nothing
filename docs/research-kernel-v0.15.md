# Trade Nothing 研究内核：P0 修复与 P1 收益目标

> 日期：2026-08-10
> 状态：P0 已实现，P1 仅冻结目标与验收口径
> 边界：这是跨投影共享的确定性约束，不是新的状态机

## 1. 为什么需要一个小内核

Research Agenda 和 CandidateMap 面向不同用户问题，但不能各自发明“证据有效”“答案完成”
和“条件完整”的含义。此前真正危险的不是少一个状态，而是同一事实在不同模块中可能得到
不同待遇：未来日期可被接受，代理写的来源标签可制造发布方多样性，无证据的 `ANSWERED`
可结束研究，具名候选只要字段非空就可成为 `SETUP_READY`。

`scripts/research_kernel.py` 只统一四组不变量：

1. 证据日期、URL 身份、去重和发布方边界；
2. 多角色、多轮答案与研究方向的确定性合并；
3. 上市标的的 `exchange + ticker` 身份；
4. EVENT/ECONOMIC setup 的字段内容、字段证据、事件窗口和冲突检查。

它不拥有轮次、预算、调度、授权、报告时点、候选晋级或外部动作。Agenda 和 CandidateMap
仍是面向产品的投影，旧 crux 仍是兼容审计副轨。

## 2. P0：已经修复的真实错误

### 2.1 证据不再由代理自证

- 日期必须是 ISO `YYYY-MM-DD`，且不得晚于运行的 `as_of_date`；
- 证据按规范化 URL、claim、number 去重，换 `evidence_id` 或来源名称不能复制事实；
- 发布方身份由 URL host 推导，代理填写两个 `source` 名称不能把一个网站变成两家来源；
- 重复证据保留 alias 审计，但 Agenda 只存一份 canonical evidence。

直接收益：减少未来信息污染、重复证据膨胀和伪交叉验证。

### 2.2 答案不再由最后写入者决定

- `ANSWERED` 没有有效证据时自动降为 `PARTIAL / HYPOTHESIS`；
- 所有历史答案变体按证据边界确定性合并，不依赖 Detective/Inquisitor 写入顺序；
- 同等级的完成答案与实质质疑保留为 `DISPUTED`；
- 低证据等级的新质疑不能抹掉更强的既有答案，但会保留在 `strongest_challenge`；
- 研究方向的 `SUPPORTED / CHALLENGED` 同样按证据等级合并，同等级冲突保持
  `UNRESOLVED`。

直接收益：减少假完成、静默覆盖和“先后顺序决定结论”。

### 2.3 具名标的和 setup 不再是假身份、假完整

- `LISTED_EQUITY` 必须有真实 ticker；`UNKNOWN / TBD` 会被拒绝；
- A 股代码可确定性推导交易所，其他代码必须显式提供 exchange；
- `SETUP_READY` 不再只看字符串非空。每一种 setup 都要求关键字段有自己绑定的证据；
- 关键字段的自然补充使用 `REFINE`，纠错覆盖使用 `REPLACE`；只有角色显式声明互斥且未裁决
  的 `CHALLENGE` 才形成字段冲突并保持 `EXPLORE`；
- catalyst window 必须有未过期的 ISO 日期；
- `NO_USABLE_SETUP` 必须为四个覆盖维度各保存实际 query、检查过的具体 URL 和 outcome，
  并覆盖经济链、市场载体、竞争替代、失败分支和资本关系五种候选构造路径；
  `INSUFFICIENT` 不得算完成。
- 同题重跑可携带最多 8 条带 URL/日期的既有关键发现作为检索线索；本轮证据必须逐条处置，
  旧结论不得静默消失，也不得直接继承为事实。
  勾选框和一句说明不能证明“已经搜完”。

直接收益：减少伪具名候选、伪 setup 和没有搜索轨迹的负结论。

### 2.4 模型调用不再依赖不可见的文件名

- 每次 Framer、Detective、Inquisitor、Judge、CandidateScreen 和 Claim Verifier 调用都收到
  完整 `WORK WINDOW`：阶段、角色、目标、权威输入、输出产物、禁止事项、完成条件、下一消费者；
- 角色文件与 protocol 正文被物理嵌入 prompt，隔离工作目录中不存在的 `detective.md` 不再被
  当作已经交付的上下文；
- prompt hash 和隔离 receipt 绑定模型实际看到的完整契约。

直接收益：减少 schema 漂移、任务串台、可选副轨挤占主任务，以及“模型没听懂”掩盖接口缺失。

### 2.5 运行结果不再由报告作者自证

- `scripts/execution_integrity.py` 只管理执行声明，不参与 Agenda 状态、轮次调度或研究判断；
- 每个可声明轮次绑定 Detective、Inquisitor、Judge 三个独立宿主身份，以及各自完整 prompt
  和 payload hash；缺失或篡改时，本轮在写 state 前被拒绝，或以 state-only 更新降级保存；
- host runner 的 `auto` 不再扫描本机 CLI 或继承父进程品牌来猜 provider；显式选择和可执行文件
  预检发生在创建 run 之前；
- manifest 顶层 `status` 始终镜像最近持久化 envelope，不再永久停在 `active`；
- 报告嵌入确定性 execution-integrity marker。轮次、当前方法运行、隔离和历史回放声明由 state、
  收据、method identity 与 manifest 绑定共同导出，模型不能自行填写；
- 运行失败后的内联研究必须使用独立的 `INLINE_DEGRADED_RESEARCH` 结果，不得借用失败 run_id。

直接收益：阻止“口述三轮”、旧 state 冒充新方法重跑、失败 run 与手工报告拼接，以及 Codex
误调用本机 Claude 形成的伪多智能体运行。

## 3. P0 验收口径

以下是确定性合同，不是效果宣传：

- 同一证据 tuple 在统一账本中只存一次；
- 非 ISO 或晚于 as-of 的证据接受数为 0；
- 角色输入顺序反转后，答案和方向合并结果相同；
- 无证据 `ANSWERED` 的可用答案数为 0，但报告仍可交付；
- `UNKNOWN` 上市 ticker 接受数为 0；
- 未绑定关键字段证据、事件窗口无效或字段冲突时，setup-ready 数为 0；
- 没有四个可检查搜索字段或五种候选构造 route kind 时，`NO_USABLE_SETUP` 数为 0；
- 全部现有离线安全门与历史兼容回放继续通过。
- 没有完整三角色收据时，可声明完成轮次数为 0；method drift 时当前方法运行声明为 false；
- runtime preflight 失败时不创建新 manifest；暂停/报告状态必须出现在 manifest 顶层；
- `INLINE_DEGRADED_RESEARCH` 中 Round/第 N 轮声明和隔离声明通过报告校验的数量为 0。

这些指标只证明错误被物理阻断，不证明机会召回、Alpha 或投资收益提高。

## 4. P1：把产业判断变成可解释的市场选择

P1 不新增状态、生命周期、审批或第二套 orchestration。它在现有 Agenda 与 CandidateMap
之间增加一个 Market Bridge 投影，解决“有产业结论、有候选名单，但无法回答为什么是它、
为什么是现在”的产品断点。效率优化退居次要目标，不能替代建议价值。

### 4.1 ValueTransferPath：先解释利润池如何移动

已实现：每条承重产业结论可以提交最短价值路径，绑定 Research Question/Direction 和统一
`evidence_id`，明确事实变化、约束变化、利润池转移、兑现视野与证伪。缺证据的路径保留为
`HYPOTHESIS`，不能借产业叙事自证；只有类别词而与具体机制/利润池文本不对齐的证据同样不能
把路径升级为 grounded。

预期收益：候选不再只靠自由文本声称“受益”；报告可以追溯某公司究竟承接哪个增量、通过
订单/收入/利润/现金的哪一步兑现。

### 4.2 双股票池：经济暴露与市场选择分别建立

已实现：Candidate BridgeView 分别记录有字段证据的经济暴露强度和带 as-of、基准、相对强弱
及成交指标的市场确认。二者只投影为 `CONFIRMED_LEADER / LATENT_ECONOMIC / EVENT_BETA /
LOW_PRIORITY / UNRESOLVED`，不合成为综合分、概率或收益预测。

预期收益：区分“真正赚到产业钱”“市场当前把它当载体”“概念强但经济弱”和“经济强但尚未
被市场确认”，避免用概念归属代替公司映射。

### 4.3 市场时间结构与横向选择

已实现：市场阶段按 `EVENT_DAYS / TACTICAL_WEEKS / EARNINGS_QUARTERS /
STRUCTURAL_YEARS` 分开解释，保留角色间阶段争议，不用固定天数推进。每个条件性优先项必须
给出最近替代标的、当前优先理由和切换条件；`WATCH_ONLY / FAILURE_HEDGE` 不能因字段齐全
获得推荐权。报告不再把 `SETUP_READY` 自动写成推荐。

预期收益：同一标的可以在短线拥挤但长期产业占优，不再由一个全局顺序覆盖不同时间视野；
用户能看到为什么选 A 而不是 B，以及什么事实会改变选择。

### 4.4 冻结市场快照，不伪装通用数据库

已实现三段窄链路：兼容命名的 `scripts/free_market_observations.py` 从显式选择的 Tushare、
BaoStock、AKShare 腾讯或带来源 URL 的 CSV 获取单一 A 股候选与基准，冻结请求、交易日、
provider version 与序列哈希；`scripts/market_snapshot_adapter.py` 校验上游回执后，确定性计算
5/20/60 日收益、超额收益、60 日回撤、20 日量比和当前换手，并把规范化结果也写入内容哈希；
最后由宿主用 `--ingest-market-snapshot` 把完整 artifact 写入注册 run 的可信数据平面。三段都
不猜市场日历，不自动降级，也不把旧快照或模型自报快照称为当前。

推荐权限额外要求非假说价值路径、双角色同阶段读数、完整双池，以及同时包含相对强弱和市场
活跃度的宿主快照。估值字段本身不能证明市场选择，单角色意见也不能叫共识。

仍待完成的数据能力：稳定的概念/行业横截面发现、免费源之间的显式对账，以及 H/美股连接器。
没有可靠来源时保留 `UNKNOWN`，但产业优先级与市场确认条件仍应分开交付。

### 4.5 用真实课题评价建议是否更有用

继续用至少 5 个不同类型的真实课题做固定 as-of 回放。盲评新增硬问题：是否形成经济暴露池
与市场交易池，是否解释最近替代项，是否按时间视野给出不同建议，是否避免完整但无吸引力的
候选被自动推荐。

P1 只有在具名具体性、横向解释力和建议可用性改善，同时证据诚实度不退化时才算有效；
工程测试、token 下降或候选数量增加都不能单独宣称产品提升。

## 5. P1 明确不做什么

- 不重新设计 Research Agenda、crux 或 CandidateMap 状态；
- 不引入 Thesis、Decision、CandidateScreen 晋级、订单、仓位或执行；
- 不增加综合分、伪概率或用规则替代研究判断；
- 不为了减少 token 删除挑战、未知项、来源 URL 或报告中的条件/失效信息；
- 不把固定 fixture、测试通过或旧 benchmark 当成真实效果验证。

P1 的设计评审只问三个问题：是否减少错误判断，是否减少无效研究成本，是否让用户更容易
据报告采取下一项研究动作。回答不了其中至少一个的问题，不进入实现。
