# Market Bridge Contract

Market Bridge 把产业因果翻译为可交易市场表达。它是 Research Agenda 与 CandidateMap 之间的
投影，不是状态机、候选晋级器或交易决策器。

## 1. 核心判断

产业研究回答“价值最终流向谁”；市场研究回答“当前边际资金通过谁表达哪一项预期变化”。
两者不能用“属于同一概念”代替连接。

```text
事实变化
  -> 约束变化
  -> 利润池转移
  -> 公司经济暴露
  -> 市场已有预期
  -> 可交易载体选择
  -> 边际资金与筹码反馈
  -> 财务兑现或证伪
```

任何条件性优先建议都必须回答：

1. 为什么该公司获得产业增量；
2. 为什么市场会选择该证券表达；
3. 当前价格与预期已经反映什么；
4. 为什么此时优于最接近的替代标的；
5. 什么条件会切换到替代标的或推翻映射。

## 2. ValueTransferPath

每条承重产业结论最多建立一条最短价值转移路径：

```json
{
  "path_key": "VT1",
  "origin_question_ids": ["RQ4"],
  "origin_direction_ids": [],
  "state_change": "可重复使用验证提高潜在发射频次",
  "constraint_change": "发动机周转、检修和高频耗材成为新约束",
  "profit_pool_shift": "价值从单次制造部分转向复用维护与高频供应",
  "economic_winners": ["高频耗材和检修能力拥有者"],
  "economic_losers": ["只受益于一次性整箭制造的环节"],
  "realization_horizon": "EARNINGS_QUARTERS",
  "falsifier": "复飞频率未提高或复用维护成本不降",
  "evidence_ids": ["EV-..."]
}
```

约束：

- 必须链接现有 Research Question；方向链接可选；
- 引用只能指向统一 Agenda evidence；
- 缺证据时可以保留为 `HYPOTHESIS`，但不得写成已确认利润池；只有存在机制类和经济暴露类
  的语义证据锚，路径才获得推荐权限。随手绑定价格或筹码引用不能把产业因果“洗白”；
- `path_key` 只在单角色 payload 内引用，持久化时转换为稳定 `VT-*` ID。

## 3. MarketPhaseSnapshot

市场阶段是报告时点的解释性快照，不控制运行。不同角色可以得出不同阶段，冲突必须保留。

```json
{
  "as_of_date": "YYYY-MM-DD",
  "horizon": "EVENT_DAYS|TACTICAL_WEEKS|EARNINGS_QUARTERS|STRUCTURAL_YEARS",
  "phase": "LATENT|IGNITION|DIFFUSION|VERIFICATION|DIVERGENCE|CROWDING_RESET|UNRESOLVED",
  "dominant_pricing_variable": "当前边际价格主要在交易什么",
  "industry_clock": "产业事实走到验证、订单、收入、利润或现金的哪一步",
  "market_clock": "市场走到预期形成、载体选择、扩散、验证或重置的哪一步",
  "strongest_alternative_phase": "最强替代阶段解释",
  "falsifier": "哪项价格或产业信号会推翻本阶段判断",
  "evidence_ids": ["EV-..."]
}
```

禁止用固定天数自动推进阶段。阶段由事件、相对价格、广度、领涨集中度、成交筹码和财务验证
共同解释。

## 4. 双股票池快照

每个产生横向优先建议的时间视野必须同时具备：

- `ECONOMIC_EXPOSURE`：按公司业务、订单、收入、利润或现金暴露构造；
- `MARKET_TRADING`：按固定概念/行业成分、相对强弱、成交与流动性构造。

两个池都必须冻结 as-of、构造规则、基准、至少两个具名成员以及每个成员的证据 ID。模型随手
挑两只股票互相比，不能证明已经覆盖方向内的强势载体。推荐候选和最近替代项必须出现在同一
时间视野的双池并集中；经济暴露为 LOW 的事件 beta 可以不进入经济暴露池，但必须有公司级
证据支持其低暴露判断。

```json
{
  "universe_type": "ECONOMIC_EXPOSURE|MARKET_TRADING",
  "as_of_date": "YYYY-MM-DD",
  "horizon": "TACTICAL_WEEKS",
  "universe_name": "固定股票池名称",
  "construction_rule": "研究前冻结的有界纳入规则",
  "benchmark": "MARKET_TRADING 必填",
  "evidence_ids": ["EV-..."],
  "members": [
    {
      "candidate": "公司", "ticker": "000000", "exchange": "XSHE",
      "role_in_universe": "纳入原因", "evidence_ids": ["EV-..."]
    }
  ]
}
```

## 5. Candidate BridgeView

候选发现的四个搜索字段只回答“查了什么”，不能证明“候选空间如何构造”。有效的有界负结果
还必须分别覆盖五种 `route_kind`：

- `ECONOMIC_CHAIN`：直接兑现、瓶颈或二阶经济路径；
- `MARKET_CARRIER`：由辨识度、流动性和相对强弱实际承载交易的证券；
- `COMPETITOR_OR_SUBSTITUTE`：竞争技术、替代路线或先例；
- `FAILURE_OR_ADVERSE`：失败受益、逆向暴露或对冲路径；
- `OWNERSHIP_OR_CAPITAL`：股权、资本关系、IPO 或私营主体到上市公司的连接。

每条 route 同时保存搜索字段、`route_kind`、实际 query、具体 URL 和
`FOUND / NO_RESULT / INSUFFICIENT`。`NO_RESULT` 是可审计的负结果；`INSUFFICIENT` 是未完成缺口，
不得帮助形成 `NO_USABLE_SETUP`。这只是报告投影，不新增状态或生命周期。

宿主已有行情观测时，先冻结候选与基准的同一交易日序列。A股结构化或免费源可先运行
`scripts/free_market_observations.py`；它只采集显式选择的单一来源，随后由
`scripts/market_snapshot_adapter.py` 校验采集回执并计算指标：

```json
{
  "as_of_date": "YYYY-MM-DD",
  "candidate": {
    "name": "公司", "ticker": "000000", "exchange": "XSHE",
    "source": "provider", "source_url": "https://...",
    "observations": [
      {"date": "YYYY-MM-DD", "close": 10.0, "volume": 1000000, "turnover_rate": 2.1}
    ]
  },
  "benchmark": {
    "name": "固定行业或宽基基准", "ticker": "INDEX", "exchange": "...",
    "source": "provider", "source_url": "https://...",
    "observations": [{"date": "YYYY-MM-DD", "close": 1000.0}]
  },
  "evidence_ids": ["EV-PRICE", "EV-CROWDING"]
}
```

运行 `scripts/market_snapshot_adapter.py` 后，必须由宿主把**完整 adapter 产物**显式写入
当前注册 run：

```bash
python3 scripts/deepthink_orchestrator_v2.py --ingest-market-snapshot \
  --run-id RUN_ID --market-snapshot market-snapshot.json
```

引擎校验 adapter 内容哈希、完整上游采集回执 envelope 及其 ID、候选身份哈希、交易日、
Research Agenda 中已存在的
证据 ID，并要求至少一个 5/20/60 日超额收益和一个成交量比/换手率维度。价格/预期证据与
成交/拥挤证据必须分别覆盖。候选和基准必须结束在同一观测交易日；不足窗口时对应指标为
null，不得补值。行情源只能支持市场观测，不能证明公司订单、客户、利润或产业暴露。

CandidateMap 继续拥有证券身份、setup 字段和字段证据。Market Bridge 只添加连接信息：

```json
{
  "value_path_refs": ["VT1"],
  "economic_exposure_strength": "HIGH|MEDIUM|LOW|UNKNOWN",
  "economic_rationale": "产业增量对公司整体的重要性和兑现方式",
  "market_recognition": "LEADER|CONFIRMED|EMERGING|WEAK|UNKNOWN",
  "market_selection_rationale": "资金为何把它当成载体",
  "horizon_fit": ["TACTICAL_WEEKS", "EARNINGS_QUARTERS"],
  "trusted_market_snapshot_receipt_id": "宿主上下文给出的 receipt_id；无则留空",
  "closest_alternative": {
    "candidate": "替代公司",
    "ticker": "000000",
    "exchange": "XSHG|XSHE|XBEI|其他明确交易所"
  },
  "why_prefer_now": "当前时点为何优先本候选",
  "switch_condition": "何时应改选替代标的"
}
```

`economic_exposure_strength` 必须同时由该候选自己的 economic exposure 字段证据与非
`HYPOTHESIS` 价值路径支撑；`market_recognition` 必须由宿主已摄入的当前快照支撑。模型
载荷中的 `market_snapshot` 即使字段齐全也只作为审计上下文，不能写入可信数据平面或自证。
价值路径的机制证据必须同时匹配 `state_change / constraint_change` 的类别与文本语义，经济
证据必须同时匹配 `profit_pool_shift`；只有“业务、收入、订单”等泛化词、但与路径正文无语义
重合的证据不能把路径洗成 grounded。该检查是确定性的有界对齐，不冒充来源页面的自然语言蕴含证明。
`LEADER / CONFIRMED / EMERGING` 至少要与一个正的基准超额窗口方向一致；否则即使回执有效也
降为 `UNKNOWN`，避免用负相对强弱讲“强势载体”。
非交易日允许使用研究时点之前三天内的最近观测交易日，但必须显式标记
`latest_observed_session_on_or_before_as_of=true`；更早快照或未确认最近观测日不得形成市场确认。

## 6. 双股票池与条件性建议

Market Bridge 把候选投影为四类，不计算综合分或收益概率：

| 经济暴露 | 市场确认 | 投影 |
|---|---|---|
| HIGH/MEDIUM | LEADER/CONFIRMED | `CONFIRMED_LEADER` |
| HIGH/MEDIUM | EMERGING/WEAK/UNKNOWN | `LATENT_ECONOMIC` |
| LOW | LEADER/CONFIRMED/EMERGING | `EVENT_BETA` |
| LOW | WEAK/UNKNOWN | `LOW_PRIORITY` |

只有同时具备非假说价值路径、时间视野、双角色阶段共识、完整双池、可信市场快照、有效替代
标的、当前优先理由和切换条件时，才能形成横向条件性建议。单角色阶段读数标记为
`SINGLE_VIEW`；两个未绑定有效宿主执行回执的角色槽位标记为 `UNVERIFIED_CONSENSUS`，两者都
不等于可授权共识。`WATCH_ONLY` 与 `FAILURE_HEDGE` 即使字段完整，也只能作为反证或观察样本。
两角色的当前阶段读数都必须绑定非假说证据；无证据的同意不能搭便车形成推荐权。

推荐按时间视野分别输出：

- `EVENT_DAYS`：事件弹性与兑现风险；
- `TACTICAL_WEEKS`：相对强弱、资金扩散与拥挤；
- `EARNINGS_QUARTERS`：订单、收入、利润和现金验证；
- `STRUCTURAL_YEARS`：长期壁垒与利润池归属。

不得把一个全局排序同时用于不同时间视野。

## 7. 负结果

若没有条件性优先项，报告必须指出具体缺在哪一层：

- 没有可验证价值转移路径；
- 有产业暴露但没有市场确认；
- 有市场强势但经济暴露很弱；
- 没有有效替代比较；
- 市场快照缺失或过期；
- 市场快照只有估值、缺相对强弱或成交活跃度；
- 价值路径仍是无证据假说；
- 阶段读数只有单一角色；
- 当前阶段存在实质争议。

“字段未齐”不再等于“没有推荐标的”，字段齐全也不再自动等于“值得推荐”。
