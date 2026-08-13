# Trade Nothing

一个以证据和结果为中心的投资研究 Skill：先找全当期重大事实，再按时间视野连接产业经济与
市场运行，最终只形成一份可审计的决策快照。

[English](README.md) · [架构](docs/architecture.md) ·
[v0.18.0 发布说明](docs/release-v0.18.0.md) · [数据源](references/data-sources.md)

## 它解决什么

Trade Nothing 面向公司、事件、产业、主题、A 股、商业航天、AI 产业链和光伏等研究。

产品标准很简单：在同模型、同截止日和可比预算下，使用 Skill 必须比不使用 Skill 找到更多
会改变判断的事实，并形成更有用的答案。角色更多、URL 更多、报告更长，都不等于价值。

v0.18 活跃内核只持久化四个对象：

- `TaskSpec`：到底要回答什么；
- `EvidenceStore`：实际看到了什么、检查了什么；
- `DecisionSnapshot`：唯一面向用户的语义真相；
- `RunLedger`：宿主实际上执行了什么。

只有 Value Lead 能完整替换 DecisionSnapshot。可选子智能体 Challenger 在宿主分配的上下文中攻击
具名承重结论，但不能写结论。确定性代码校验证据覆盖、谱系、追加式迁移、预算和执行
收据；用户版与审计版报告来自同一份已校验 Snapshot。

范围止于深度研究报告和条件性建议，不拥有订单、仓位、组合、目标价、发布或下游 handoff。

## v0.18.0：宿主能力优先，可移植语义内核

v0.18 保留 v0.17 的四对象内核，并移除最后一层运行时错位：在 Codex 中，原生工具和一个
原生子智能体是默认执行路径，外部模型 CLI 只是显式可选的适配器。Agent Loop 仍为：

```text
WorkingSet -> 一个 ActionIntent -> 证据/工具/可选 Challenger
           -> 原子 DecisionSnapshot -> 校验 -> 停止或下一动作
```

真正影响效果的变化包括：

- 先枚举官方公告/状态索引，再做主题搜索；亏损、减值、关联借款、激励、质押、解禁等潜在
  重大标题不能用模板理由在标题层排除；
- 重大标题必须先有宿主提取的正文摘录、定位和绑定 SourceCheck 的文档哈希，再由 Lead 在重大变化、
  开放缺口、非重大处置三者中唯一选择；事件族由主体、事件类型和宿主锚点派生；
- 已提交 Snapshot 只对自己的证据前沿负责；后续宿主或 Challenger 追加只创建待处理义务，
  不再反向判旧 Snapshot 无效或促使脚本代写结论；
- 每个付费研究窗口都必须新增观察，并产生真实语义 Snapshot 变化；
- 每次完整 Snapshot 都必须保留全部 TaskSpec 问题；
- 同一 EvidenceItem 可带多个真实语义角色；“市场正在交易什么”与“哪个标的达到条件性研究结论”
  分离，新的优先标的仍自动继承全部公司现实核验；
- 不透明数值字符串被拒绝；结构化 measure 使用受控指标、明确主体和注册口径，统一管理单位、
  缩放、期间与展示，不能跨事实或跨证券借用数值；
- 最近替代必须是 `UNKNOWN`，或由自身市场证据支持的规范 `ticker@MIC`，不能只是一个自由文本名字；
- 冻结的 Tushare/BaoStock/AKShare/CSV 行情可直接转换成规范宿主输入；
- Codex 默认使用原生子智能体 Challenger；报告区分 `HARNESS_REPORTED`、调用方观察的
  `PROCESS_REPORTED` 和 `UNVERIFIED`，不再统称“已验证”；
- 可选 CLI 适配器不能签发强进程证明；未来只有真正拥有创建、等待和结果捕获的应用宿主才可提供强证明；
- 用户版与审计版报告由同一已校验 run 纯渲染；交付前验证器重算完整 run/RunLedger、状态、方法、
  渲染器与内容绑定；
- 超时、配额、权限和 JSON 错误只记录一次，绝不自动重试；
- 旧引擎不再进入活跃方法身份，也不会被安装到 Agent 的语义路径中。

**校准状态：** v0.18.0 已实现并通过确定性回归门，但仍是
`UNBENCHMARKED_METHOD_CHANGE`。工程正确不等于研究有效，更不等于 Alpha；还需要盲测的
同模型前向对比。

[v0.10 基础设计](docs/hypothesis-led-research-v0.10.md)和后续历史引擎继续保留用于回放与
架构考古，但不再拥有新运行的语义权威。

## 使用

### 普通问答

直接提投资研究问题。需要时核验最新来源，明确截止日和证据边界；简单问题不会创建注册 run。

### `-deepthink2`

明确给出 0–10 轮预算。预算是上限，不是必须跑满的配额；没有能显著改变判断的当前动作就
提前停止。

启动前由父 Agent 在同一工作窗口写明 `primary_entities` 和研究问题；这不是额外 Framer 调用。
深研入口会拒绝只有泛化 topic 的 TaskSpec，防止静默选择错误事实面。

在 Codex 中使用原生 harness 路径：

```bash
python3 scripts/research_loop.py start \
  --topic "你的问题" --task-spec-json task-spec.json --round-budget 3 \
  --execution-mode HARNESS_ORCHESTRATED
```

父 Agent 用原生工具执行返回的 WorkingSet。如果请求 `CHALLENGER`，将该有界提示原样交给
一个 Codex 子智能体，记录 `HARNESS_REPORTED` 收据，提交 JSON，再由父 Lead 处理。按 run ID
查看或继续：

```bash
python3 scripts/research_loop.py status --run-id "RUN-..."
python3 scripts/research_loop.py dispatch --run-id "RUN-..."
python3 scripts/research_loop.py verify-report --run-id "RUN-..." --bundle "/path/report-bundle-....json"
```

精确数据包和收据协议见 [Research Loop 合同](references/research-loop-contract.md)。手工父 Agent
收据只证明 prompt/payload 谱系，仍为 `SELF_DECLARED / UNVERIFIED`。
`research_host_runner.py` 只是用户显式选择外部进程运行时才使用的适配器；Claude CLI 的认证或
权限失败不得阻断 Codex 原生路径。其收据只是 `PROCESS_REPORTED`，不是独立执行强证明；要满足
官方索引或公告正文门，结果仍须由宿主显式摄取。

## 安装

### 在 Agent 中用自然语言安装

只需要这句：

> 从最新、已审阅的 `main` commit 安装或更新 `trade-nothing` Skill；核验 commit 和源码同步。
> 不要启动任何研究 run。

Agent 应在临时目录执行 `git clone --branch main --depth 1`，记录 `git rev-parse HEAD`，再用
`git switch --detach` 固定源码，然后运行：

```bash
python3 <checkout>/scripts/install_skill.py --source <checkout> --targets <target>
```

在开发目录中一次同步 Codex、Claude 和 Gemini：

```bash
make install DEV_DIR="<checkout>"
```

安装只复制活跃白名单文件。目标中的退休受管代码会移动到可恢复隔离目录；运行状态和凭证
不会被触碰。

## 配置 Tushare Pro

只配置宿主环境变量，不需要分别修改几个 Agent 路径：

```bash
launchctl setenv TUSHARE_TOKEN "YOUR_TOKEN"
```

单个终端会话可用 `export TUSHARE_TOKEN="YOUR_TOKEN"`，之后重启相关应用。凭证不会进入角色 prompt、
状态、收据、报告、Git 或已安装 Skill 文件。BaoStock 是免费基线，AKShare 是有界
回退；替换数据源的方法见[数据源合同](references/data-sources.md)。

## 验证

```bash
python3 scripts/test_research_core.py
python3 scripts/test_research_loop.py
python3 scripts/test_current_reality_regression.py
python3 scripts/test_research_host_runner.py
python3 scripts/test_research_market_input.py
python3 scripts/version.py
make test
```

这些测试证明合同和执行行为，不证明市场效果。产品前向门要求：冻结 P0 事实零遗漏、没有伪造质证来源、
没有语义矛盾、五个多样案例中至少四个的决策价值高于基线，成本不超过基线 1.5 倍。

## 每日主题

`make daily` 只生成一份市场观察和一个动态主题/0–10 轮预算建议；不会启动深研、重试、发布、
部署或交易：

```bash
make daily
```

## 许可证

MIT。研究产物不构成投资建议或执行授权。
