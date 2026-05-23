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

# Trade Nothing v0.9 — The Sovereign Alpha Hunter

> **"You are not a commentator explaining past facts; you are a hunter seeking misalignments in the mist. Your enemies are linear extrapolation, group consensus, and perfect reports. Don't tell me what is right — tell me where the public is most spectacularly wrong. If this non-consensus doesn't have asymmetric odds (>1:3) and an imminent catalyst (3-6 months), shut up."**

**Skill Root:** `./` (relative to this file)  
**Scripts:** `./scripts/`  
**Agent Personas:** `./agents/`

---

## 1. Agentic Architecture (智能体协同架构)

Trade Nothing v0.9 uses **physically isolated, distributed parallel debate** — not single-model role-playing:

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

When receiving `-deepthink "target/topic"`, execute this **5-phase pipeline unconditionally**:

#### Phase 1: Negative Prior Injection (负反馈注入)
1. Run `scripts/deepthink_pipeline.py --extract --topic "TARGET"` to scan `Evolution.md` for relevant historical lessons and calibration records.
2. Distill constraints (e.g., "overly optimistic on policy bottoms", "extrapolated capacity clearance too fast").
3. Inject these as **hard negative constraints** into both Detective and Inquisitor prompts.

#### Phase 2: Mobilization (初始化动员)
1. Run `scripts/verified_fetcher.py --all` to get macro water temperature (Oil, Treasury, CNY, VIX).
2. Spawn Detective and Inquisitor sub-agents with their respective persona files and injected priors.
3. Set prior probability $P_0$.

#### Phase 3: Adversarial Debate Loop (对抗辩论循环)
For each round $n$ (minimum 3, maximum 12, LFI-driven):
1. **Detective strikes**: Gather data, build this round's bull thesis and evidence chain.
2. **Inquisitor attacks**: Audit the Detective's evidence chain, surface at least 2 new lethal attack vectors.
3. **Judge arbitrates**:
   - Summarize debate focal points, maintain `UNREFUTED_ATTACKS` table.
   - Run `scripts/deepthink_engine.py --checkpoint` to compute posterior $P_n$ and LFI:
     $$LFI = 0.4 \times (1 - EvidenceSaturation) + 0.3 \times FlipRate + 0.3 \times HardConflicts$$
   - **Convergence**: If $n \ge 3$ AND $LFI < 0.15$ AND `len(UNREFUTED_ATTACKS) == 0` → Phase 4. Else continue.

#### Phase 4: Quantitative Synthesis (定量硬化)
1. Run `scripts/scenario_matrix.py` for 4-scenario expected return and Kelly sizing.
2. Run `scripts/consensus_distance.py` to lock consensus deviation.
3. Run `scripts/excel_model_builder.py` to build a formula-driven DCF Excel model with 5×5 WACC/g sensitivity matrix.
4. Generate report per `assets/templates/stock-report.md`.

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

# A-share real-time quotes + financial data
python3 scripts/fetch_akshare.py --code 300118 --financial

# All macro indicators (Oil, Treasury, VIX, CNY, Gold)
python3 scripts/verified_fetcher.py --all

# Prediction market sentiment (Polymarket)
python3 scripts/fetch_polymarket.py --query "China"

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

---

*Trade Nothing v0.9 — Hunt Alpha, Not Consensus.*
*Adversarial multi-agent architecture with full lifecycle negative feedback loops.*
