# Trade Nothing

Trade Nothing 是一套对抗式投资研究 Skill。它把研究拆成若干承重 crux，由偏多的
Detective 和偏空的 Inquisitor 分别寻找证据与反证，再由确定性证据闸门判断是否允许
生成正式报告。

它是研究工作流，不是自动交易系统。它不会自动给出买卖指令、目标价、预期收益、
Kelly 仓位或持仓比例。

## 现在真正可靠的部分

- Judge 信号必须携带 claim、source、date 和具体文章/公告/API URL；否则不能推动 crux。
- Judge 的引用必须能反查到隔离 agent 的原始 JSON，不能临时编造。
- 同一 URL + claim + number 不能重复计分。
- 每条 crux 至少需要两个不同的具体来源，才允许退休。
- `continue` 和 `fuse_break` 都会阻断正式报告。
- 报告中的数值是**辩论支持度**，不是经过历史校准的市场概率。
- 运行状态写入 `TRADE_NOTHING_SCRATCH_DIR`，不再污染 Skill 源码目录。
- 系统提醒与 webhook 默认关闭；只有显式传入 `--notify` / `--webhook` 才会触发。

## 隔离是宿主能力，不是 Skill 自带能力

Skill 本身无法保证“物理隔离”。宿主应把 Detective 和 Inquisitor 放进互不共享中间
推理的独立上下文。如果只能由同一个模型切换角色，报告必须标注为 `degraded`，不得
声称完成了物理隔离或真正的多智能体对抗。

## 推荐流程：`-deepthink2`

运行前先完整阅读 [SKILL.md](SKILL.md)。

```bash
# 1. 立题：生成可证伪的研究问题与 2-5 条 crux。
python3 scripts/deepthink_orchestrator_v2.py --frame --topic "TARGET"

# 2. 宿主运行 agents/framer.md，再初始化状态。
python3 scripts/deepthink_orchestrator_v2.py --init \
  --topic "TARGET" --frame-json '<framer_json>'

# 3. 在隔离上下文运行 Detective/Inquisitor，再由 Judge 评分并逐轮提交。
python3 scripts/deepthink_orchestrator_v2.py --submit \
  --topic "TARGET" --det '<detective_json>' \
  --inq '<inquisitor_json>' --judge '<judge_json>'

# 4. 只有收敛和证据闸门同时通过，才会输出正式报告。
python3 scripts/deepthink_orchestrator_v2.py --report --topic "TARGET"
```

主要状态：

- `dispatch_subagents`：只继续质证 OPEN crux。
- `ready_for_report`：确定性收敛与证据闸门通过。
- `blocked_max_rounds`：达到熔断轮次，禁止正式报告。
- `blocked_unconverged`：仍有未决 crux，禁止正式报告。
- `blocked_evidence_gate`：独立来源不足，禁止正式报告。
- `no_edge`：立题阶段没有发现值得投入的非共识角度，提前停止。

旧的 `-deepthink` 单后验/LFI 流程仅为兼容保留。其数值是未校准的历史启发式，不能
包装成真实胜率。

## v2 证据格式

Detective 在 `crux_evidence` 中按 crux 提交证据；Inquisitor 在 `crux_attacks` 中按
crux 提交攻击。引用对象格式如下：

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

裸域名、缺日期、缺来源，以及 Judge 自行补出的引用都会被拒绝。

## 环境变量

| 变量 | 默认值 | 用途 |
|---|---|---|
| `TRADE_NOTHING_SKILL_DIR` | 自动识别 | Skill 安装根目录 |
| `TRADE_NOTHING_SCRATCH_DIR` | `~/.trade-nothing/scratch` | 状态与 Issue 文件 |
| `TRADE_NOTHING_OUTPUT_DIR` | `~/trade-nothing-outputs` | 生成物 |
| `TRADE_NOTHING_VAULT_DIR` | `~/trade-nothing-vault` | 研究资料库 |
| `TRADE_NOTHING_EVOLUTION_PATH` | `<skill>/Methodology_Evolution.md` | 负面先验记忆 |
| `TRADE_NOTHING_MODEL_DEEP` | 宿主默认 | 质量关键 agent 与 Judge |

## 维护与同步

默认本地配置以 `~/Documents/trade-nothing` 为唯一开发源。

```bash
# 确定性、离线的 v2 安全回归
make test

# 旧流程兼容测试
make test-legacy

# 不作为发布闸门的在线数据源诊断
make test-live

# 同步受控源码到 Codex 与 Gemini 安装副本
make install

# 只校验哈希，不改文件
make status
```

`make install` 不会复制或删除运行期 JSON、state、scratch 或个人研究文档。

## 许可证

MIT，见 [LICENSE](LICENSE)。
