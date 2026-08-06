# Trade Nothing

<p align="center">
  <img src="assets/images/hero_banner.jpg" alt="Trade Nothing——越过共识寻找现实" width="900" />
</p>

<p align="center"><strong>大胆猜想，沿迹求证，只让经得起证据的东西晋级。</strong></p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="SKILL.md">运行契约</a> ·
  <a href="docs/release-v0.13.1.md">v0.13.1 发布说明</a> ·
  <a href="docs/hypothesis-led-research-v0.10.md">v0.10 基础设计</a>
</p>

Trade Nothing 是一套面向 Agent Runtime 的对抗式投资研究 Skill。它不是证否机器，也
不是故事生成器：大胆、非共识的猜想可以先进入不可晋级的探索账本，再沿可观察代理
线索、替代解释和证伪条件“草蛇灰线”地求证；正式结论则始终受确定性证据闸门和人工
复核约束。

目标不是追求最低风险，而是更积极地寻找收益风险不对称的机会，同时让下行摩擦、
失效条件、证据缺口以及市场已经支付的价格无处隐藏。

它是研究工作流，不是自动交易系统。它不会自动给出买卖指令、目标价、预期收益、
Kelly 仓位或持仓比例。

## v0.13.1：假说驱动、时间有界的研究

> **想象负责提出，证据负责晋级，风险控制决定能否执行。**

```mermaid
flowchart LR
    A["研究意图"] --> B["探索轨<br/>假说花园 → WildHypothesis → ProxyTrail"]
    A --> C["正式轨<br/>Crux → 已接纳证据 → 根命题结论"]
    B -. "新 Seed 必须重新通过证据准入" .-> D["OpportunitySeed"]
    C --> D
    D --> E["CandidateScreen → 快照绑定核验 → 人工复核"]
    B --> F["一个有界探索动作<br/>设计 → 计划 → 明确授权 → 回执"]
    F -. "不能晋级、定仓或交易" .-> B
```

两条轨道有意保持不对称：大胆假说可以在尚无引用时被记录，但不能改变 crux 支持度、
根命题结论、CandidateScreen、Thesis、Decision、订单或持仓。它若要进入正式轨，
必须新建 `OpportunitySeed`，并独立通过同一 Agent、同一轮次、同一 crux 的既有
证据准入闸门。

v0.13.1 保留 v0.10 的假说驱动基础，并把时间、研究预算分配和面向人的报告输出升级为
显式契约。当前方法包括：

- **时间语义失败关闭。** `as_of_date` 是证据截止日，`horizon` 是相对决策窗口，
  `forecast_target_date` 是可选的精确未来目标；未来目标绝不能伪装成证据覆盖日期。
- **报告拥有锁定事实层。** 每份新 Decision Brief 必须以确定性 Facts Box 开头；
  Evidence Ledger 与 Candidate Cards 独立、按内容寻址保存。自由叙事可以改善可读性，
  但不能改写状态、引用或行动闸门。
- **报告等级与候选晋级解耦。** `FORMAL` 只要求收敛、必要 Landscape 覆盖完成和每条
  crux 具备独立来源。CandidateScreen 只控制具名标的排序，快照 claim 核验只控制候选
  晋级；零候选也是合法的正式研究结果。
- **大胆猜想成为一等研究对象。** `OPPORTUNITY_DISCOVERY` 和 `HYBRID` 先生成
  5–7 条实体无关路径；每个 `WildHypothesis` 都要写清因果链、共识盲区、上行与
  下行机制、催化剂、期限、替代解释和证伪条件。
- **微弱线索变成可审计轨迹。** `ProxyTrail` 把一个可观察线索与方向、因果联系、
  替代解释、来源谱系、有界查询和停止条件绑定起来，不允许从“有意思”直接跳到
  “可投资”。
- **收益风险不对称只调度注意力，不调度资金。** 上行形态、凸性、下行摩擦和
  见到判别信号的时间，可以决定下一步优先研究什么；它们不是概率、预期收益、
  目标价、方向或仓位输入。
- **正式停止不再抹去探索价值。** 每份报告只有一个确定性 `formal_action`，同时
  最多保留一个需要单独授权的 `exploration_action`。后者只能获取信息，不能覆盖
  正式停止或推动候选晋级。
- **证据耗尽也能诚实收敛。** Judge 连续给出零信号不会改变支持度；只有在来源充分、
  多空双方都已探查且有界研究不再产生新证据时，crux 才可能进入 `MONITORABLE`。
  从未探查、只有单边、来源单薄或新引入的 crux 继续失败关闭。

完整说明见 [v0.13.1 发布说明](docs/release-v0.13.1.md)、历史
[v0.10 基础设计](docs/hypothesis-led-research-v0.10.md)、
[假说协议](references/hypothesis-protocol.md)和
[报告契约](references/report-contract.md)。

> [!IMPORTANT]
> **校准状态：** v0.13.1 已实现，并通过确定性工程安全门；但
> `scripts/benchmark_current.py --check` 当前返回 `UNBENCHMARKED_METHOD_CHANGE`。
> 这表示运行方法已不同于最后校准的 v0.9.9 身份。现有 closed-packet 与 discovery
> 套件只是历史控制，不是 v0.13.1 提高机会召回率、线索质量、Alpha、收益率或风险调整
> 收益的证据。工程正确性、研究有效性和投资收益是三层不同结论。

## 现在真正可靠的部分

- Judge 信号必须携带 claim、source、date 和具体文章、公告或 API URL，否则不能
  推动 crux。
- Judge 引用必须能反查到隔离 Agent 的原始 JSON，不能临时编造。
- 同一规范化 URL、claim 和 number 不能重复计分。
- 即使保留了新的审计引用，Judge 零信号也绝不会改变辩论支持度。
- `wild_hypotheses`、`hypothesis_sparks`、`proxy_trails` 和所有
  `HYPOTHESIS_ONLY` 对象，对 Judge 评分、来源计数、收敛和晋级完全不可见。
- `EVIDENCE_BACKED` 仍然只是探索成熟度，不是 `OpportunitySeed`，也不能进入
  CandidateScreen。
- `continue`、`fuse_break`、独立来源不足以及必要 crux 未解决，只会阻断 `FORMAL` 等级，
  不会阻断完整的分级报告包。
- `NO_EDGE` 只表示当前框架和证据下没有建立可用的预期差，不等于 `AVOID` 或
  `SHORT`，也不要求删除一个有界的探索路径。
- 报告数值只是辩论支持度和工作流启发式，不是经过校准的市场概率。
- 探索执行严格遵循“类型化设计 → 计划 → 明确授权 → 回执”：一次精确查询、最多
  三份文档、不得自动重试；状态或 as-of 漂移后不得摄入结果。
- 运行状态写入 `TRADE_NOTHING_SCRATCH_DIR`，不污染 Skill 源码；发布包不包含提醒、
  webhook、投资组合或下单执行入口。

## 隔离是宿主能力，不是 Skill 自带能力

Framer 在父上下文内联运行且不浏览。Detective 和 Inquisitor 必须进入互不共享中间
推理的独立上下文；CandidateScreen 与 claim 核验也有各自的隔离契约。如果宿主只能
让同一个模型切换角色，运行必须标注为 `degraded`，不得声称完成了物理多智能体隔离。

## 安装

### 在 Agent 中用自然语言安装

把下面整段直接发给 Codex、Claude Code、Gemini CLI、Antigravity 或其他编程 Agent：

```text
请为当前 Agent Runtime 安装 Trade Nothing v0.13.1，源码为：
https://github.com/Thhoho/trade-nothing.git

安全与验收要求：
1. 不要启动任何研究 run；本次只授权安装。
2. 先识别当前 Runtime 已配置的 Skill 根目录，并以其中的 `trade-nothing` 为目标。Codex
   使用 `${CODEX_HOME:-$HOME/.codex}/skills/trade-nothing`，Claude Code 使用
   `$HOME/.claude/skills/trade-nothing`，Gemini CLI 使用
   `$HOME/.gemini/skills/trade-nothing`。其他 Runtime 只能使用其文档或配置明确给出的目录；
   无法确认时停止并询问我，不要猜路径。
3. 写入前检查已有源码目录和安装目标。不得 reset、删除或覆盖 dirty checkout、运行状态、
   scratch、个人研究记忆或目标目录元数据。
4. 在新的临时目录或我批准的源码目录 clone/fetch，checkout 精确的 annotated tag
   `v0.13.1`，确认 `git cat-file -t v0.13.1` 输出 `tag`，并报告
   `git rev-parse 'v0.13.1^{commit}'` 解析出的 commit；不得从未打 tag 的分支 tip 安装。
5. 在该 checkout 中运行 `python3 scripts/version.py` 和 `make test`。除非必要检查因缺少
   依赖失败且我明确批准，否则不要安装第三方依赖。
6. 使用 `python3 scripts/install_skill.py --source <checkout> --targets <target>` 安装，
   不要手工复制；然后运行 `python3 scripts/check_source_sync.py --source <checkout>
   --targets <target>`。
7. 保留 `Methodology_Evolution.md`、`scripts/.state`、`.git` 和
   `~/.trade-nothing/` 下的全部内容；旧受控代码交给安装器移入可恢复隔离区。
8. 宿主要求时，网络访问和工作区外写入必须先申请权限。最后报告 tag、commit、安装目标、
   测试结果、同步结果和被隔离文件。
```

这段提示默认只安装到当前 Runtime。若要把同一份已验证 checkout 同步到默认的 Gemini、
Codex 和 Claude 目录，需要明确要求 Agent 运行 `make install DEV_DIR="<checkout>"`，随后
运行 `make status DEV_DIR="<checkout>"`。

### Shell 安装

```bash
git clone --branch v0.13.1 --depth 1 https://github.com/Thhoho/trade-nothing.git
cd trade-nothing
test "$(git cat-file -t v0.13.1)" = tag
git rev-parse 'v0.13.1^{commit}'
python3 scripts/version.py
make test
```

把受控包安装到默认的 Gemini、Codex 和 Claude Skill 目录：

```bash
make install DEV_DIR="$(pwd)"
```

这个命令不会删除运行期 JSON、state、scratch、`.git` 或个人研究文档；已退出源码的
受控代码会被移入可恢复隔离区。Antigravity 与 Claude Code 具备有界进程适配器，Codex
具备手工 collaboration receipt 构造器；Gemini、Hermes 与 OpenHands 在本版本仍是
手工/协议级集成。准确矩阵见 `references/runtime-compatibility.md`。

然后可以直接对 Agent 说：

```text
使用 trade-nothing -deepthink2，以 OPPORTUNITY_DISCOVERY 模式研究：
“未来 3–6 个月，AI 数据中心电力约束可能把价值转移到哪些尚未充分定价的环节？”
```

推荐的 `-deepthink2` 主路径是：

1. 定义有边界、可证伪的问题，并选择 `THESIS_CHALLENGE`、
   `OPPORTUNITY_DISCOVERY` 或 `HYBRID`。
2. 在父上下文内联运行 Framer，初始化确定性状态，再把选中的 OPEN crux 分派给
   隔离的 Detective 与 Inquisitor。
3. Judge 只对带引用的正式证据评分；由引擎而不是 LLM 更新支持度，并决定继续、
   收敛或熔断。
4. 机会研究必须先让有证据的 Seed 成熟并完成 CandidateScreen，再进入快照绑定的
   claim 核验与人工复核。
5. 如有价值，可以设计一个有界探索动作；计划不等于授权，只有用户对精确 action ID
   的明确授权，才允许执行一次查询并提交一次回执。

驱动底层命令前，必须完整阅读 [SKILL.md](SKILL.md)。运行恢复、CandidateScreen、
claim 核验和探索执行的精确 schema 都以其中契约为准。

## 最小手动流程

```bash
# 生成 framing 请求，再由宿主内联执行 agents/framer.md。
python3 scripts/deepthink_orchestrator_v2.py --frame --topic "TARGET"

# 用原样 Framer JSON 初始化。
python3 scripts/deepthink_orchestrator_v2.py --init \
  --topic "TARGET" --frame-json '<framer_json>'

# 提交隔离的 Detective、Inquisitor 与 Judge 载荷。
python3 scripts/deepthink_orchestrator_v2.py --submit \
  --topic "TARGET" --det '<detective_json>' \
  --inq '<inquisitor_json>' --judge '<judge_json>'

# 每个终态都渲染；确定性闸门控制报告等级与允许表达的结论。
python3 scripts/deepthink_orchestrator_v2.py --report --topic "TARGET"
```

报告命令会返回锁定的 `facts_box_markdown`、独立的
`evidence_ledger_markdown`、可选 Candidate Cards 和结构化 view model。新的宿主应把
Facts Box 原样放在内容驱动的 Decision Brief 顶部，并单独保存 Evidence Ledger；
确定性的 `brief` 与 `full` 仅作为兼容回退。

常见终态或续研状态：

- `dispatch_subagents`：只对有界的 OPEN-crux packet 继续质证。
- `ready_for_report`：确定性收敛与证据闸门通过。
- `blocked_max_rounds`：达到熔断轮次，同时交付降级报告与 Resolution Memo。
- `report_data_ready`：报告数据已就绪。它总是产出——限制由 `report_grade` 承载。
- `no_edge`：尚未建立可正式使用的预期差；仍可保留一个明确标注的有界探索动作，
  但必须单独授权。

报告等级与两道硬闸门：

- `report_grade` 为 `FORMAL` / `PROVISIONAL` / `EXPLORATORY`。未满足的闸门降低等级，
  但不再删除研究成果。
- 它只由收敛、必要 Landscape 覆盖和 crux 独立来源决定。CandidateScreen 与 claim 核验
  进入独立的 `candidate_lifecycle`，不会降低报告等级。
- `publication_allowed`（仅 `FORMAL`）：对外传播稿的唯一硬闸门。
- `ranking_allowed`（需完成 CandidateScreen）：对具名标的排序或使用推荐语气的硬闸门，
  且只覆盖 `candidate_lifecycle.rankable_seed_ids`。
- 断言分三档：`VERIFIED` 可直接陈述；`SINGLE_SOURCE` 标注『单一来源·未交叉验证』；
  `HYPOTHESIS` 标注『假说』并允许写进正文。撕掉标签才是违规。

旧的 `-deepthink` 单后验/LFI 流程已于 v0.13.0 退役。它的 LFI/AFI/EGI/后验数值未经校准、
维护独立的 `scripts/.state/` 状态格式，且其 harvest 路径对 `-deepthink2` 的状态会静默失效。
收到 `-deepthink` 请求时改用 `-deepthink2`。

## 正式证据格式

正式引用对象格式如下：

```json
{
  "claim": "来源具体证明了什么",
  "number": "数值或 null",
  "source": "机构名称",
  "url": "https://example.com/specific-page",
  "date": "YYYY-MM-DD",
  "source_tier": "primary"
}
```

裸域名、缺日期、缺来源、超出冻结 as-of 的未来证据，以及 Judge 自行补出的引用都会
被拒绝。

## 环境变量

| 变量 | 默认值 | 用途 |
|---|---|---|
| `TRADE_NOTHING_SKILL_DIR` | 自动识别 | Skill 安装根目录 |
| `TRADE_NOTHING_SCRATCH_DIR` | `~/.trade-nothing/scratch` | 状态与 Issue 文件 |
| `TRADE_NOTHING_OUTPUT_DIR` | `~/trade-nothing-outputs` | 生成物 |
| `TRADE_NOTHING_VAULT_DIR` | `~/trade-nothing-vault` | 研究资料库 |
| `TRADE_NOTHING_EVOLUTION_PATH` | `<vault>/Methodology/Evolution.md` | 负面先验记忆 |
| `TRADE_NOTHING_MODEL_DEEP` | 宿主默认 | 质量关键角色与 Judge |

## 验证、维护与同步

默认本地配置以 `~/Documents/trade-nothing` 为唯一开发源。

```bash
# 当前方法的确定性安全与回归门
make test

# 完整离线单元测试发现
python3 -B -m unittest discover -s scripts -p 'test_*.py'

# 版本与 benchmark 身份检查
python3 scripts/version.py
python3 scripts/benchmark_current.py --check --source-repo .

# 同步受控源码、隔离退役代码，再核对精确哈希
make install DEV_DIR="$(pwd)"
make status DEV_DIR="$(pwd)"
```

已安装包会明确以 package 模式检查 benchmark，并说明无法在包内核验固定 Git 对象；
`--source-repo .` 只应在规范 Git 源仓库中运行。

## 目录结构

```text
agents/       隔离角色契约
scripts/      Orchestrator、确定性引擎、校验器与测试
references/   规范性研究与交接协议
docs/         架构与设计说明
benchmarks/   冻结评估包与方法绑定
assets/       报告模板与 README 插图
legacy/       仅源码保留的 v0.9 执行面和历史设计；不会进入安装包
SKILL.md      Agent 运行时主契约
```

## 许可证

MIT，见 [LICENSE](LICENSE)。
