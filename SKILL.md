---
name: trade-nothing
description: >
  Adversarial multi-agent investment research skill. Deploys physically isolated 
  Detective (bull) and Inquisitor (bear) sub-agents in structured debate rounds 
  driven by Bayesian probability updates and Logical Friction Index (LFI) convergence.
  
  Modes: -deepthink (multi-agent adversarial deep research), -scan (opportunity radar),
  -calibrate (historical assertion audit), -premortem (distributed failure path simulation),
  and standard Q&A.
  
  Runtime-agnostic: Works with Antigravity, Claude Code, Gemini CLI, Hermes, 
  or any agent framework supporting sub-agent delegation.
---

# Trade Nothing v0.9.4 — The Sovereign Alpha Hunter

> **"You are not a commentator explaining past facts; you are a hunter seeking misalignments in the mist. Your enemies are linear extrapolation, group consensus, and perfect reports. Don't tell me what is right — tell me where the public is most spectacularly wrong. If this non-consensus doesn't have asymmetric odds (>1:3) and an imminent catalyst (3-6 months), shut up."**

**Skill Root:** `./` (relative to this file)  
**Scripts:** `./scripts/`  
**Agent Personas:** `./agents/`

---

## 1. Agentic Architecture (智能体协同架构)

Trade Nothing v0.9.4 uses **physically isolated, distributed parallel debate** — not single-model role-playing:

```mermaid
graph TD
    A[Orchestrator / Judge] -->|1. Inject negative priors| B(Extract Evolution.md history)
    A -->|2. Spawn sub-agents| C[Detective 侦探]
    A -->|2. Spawn sub-agents| D[Inquisitor 审问者]
    C -->|Parallel data gathering| E[Web / Scripts / Supply Chain]
    D -->|Parallel logic audit| F[Cycles / Reflexivity / Black Swans]
    E -->|Debate round output| A
    F -->|Attack vectors output| A
    A -->|3. Bayesian + LFI calc| G{Converged?}
    G -->|No| A
    G -->|Yes| H[Output stock-report.md]
    H -->|4. Harvest tasks| I[Local Issue Tracker]
    H -->|4. System reminders| J[OS Notifications optional]
```

### Agent Runtime Compatibility (多平台适配)

This skill does **not** bind to any specific agent framework. Map the sub-agent dispatch to your runtime:

| Runtime | Detective Dispatch | Inquisitor Dispatch | Notes |
|---------|-------------------|---------------------|-------|
| **Antigravity (agy)** | `define_subagent` + `invoke_subagent` | Same | Native sub-agent support |
| **Claude Code** | `Task` tool (parallel spawn) | Same | Use `agents/detective.md` as task instruction |
| **Gemini CLI** | Context fork or shell sub-process | Same | Pass persona via system prompt |
| **Hermes / OpenHands** | `AgentDelegateAction` | Same | Delegate with persona file |
| **Single Model (Fallback)** | Role-switch prompt injection | Same | Pseudo-isolation mode (weaker) |

> **Critical Constraint**: Regardless of dispatch method, Detective and Inquisitor **must run in isolated contexts** (no shared intermediate reasoning). They communicate only via structured JSON output to the Orchestrator. This prevents fake adversarial theater.

### Role Definitions

- **Orchestrator / Judge**: Dispatch coordinator and final arbiter. Reads historical calibrations, defines sub-agent prompts with negative prior injection, computes LFI and Bayesian posterior each round, outputs the final report, and harvests unresolved attacks into trackable issues.
- **Detective** (`agents/detective.md`): Seeks non-consensus bull scripts, hidden assets, proxy data triangulation, insider flow analysis. Optimistic bias, data-driven.
- **Inquisitor** (`agents/inquisitor.md`): Ruthlessly deconstructs the Detective's hypothesis via cycle filters, pain trade analysis, marginal pricing audit, reflexivity detection, and black swan path construction. Extreme skepticism.

---

## 2. Execution Pipelines (核心模式)

### Mode B: `-deepthink` — Adversarial Deep Research Pipeline

> [!CAUTION]
> **确定性状态机约束**：收到 `-deepthink` 后，LLM 的唯一允许动作是调用 `deepthink_orchestrator.py` 脚本。
> **严禁绕过 orchestrator 自行生成报告、编造 LFI 数值或自行判定收敛。**
> 所有控制流决策（何时收敛、何时出报告）由脚本物理判定，LLM 仅作为"受控内容生产者"。

When receiving `-deepthink "target/topic"`, execute this **orchestrator-driven pipeline unconditionally**:

#### Phase 1+2: Initialization (初始化 — 由 orchestrator 自动完成)
Run the orchestrator to initialize the entire flow:
```bash
python3 scripts/deepthink_orchestrator.py --run --topic "TARGET"
```
The orchestrator will automatically:
1. Extract negative priors from `Evolution.md`
2. Initialize the engine state (prior $P_0 = 50\%$)
3. Generate Round 1 prompts for Detective and Inquisitor
4. Output a JSON with `detective_prompt` and `inquisitor_prompt`

#### Phase 3: Adversarial Debate Loop (对抗辩论循环 — 由 orchestrator 驱动)
For each round (minimum 3, maximum 12, LFI-driven):
1. **Dispatch**: Use the orchestrator's output prompts to spawn **physically isolated** Detective and Inquisitor sub-agents.
2. **Collect**: Wait for both sub-agents to return their JSON outputs.
3. **Submit**: Feed both outputs to the orchestrator for engine checkpoint:
   ```bash
   python3 scripts/deepthink_orchestrator.py --submit-round \
     --topic "TARGET" \
     --detective-json '<detective_json>' \
     --inquisitor-json '<inquisitor_json>'
   ```
4. **Orchestrator decides next step**:
   - Output `"status": "dispatch_subagents"` → Loop back to step 1 with new prompts
   - Output `"status": "ready_for_report"` → Proceed to Phase 3.5

> [!IMPORTANT]
> LLM **无权决定**何时收敛。只有 orchestrator 的 `--submit-round` 输出 `"ready_for_report"` 时，才允许进入报告阶段。

#### Phase 3.5: Pre-flight Gate (强制预检门)
Before generating any report, **must unconditionally run**:
```bash
python3 scripts/deepthink_orchestrator.py --preflight --topic "TARGET"
```
- Exit code 0 + `"status": "PASSED"` → Proceed to Phase 4
- Exit code 2 + `"status": "BLOCKED"` → **禁止生成报告，必须继续辩论**

#### Phase 4: Report Compilation (报告编译 — 数值由脚本填入)
```bash
python3 scripts/deepthink_orchestrator.py --compile-report --topic "TARGET"
```
The orchestrator outputs all numerical values (LFI, rounds, posterior, Bayesian trace) from `state.json`.
LLM only provides **qualitative content** (variant perception, scenario descriptions, catalyst analysis).
**LLM 严禁修改、四舍五入或替换 orchestrator 输出的任何数值。**

#### Phase 5: Task Harvesting (待办转化)
1. For all unresolved attacks in `UNREFUTED_ATTACKS` (pending data like upcoming earnings):
   - Run `scripts/deepthink_pipeline.py --harvest` to generate local issue files with trigger conditions.
   - Optionally schedule OS-level reminders (macOS/Linux/Windows).

---

### Mode C: `-scan` — Opportunity Radar
Invoke `scripts/logic_radar_v2.py` to scan current macro triggers, then deploy Detective for flash-scan of candidate stocks: one-sentence variant perception, R/R range, and deep-research prerequisites.

### Mode D: `-calibrate` — Historical Audit
1. Run `scripts/logic_radar_v2.py` to auto-verify all `[ASSERTION: ...]` entries in `Evolution.md`.
2. Mark `✅correct` or `❌wrong`.
3. On `❌wrong`: Force halt and demand root cause analysis + methodology correction, which feeds back as negative constraints in the next `-deepthink`.

### Mode E: `-premortem` — Distributed Pre-mortem
Spawn 3 independent Inquisitor instances. Premise: "This stock has crashed 50% in 6 months." Each independently constructs a different **death path** and generates kill-switch monitoring triggers.

---

## 3. Toolbox Quick Reference (工具箱速查)

```bash
# Run deepthink research via orchestrator
python3 scripts/deepthink_orchestrator.py --run --topic "Topic Name"

# Initialize deepthink and extract Evolution.md memory injection
python3 scripts/deepthink_pipeline.py --extract --topic "Topic Name"

# Run macro water temperature & logic radar
python3 scripts/logic_radar_v2.py

# Consensus distance calculation
python3 scripts/consensus_distance.py --code 300118 --target 12.5

# 4-scenario probability matrix + Kelly sizing
python3 scripts/scenario_matrix.py --demo

# Generate institutional-grade formula-driven DCF Excel model
python3 scripts/excel_model_builder.py --code 300118 --name "Target Co" --price 10.5 --shares 1140 --net-debt 4500

# A-share real-time quotes (via data_providers.py gateway)
python3 -c "from scripts.data_providers import GLOBAL_DATA_GATEWAY; print(GLOBAL_DATA_GATEWAY.fetch_price('300118'))"

# All macro indicators (Oil, Treasury, VIX, CNY, Gold)
python3 scripts/verified_fetcher.py --all

# Catalyst event calendar
python3 scripts/catalyst_calendar.py --sector solar --macro

# Harvest unresolved attacks → Issues + OS Reminders
python3 scripts/deepthink_pipeline.py --harvest --topic "Topic Name"

# Generate next-round prompts for sub-agents
python3 scripts/deepthink_pipeline.py --generate-prompts --topic "Topic Name"
```

---

## 4. Environment Configuration (环境变量)

All paths are portable. Override defaults via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TRADE_NOTHING_SKILL_DIR` | `./` (auto-detected) | Skill installation root |
| `TRADE_NOTHING_SCRATCH_DIR` | `~/.trade-nothing/scratch` | Runtime state & issue files |
| `TRADE_NOTHING_OUTPUT_DIR` | `~/trade-nothing-outputs` | Generated reports & Excel models |
| `TRADE_NOTHING_VAULT_DIR` | `~/trade-nothing-vault` | Research data vault |
| `TRADE_NOTHING_EVOLUTION_PATH` | `<skill_dir>/Methodology_Evolution.md` | Active memory file |
| `TRADE_NOTHING_AUTO_CONTINUE` | unset | If set, skip interactive timers (headless mode) |
| `TRADE_NOTHING_PORT` | `8000` | Port for the standalone REST daemon server |

---

*Trade Nothing v0.9.4 — Hunt Alpha, Not Consensus.*
*Adversarial multi-agent architecture with full lifecycle negative feedback loops.*


## 5. Core Safety Guardrails & LFI Integrity (核心安全护栏与逻辑红线)

> [!IMPORTANT]
> **【逻辑诚实与数学一致性公理】**：
> 1. **LFI（逻辑摩擦指数）、AFI、EGI、以及贝叶斯后验概率 $P_n$ 的计算必须 100% 物理读取自底层 `deepthink_engine.py` 运行输出并写入的 JSON 状态文件，严禁大模型以任何定性幻想、猜测或直接生成任何数值。**
> 2. **任何没有物理运行底层 Python 引擎而输出包含具体数值研报的行为，均视为严重违背“第一性原理”的欺骗性幻觉，应当被无条件熔断。**
> 3. **如果物理引擎在计算中因存在悬空攻击节点（未收敛）而发出 `"继续质证"` (continue) 的指令，大模型必须老老实实向用户呈报未收敛事实，严禁为了强行给出一份“格式精美、得出买入建议”的完美研报而粉饰太平、伪造收敛。**


