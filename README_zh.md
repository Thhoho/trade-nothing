# Trade Nothing

Trade Nothing 是一个用于投资研究的对抗式多智能体 skill，适用于 Codex、Gemini CLI、
Antigravity、Claude Code、OpenHands 等 agent runtime。

它的目标不是生成一份漂亮的买入研报，而是回答一个更窄的问题：

> 市场在哪里自信地错了？证据是否足够支持行动？

当前推荐使用 `-deepthink2`。它会把一个投资问题拆成几个承重 crux，让互相隔离的
多头/空头 agent 分别找证据和攻击，再由 Judge 只按有来源的证据评分，最后由确定性
Python engine 判断是否收敛。

<p align="center">
  <img src="assets/images/philosophy.jpg" alt="Trade Nothing 哲学：共识与现实的错配" width="640" />
</p>

## v0.10.2 改了什么

`-deepthink2` 现在是主路径。

- 用 per-crux 证明账本替代单一总后验。
- 要求证据使用具体原文 URL，不能只挂网站首页。
- 达到最大轮次但未收敛时，禁止生成正式报告。
- 新增 `scripts/validate_report_v2.py`，检查无效引用和未挂引用的数字。
- 保留老 `-deepthink`，用于兼容旧流程和回归对照。

## 该用 `-deepthink` 还是 `-deepthink2`

默认用 `-deepthink2`。

`-deepthink` 是老流程，适合对比旧结果，但它把所有争议压成一个总概率，容易走向极端，
也容易跑满 12 轮。

`-deepthink2` 是新流程：

- 每条关键假设都有自己的概率。
- 已解决的 crux 会退休，后续轮次只打未解决问题。
- 只有 engine 判定收敛，才允许生成正式报告。
- `fuse_break` 代表达到最大轮次，不代表收敛。

<p align="center">
  <img src="assets/images/architecture.jpg" alt="Trade Nothing 对抗式架构" width="680" />
</p>

## 安装

先克隆仓库并安装 Python 依赖：

```bash
git clone https://github.com/Thhoho/trade-nothing.git
cd trade-nothing
python3 -m pip install -r requirements.txt
```

然后把仓库暴露给你的 agent runtime。

### Codex

```bash
mkdir -p ~/.codex/skills
ln -s "$(pwd)" ~/.codex/skills/trade-nothing
```

在 Codex 里使用：

```text
使用 trade-nothing -deepthink2 研究 “未来 3-6 个月 NVDA AI 基础设施是否值得做多”
```

### Claude Code

Claude Code 不一定需要全局 skill registry。最稳的方式是把仓库放到当前项目内，
或者在项目说明里明确指向 `SKILL.md`。

方式 A：放到当前项目：

```bash
mkdir -p tools
git clone https://github.com/Thhoho/trade-nothing.git tools/trade-nothing
```

在项目的 `CLAUDE.md` 里加入：

```md
当我提到 trade-nothing 或 -deepthink2 时，先阅读 tools/trade-nothing/SKILL.md。
按其中的 orchestrator-driven workflow 执行，并使用 tools/trade-nothing/agents/ 下的 agent prompts。
```

方式 B：保留一个共享 clone，让 Claude Code 读取绝对路径：

```md
当我提到 trade-nothing 或 -deepthink2 时，先阅读 /absolute/path/to/trade-nothing/SKILL.md。
```

在 Claude Code 里使用：

```text
读取 /absolute/path/to/trade-nothing/SKILL.md，并用 -deepthink2 研究 “未来 3-6 个月 NVDA AI 基础设施是否值得做多”
```

### Antigravity / Gemini CLI

```bash
mkdir -p ~/.gemini/skills
ln -s "$(pwd)" ~/.gemini/skills/trade-nothing
```

在 Antigravity 或 Gemini CLI 里使用：

```text
使用 trade-nothing -deepthink2 研究 “未来 3-6 个月 NVDA AI 基础设施是否值得做多”
```

如果目标 skill 目录已经存在，把它替换成指向当前仓库的 symlink 即可。

## 最简单的使用方式

在 agent 里直接说：

```text
使用 trade-nothing -deepthink2 研究 “未来 3-6 个月 NVDA AI 基础设施是否值得做多”
```

agent 应该先阅读 `SKILL.md`，然后按 v2 状态机执行：

```bash
python3 scripts/deepthink_orchestrator_v2.py --frame --topic "TARGET"
python3 scripts/deepthink_orchestrator_v2.py --init --topic "TARGET" --frame-json '<framer_json>'
python3 scripts/deepthink_orchestrator_v2.py --submit --topic "TARGET" \
  --det '<detective_json>' --inq '<inquisitor_json>' --judge '<judge_json>'
python3 scripts/deepthink_orchestrator_v2.py --report --topic "TARGET"
```

通常你不需要手动敲这些命令，由 agent 负责调度。

## 报告发布前校验

v2 报告发布前必须跑：

```bash
python3 scripts/validate_report_v2.py \
  --report stock-report.md \
  --state scripts/.state/<topic>_v2_state.json
```

校验器会拦截：

- 引用只是网站首页；
- BATTLE_LOG 还没填；
- 引用了不存在的 `[n]`；
- 报告里出现数字但同一行没有 `[n]` 引用。

这不是吹毛求疵。投资报告宁可阻断，也不能把无来源数字包装成结论。

## v2 流程怎么跑

<p align="center">
  <img src="assets/images/pipeline.jpg" alt="Trade Nothing deepthink 流程" width="720" />
</p>

1. **Framer**：定义决策问题和 2-5 条 crux。
2. **Detective**：寻找最强多头证据。
3. **Inquisitor**：攻击多头论点，并可提出新 crux。
4. **Judge**：只根据 agent 输出中的证据打分。
5. **Crux engine**：更新概率并决定继续、收敛或阻断。
6. **Report renderer**：从 engine state 生成 A 层证明账本，并给 B 层综合指令。
7. **Validator**：报告发布前做硬校验。

概率不是 LLM 写的，而是 `crux_engine.py` 算的。

## 重要安全规则

`fuse_break` 不是收敛。

如果仍有任何 crux 是 `OPEN` 或 `PENDING`，`deepthink_orchestrator_v2.py --report`
会返回 `blocked_unconverged`，拒绝生成正式报告。

## 常用命令

运行 v2 全链路自测：

```bash
python3 scripts/deepthink_orchestrator_v2.py --selftest
```

运行 crux engine 回放测试：

```bash
python3 scripts/crux_engine.py
```

检查版本一致性：

```bash
python3 scripts/version.py
```

## 目录结构

```text
agents/       agent prompt：framer、detective、inquisitor、judge
scripts/      orchestrator、engine、validator、数据工具
docs/         架构和设计说明
examples/     示例 state 和情景文件
references/   数据源和 vault 规则
SKILL.md      agent 运行时主说明
```

## License

MIT。
