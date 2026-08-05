---
name: trade-nothing
description: >
  Adversarial investment-research skill with a crux evidence ledger, citation-gated
  Judge signals, deterministic convergence, a non-promotable hypothesis-and-proxy
  exploration ledger, evidence-backed opportunity harvesting
  from both surviving and failed cruxes, and two-sided CandidateScreen investability
  pre-checks plus snapshot-bound claim verification. Host-enforced agent isolation is used
  where the runtime supports it. Debate-support scores, OpportunitySeeds, screening states,
  and claim-verification states are workflow heuristics, not calibrated probabilities,
  expected returns, trade instructions, or sizing inputs.
  
  Modes: -deepthink2 (recommended crux-based research), -deepthink (legacy LFI pipeline),
  -scan (experimental macro radar, not a full-universe scanner),
  -calibrate (historical assertion audit), -premortem (distributed symmetric scenario stress test),
  and standard Q&A.
  
  Runtime-agnostic: Works with Antigravity, Claude Code, Gemini CLI, Hermes, 
  or any agent framework supporting sub-agent delegation.
---

# Trade Nothing v0.13.0 — The Sovereign Alpha Hunter

> **"Propose boldly where consensus may be wrong; follow faint proxy trails before the answer is
> obvious; promote nothing until evidence survives adversarial checks. Seek upside actively without
> hiding failure paths, invalidation, or the price already paid. Excess caution is not edge, and
> imaginative prose is not evidence."**

**Skill Root:** `./` (relative to this file)  
**Scripts:** `./scripts/`  
**Agent Personas:** `./agents/`

---

## 1. Agentic Architecture (智能体协同架构)

Trade Nothing requires **host-enforced isolated contexts** for the Detective and Inquisitor.
Framer is deliberately different: it must execute **inline in the parent context**, without search
or sub-agent dispatch. It declares `research_intent` and creates hypotheses and research structure,
not evidence. `OPPORTUNITY_DISCOVERY` and `HYBRID` start with a 5–7 path entity-agnostic hypothesis
garden even when the named task is one company or asset; `THESIS_CHALLENGE` may omit it.
The frame also separates `as_of_date` (the evidence cutoff), `horizon` (relative decision window),
and optional `forecast_target_date` (an exact future target). A question that names a later date
without the explicit target field is invalid rather than silently treated as future evidence.
The skill itself cannot guarantee physical isolation; the host must record how agents were
dispatched. Single-model role switching is allowed only as an explicitly labelled `degraded` run.

```mermaid
graph TD
    A[Deterministic Orchestrator] -->|1. Inject negative priors| B(Extract Evolution.md history)
    A -->|2. Frame research intent| K[Hypothesis Garden: HYPOTHESIS_ONLY]
    K -->|3. Spawn isolated roles| C[Detective 侦探]
    K -->|3. Spawn isolated roles| D[Inquisitor 审问者]
    C -->|Parallel data gathering| E[Web / Scripts / Supply Chain]
    D -->|Parallel logic audit| F[Cycles / Reflexivity / Black Swans]
    E -->|Evidence + hypothesis sparks| A
    F -->|Attacks + proxy trails| A
    A -->|4. Citation gate + crux support update| G{Research-ready?}
    G -->|No| A
    G -->|Yes| H[Formal status + labelled exploration report]
    H -->|5. Harvest formal tasks| I[Local Issue Tracker]
    H -->|5. Optional exploration actions| J[Human-authorized bounded tests]
```

### Agent Runtime Compatibility (多平台适配)

This skill does **not** bind to any specific agent framework. Map the sub-agent dispatch to your runtime:

| Runtime | Detective Dispatch | Inquisitor Dispatch | Notes |
|---------|-------------------|---------------------|-------|
| **Antigravity (agy)** | `define_subagent` + `invoke_subagent` | Same | Native sub-agent support |
| **Claude Code** | `Task` tool (parallel spawn) | Same | Use `agents/detective.md` as task instruction |
| **Gemini CLI** | Context fork or shell sub-process | Same | Pass persona via system prompt |
| **Hermes / OpenHands** | `AgentDelegateAction` | Same | Delegate with persona file |
| **Single Model (Fallback)** | Role-switch prompt injection | Same | Must be marked `degraded`; no isolation claim |

Framer is never dispatched through the mechanisms in this table. On every runtime—including
Antigravity/`agy`—the parent reads `agents/framer.md`, produces its strict JSON inline, and submits
that JSON to `--init`. See `references/runtime-protocol.md` for bounded waits and failure handling.

> **Critical Constraint**: Detective and Inquisitor must run in isolated contexts with no shared
> intermediate reasoning and communicate only through structured JSON. If the host cannot enforce
> this, state that limitation in the report; do not claim a physically isolated multi-agent run.

### Role Definitions

- **Orchestrator**: Deterministic dispatch and report gate. Loads negative priors, stores evidence,
  de-duplicates citations, applies bounded support-score updates, evidence-back-checks and merges
  OpportunitySeeds across rounds, combines isolated Candidate Analyst/Skeptic screens without
  averaging away disagreement, binds decisive claims to content-hashed source snapshots, and
  blocks unconverged or source-unverified promotion.
- **Judge**: Evidence scorer, not a researcher or final decision-maker. It may score only claims
  present in the isolated agent JSON and must attach concrete citations.
- **Detective** (`agents/detective.md`): Generates non-consensus mechanisms, follows faint proxy
  trails, and verifies physical constraints, value transfer, and pricing. Optimistic exploration
  bias; explicit evidence boundary.
- **Inquisitor** (`agents/inquisitor.md`): Applies full-strength red-team attacks while constructing
  symmetric bull-surprise, base, and bear-failure paths. It can preserve counter-mechanism sparks
  without forcing an arbitrary crash or bottom price.
- **Claim Verifier** (`agents/claim_verifier.md`): Independently checks claim-to-snapshot alignment
  using short exact source spans. It does not assess publisher truth or investment merit.

---

## 2. Execution Pipelines (核心模式)

### Mode B: `-deepthink` — Legacy LFI Pipeline

> [!WARNING]
> This mode is retained for compatibility. Its single-posterior/LFI outputs are uncalibrated and
> must not be represented as market probabilities. New research should use `-deepthink2`.

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
1. **Dispatch**: Use the orchestrator's output prompts to spawn Detective and Inquisitor in host-enforced isolated contexts.
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
   - External side effects are opt-in: add `--notify` for OS reminders or `--webhook` for webhook delivery.

---

### Mode C: `-scan` — Experimental Macro Radar

Invoke `scripts/logic_radar_v2.py` to inspect its configured macro triggers. This is **not** a
full-universe stock scanner: the current script does not maintain a security universe, rank
candidates, or validate investability. If a host adds a Detective flash screen, label it
experimental and route any candidate back through `-deepthink2`. Do not emit R/R, target price,
or position sizing from radar output.

### Mode D: `-calibrate` — Historical Audit
1. Run `scripts/logic_radar_v2.py` to auto-verify all `[ASSERTION: ...]` entries in `Evolution.md`.
2. Mark `✅correct` or `❌wrong`.
3. On `❌wrong`: Force halt and demand root cause analysis + methodology correction, which feeds back as negative constraints in the next `-deepthink`.

### Mode E: `-premortem` — Distributed Pre-mortem
Spawn 3 independent Inquisitor instances. Each constructs a different symmetric
`BULL_SURPRISE / BASE / BEAR_FAILURE` map over the declared horizon, with observable triggers,
transmission chains, falsifiers, and kill-switch monitors. Do not preset a crash percentage,
bottom price, target price, or path probability.

---

### Mode F: `-deepthink2` — Crux-Based Adversarial Pipeline (v0.13.0, recommended)

> Replaces the single-posterior + LFI layer (which railroaded every run to 0%/100% and always
> burned 12 rounds) with two separate ledgers: a non-promotable **exploration ledger** for wild
> hypotheses, sparks, proxy trails, alternative explanations, and cheap tests; and a
> **per-crux evidence ledger** for bounded debate-support, decision-readiness convergence,
> de-duplicated citations, OpportunitySeed admission, and formal reporting. The score is a workflow heuristic, not
> a probability, return forecast, target price, trade signal, or sizing input.

**Model tiering** (`scripts/model_tiers.py`): Detective / Inquisitor / Candidate Analyst /
Candidate Skeptic / Claim Verifier / Framer / Judge / battle-log synthesis use the **DEEP** model by default.
Judge and CandidateScreen evidence quality directly control their respective gates.
Override via `TRADE_NOTHING_MODEL_DEEP` / `TRADE_NOTHING_MODEL_FAST`.

When receiving `-deepthink2 "target/topic"`, run this orchestrator-driven loop:

For Antigravity, prefer the resumable host runner after producing the Framer JSON inline. It creates
an immutable `run_id`, runs Detective/Inquisitor in separate OS processes, checkpoints successful
roles, dispatches Judge separately, and never retries a failed role automatically:

```bash
python3 scripts/deepthink_host_runner.py start --topic "TARGET" \
  --frame-json '<framer_output>' --run-purpose PRODUCTION_RESEARCH --round-budget 1
# Continue only after the caller authorizes more runtime/research budget:
python3 scripts/deepthink_host_runner.py resume --run-id "RUN-..." --round-budget 1
# Adopt a pre-v0.12 state once, then address it only by run_id:
python3 scripts/deepthink_host_runner.py adopt --state-path "/.../v2_state.json"
```

Use `--allow-agent-tools` only after explicit authorization. The default one-round budget is
intentional. A 429, timeout, invalid JSON, or one-sided failure returns a stage envelope and retains
the successful role payload; resume reruns only the missing role. Read
`references/run-resume-protocol.md` before adopting or recovering a run. Registered stage results
are content-addressed artifacts: the public envelope contains control fields and verified paths,
not the full result/report body. Read `references/artifact-envelope-protocol.md` before explicitly
loading one. The manual commands below
remain a runtime-agnostic fallback; once a run has an id, do not mix topic-based and run-id-based
addressing.

```bash
# 1. Framing gate (DEEP, runs once) — question type + research intent + logic graph + 2-5 cruxes
python3 scripts/deepthink_orchestrator_v2.py --frame --topic "TARGET"
# When tradenothing-next exported a human-gated ACTIVE Lesson packet, read
# references/research-start-packet-protocol.md and add:
#   --start-packet /path/to/RSP-....json
#    → execute agents/framer.md INLINE IN THE PARENT. Never define/invoke a Framer sub-agent and
#      never browse during framing. If no_edge_precheck.is_researchable=false → emit
#      No-Edge statement and STOP (spawn nothing). Lack of an obvious variant perception is not
#      sufficient; false means the question is not bounded or falsifiable.
#    → Framer must return inline JSON only. It must not create Markdown, Google Drive/cloud files,
#      or choose an output path. Persistence requires explicit user opt-in and an approved output root.
#    → OPPORTUNITY_DISCOVERY/HYBRID must include 5-7 entity-agnostic wild hypotheses in
#      hypothesis_garden, all HYPOTHESIS_ONLY. THESIS_CHALLENGE may omit the garden.

# 2. Init from frame → Round-1 dispatch prompts (Detective+Inquisitor scoped to all cruxes)
python3 scripts/deepthink_orchestrator_v2.py --init --topic "TARGET" --frame-json '<framer_output>'
# If --frame used --start-packet, --init MUST receive that exact same packet.
#    → status=frame_rejected when premise_audit, unit_of_analysis, falsifiers, concrete catalyst
#      windows, or No-Edge basis are missing. Never repair or bypass this gate by hand.
#    A host with physically isolated contexts may additionally pass --runtime-isolation verified.
#    Framer JSON cannot self-attest this field; default is unverified.

# Runtime failure receipt (non-formal; use after a bounded stage timeout, never as a report)
python3 scripts/deepthink_orchestrator_v2.py --runtime-failure --topic "TARGET" \
    --stage framing --reason "host timeout before init"

# 3. Each round: spawn isolated Detective (detective.md) + Inquisitor (inquisitor.md) on the
#    OPEN cruxes only (+ Inquisitor's free-roam slot to re-open a resolved crux). Both may emit
#    max 3 HYPOTHESIS_ONLY sparks and 3 proxy trails for the separate exploration ledger, plus
#    max 3 OpportunitySeeds backed by their own same-round/same-crux evidence. Judge must ignore
#    every exploration object. Then score only formal evidence with
#    the DEEP Judge (agents/judge.md) and submit:
python3 scripts/deepthink_orchestrator_v2.py --submit --topic "TARGET" \
    --det '<detective_json>' --inq '<inquisitor_json>' --judge '<judge_json>'
#    → status=dispatch_subagents (loop), blocked_max_rounds, ready_for_report, OR for
#      UNIVERSE_SEARCH/COMPARATIVE with screenable leads: dispatch_candidate_screeners;
#      with only blocked evidence-backed leads: candidate_gap_tasks_planned.

# 3a. Candidate maturation: after convergence, execute the bounded task rather than rewriting
#     an OpportunitySeed or lowering the independent-source gate. Every attempt is appended.
python3 scripts/deepthink_orchestrator_v2.py --plan-candidate-gaps --topic "TARGET"
python3 scripts/deepthink_orchestrator_v2.py --submit-gap-evidence --topic "TARGET" \
    --task-id "CGT-..." --supplement '<candidate-evidence-supplement JSON>'
# If the bounded task ends without aligned evidence, preserve a terminal research result.
python3 scripts/deepthink_orchestrator_v2.py --close-gap-task --topic "TARGET" \
    --task-id "CGT-..." --close-status SOURCE_EXHAUSTED --close-reason "reason"
# Read references/candidate-maturation-protocol.md before using these commands.

# 4. Report: only converged states may render a formal report. Opportunity questions with an
#    unscreened READY_FOR_SCREENING seed default to the bounded CandidateScreen continuation below;
#    report rendering is deferred until that batch completes. Use --challenge-only only when the
#    user explicitly requests thesis critique without opportunity screening. The orchestrator
#    exposes a deterministic facts box, Evidence Ledger, candidate cards, and structured synthesis
#    input. The parent compiles the content-driven Decision Brief without altering locked facts.
python3 scripts/deepthink_orchestrator_v2.py --report --topic "TARGET"
# Low-context locked-facts view (synthesis input remains explicit opt-in):
python3 scripts/deepthink_orchestrator_v2.py --report --topic "TARGET" --report-view facts_box
# Read references/report-contract.md before changing report status words, views, or next actions.
# Explicit thesis-critique-only escape hatch:
python3 scripts/deepthink_orchestrator_v2.py --report --topic "TARGET" --challenge-only

# 4a. Fuse-break: formal report remains blocked, but always render a non-formal Resolution Memo
#     plus a compact continuation packet. Persist the memo when the user requested an artifact.
python3 scripts/deepthink_orchestrator_v2.py --resolution-memo --topic "TARGET"

# 4b. Resume only after explicit user authorization because this consumes more research budget.
python3 scripts/deepthink_orchestrator_v2.py --resume-blocked --topic "TARGET" --extra-rounds 3

# 4c. Optional exploration loop. Design and planning are safe and non-executing.
# If exploration_action.authorization_state=NEEDS_ACTION_DESIGN, record exactly
# the typed design requested by its action_code. The design must bind both the
# emitted design_target_id and design_state_revision.
python3 scripts/deepthink_orchestrator_v2.py --record-exploration-design \
    --topic "TARGET" --exploration-design \
    '{"design_reviewed":true,"design_scope":"ONE_EXPLORATION_LEDGER_DESIGN","design_note":"reviewed the cheapest two-sided test","design_target_id":"DT-...","expected_state_revision":12,"hypothesis_id":"WH-...","action_code":"DESIGN_PROXY_TRAIL","proxy_plan":[{"direction":"SUPPORTS","proxy":"dated customer acceptance milestone","causal_link":"acceptance distinguishes qualified scarcity from announced capacity","publisher_class":"CUSTOMER_OR_COUNTERPARTY","bounded_query":"site:customer.example dated acceptance supplier","stop_condition":"stop after one query or three documents","origin_crux":"C1"},{"direction":"CONTRADICTS","proxy":"dated qualification lead-time compression","causal_link":"compression contradicts persistent qualified scarcity","publisher_class":"REGULATOR_OR_OFFICIAL_DATASET","bounded_query":"official qualification lead time series","stop_condition":"stop after one query or three documents","origin_crux":"C1"}]}'

# Planning freezes one attempt. Repeating this command is idempotent while that
# exact attempt remains open. An unapproved plan may be explicitly cancelled;
# cancellation performs no search and allows a new attempt ID.
python3 scripts/deepthink_orchestrator_v2.py --plan-exploration --topic "TARGET"
python3 scripts/deepthink_orchestrator_v2.py --cancel-exploration-action \
    --topic "TARGET" --action-id "EA-..." --reason "superseded by a better diagnostic route"

# Never call --authorize-exploration unless the user explicitly authorizes the
# exact action_id. This receipt is caller-attested procedural evidence; it is
# not cryptographic proof of a host UI approval event.
python3 scripts/deepthink_orchestrator_v2.py --authorize-exploration --topic "TARGET" \
    --action-id "EA-..." --authorization-receipt \
    '{"action_id":"EA-...","explicit_user_authorization":true,"authorization_scope":"ONE_BOUNDED_EXPLORATION_ACTION","authorization_note":"user explicitly approved this one bounded test"}'
# Run only the emitted dispatch contract, then close it with the exact bounded receipt.
python3 scripts/deepthink_orchestrator_v2.py --submit-exploration-result --topic "TARGET" \
    --action-id "EA-..." --exploration-result '<authorized exploration result JSON>'
# This endpoint may write one ProxyTrail only. It cannot mutate cruxes, OpportunitySeeds,
# CandidateScreens, claims, decisions, trades, or schedule a follow-on.
# Every document needs a concrete URL and YYYY-MM-DD date on or before the frozen
# as_of_date. Proxy evidence must bind an exact document_id (or the full canonical
# citation tuple), planned route_id, planned proxy, origin crux, query, source class,
# causal link, and stop condition. If formal or exploration state changed after
# authorization, the result is not ingested: the host stores only a SHA-256 stale
# receipt, closes the old attempt, and forbids automatic retry.

# 5. CandidateScreen: for opportunity questions this is the default post-convergence continuation.
#    The deterministic engine selects at most 3 de-duplicated READY_FOR_SCREENING seeds using
#    evidence breadth, causal directness, structured pricing-anchor completeness, and observable
#    catalyst. This is research priority, not expected return, conviction, or a ranking signal.
#    Omit --seed-id to screen the next unscreened batch (max 3).
python3 scripts/deepthink_orchestrator_v2.py --screen --topic "TARGET" --as-of "YYYY-MM-DD"

# 6. Submit both isolated JSON payloads. The deterministic engine emits WATCHLIST,
#    REJECTED, or THESIS_CANDIDATE, then --report renders the eight-dimension matrix.
python3 scripts/deepthink_orchestrator_v2.py --submit-screen --topic "TARGET" --as-of "YYYY-MM-DD" \
    --screen-isolation verified --analyst '<candidate_analyst_json>' --skeptic '<candidate_skeptic_json>'

# 7. List decisive claims and URLs that require immutable page snapshots.
python3 scripts/deepthink_orchestrator_v2.py --verification-plan --topic "TARGET"

# 8. Capture public pages (repeat --url) and dispatch the independent Claim Verifier.
python3 scripts/evidence_snapshot.py --url "SPECIFIC_URL" --output snapshots.json
python3 scripts/deepthink_orchestrator_v2.py --verify-claims --topic "TARGET" \
    --snapshots snapshots.json

# 9. Submit exact-span verdicts. Only snapshot-aligned VERIFIED candidates return to
#    DRAFT_REQUIRES_HUMAN; contradictions physically block promotion.
python3 scripts/deepthink_orchestrator_v2.py --submit-verification --topic "TARGET" \
    --snapshots snapshots.json --verifier '<claim_verifier_json>' --verifier-isolation verified
```

#### Phase 3.7: Tracking Track（赔率轨 — v0.12,并行研究轨）

被正式闸门卡住的 OpportunitySeed(未达 `READY_FOR_SCREENING` 且非 REJECTED),若同时满足——
赔率实质(`asymmetry_case` 已声明)、逻辑链 ≥3 环、升级/放弃检查点齐全——由
`scripts/tracking_engine.py` 确定性写入 `tracking_ledger`(ACTIVE),每轮 harvest 后自动同步。

- 账本状态: `ACTIVE` → `ESCALATED`(seed 经正式轨升级)/ `CLOSED`(被筛选否决,记录 close_reason)。
- **跟踪 ≠ 推荐**: 不改变 crux 评分、收敛、筛选、晋级或 validator 契约;无晋级与交易权限。
- Inquisitor 对每条 seed 声明 `odds_calibration`(`success_enablers` / `primary_failure_mode` /
  `failure_signal`),失败信号在准入时写入账本,供后续轮次与人工复核使用。
- 报告呈现为「跟踪清单」: 赔率姿态 × 检查点·升级 × 检查点·放弃 × 失败信号 × 下一动作。
- 设计文档: `docs/path-led-research-v0.12.md`;测试: `scripts/test_tracking_engine.py`。

#### Phase 4: Report Compilation（事实层锁定，叙事层综合）

`--report` 输出三个确定性产物：

- `facts_box_markdown`：原样嵌入 Decision Brief 顶部，不得修改；
- `evidence_ledger_markdown`：独立保存为 `{topic}_evidence_ledger.md`；
- `candidate_cards_markdown`：按内容需要嵌入 Brief 末尾或独立保存。

同时保留 `report_view_model`；只有显式传入 `--include-synthesis` 时才会提供
`synthesis_packet`。父上下文基于这些结构化输入编写叙事，并交付两个主文件：
`{topic}_decision_brief.md` 与 `{topic}_evidence_ledger.md`。兼容字段
`report_markdown` 与 `brief` / `full` 视图仍可读取，但新报告不得把它们当作默认成品。

##### Decision Brief 约束

1. 顶部逐字嵌入 `facts_box_markdown`。
2. 标题必须反映本次研究最核心的发现，不使用通用报告标题。
3. Facts Box 之后的叙事不超过 120 行，整个 Brief 不超过 150 行。
4. 叙事结构从研究发现中生长，但必须覆盖：最有价值的 2–4 条洞见、对称场景和下一步
   观察清单。
5. 数值、状态词、crux 状态、候选计数、卡片动作码和正式动作必须与确定性产物一致。
6. 引用只能来自 `report_view_model` 或显式提供的 `synthesis_packet`，使用
   `[来源名, 日期](URL)` 内联标注；不得凭空新增引用。
7. Facts Box 已包含统一边界声明，叙事中不得重复堆叠免责声明。

##### 反模板约束（Anti-Template Rule）

以下元素不得跨报告机械复用：

- 固定节段名，例如“变异感知提纯”“猎杀元数据”“专家审计闭环”“运行边界”；
- 固定 emoji 前缀，例如每篇都出现 🐑 / 🐺 / 🐂 / 🐻；
- 固定反事实句式，例如“如果 N 个月后亏了 X%，最可能原因是什么”；
- 固定 12 字段假说卡。

发现数据矛盾，就围绕矛盾展开；发现供应链关系，就讲清因果链；发现时间窗口，就聚焦
催化剂。不要因为旧模板存在某一节就补写无信息内容。叙事风格参考自然、内容驱动的雪球
长文与克制、数字和来源明确的人工决策简报。

> **Facts Box integrity:** LLM 严禁修改 `facts_box_markdown` 中的任何数值、状态词
> (`edge_state`, `evidence_direction`, `actionability`)、crux 行、候选计数或
> `formal_action`。解释可以增加语境，但不能暗示与锁定结论相反的判断。

> **Integrity:** all support scores/statuses are computed by `crux_engine.py` from Judge signals;
> the LLM must not write or alter these values. Convergence (every crux RESOLVED or MONITORABLE +
> decision stable + adversary dry) is decided by the script, not the LLM. The Judge's signal is
> bounded `[-1,1]`; no valid concrete citation means zero signal, strong signals require a sourced
> number, and duplicate evidence cannot move the same crux twice. `fuse_break` blocks formal reporting.
> The Judge must treat `wild_hypotheses`, `hypothesis_sparks`, `proxy_trails`, and every
> `HYPOTHESIS_ONLY` object as absent when scoring. Exploration novelty cannot move support, source
> counts, convergence, evidence maturity, or promotion.
> A fuse-break must still emit the deterministic non-formal Resolution Memo and compact continuation
> packet. Never auto-resume it. Late cruxes missing a falsifier/catalyst or introduced after the
> dry-round cutoff are deferred to a future topic instead of blocking the current run.
> The user-facing verdict is always three-dimensional: `edge_state`, `evidence_direction`, and
> `actionability`. `NO_EDGE` means no usable expectation gap was established; it never means
> `AVOID` or `SHORT`. A short direction requires an independently admitted short seed and screen.

> **Cost integrity:** each round deterministically dispatches at most two OPEN cruxes, prioritizing
> untested, least-recently-scored, and decision-uncertain cruxes without retiring deferred work. Each
> research agent gets at most 2 searches per dispatched crux. Stop after 2 searches without new
> primary evidence and return `UNKNOWN` for the formal finding. A role may preserve a useful anomaly
> as a `HYPOTHESIS_ONLY` spark or non-promotable proxy trail, but doing so grants no additional
> search and no evidence credit. A later exploration action requires a separately explicit human authorization
> and its own bounded query/document/stop contract. When untested cruxes exist, disable free-roam and do not
> redispatch resolved cruxes. Parent/orchestrator contexts
> consume artifact envelopes, compact packets, and final artifact paths only—never raw transcripts,
> search logs, full external-agent payloads, or a report body duplicated from disk.
> Every delegated stage must use the bounded waits in `references/runtime-protocol.md`. A timeout
> must emit `--runtime-failure`; never fabricate missing JSON, wait indefinitely, or retry automatically.

> **Framing integrity:** every factual seed must appear in `premise_audit` as `HYPOTHESIS` or
> `URL_CLAIMED_UNVERIFIED`; `SOURCED` is forbidden before snapshot-bound verification. A candidate
> URL remains unverified even when it looks concrete. A researchable frame needs 2–5 cruxes, each
> with a monitor, falsifier, and exact future catalyst checkpoint inside the 3–6 month horizon.
> Each catalyst must declare `REVIEW_CHECKPOINT` or `DATE_CLAIMED_UNVERIFIED` and bind to a premise
> ID included in the No-Edge basis. The report keeps every framing premise visibly provisional.
> Every researchable crux must also freeze 2–3 bounded `evidence_plan` routes spanning at least two
> publisher classes. Init rejects a round fuse that cannot accommodate deterministic crux rotation,
> Landscape coverage, and the post-coverage dry window. Read
> `references/framing-feasibility-protocol.md` before changing the Framer schema or scheduler.
> Every researchable frame must also declare one question type and a connected logic graph.
> It must independently declare `research_intent=THESIS_CHALLENGE|OPPORTUNITY_DISCOVERY|HYBRID`;
> question type cannot be used as a proxy for user intent. `OPPORTUNITY_DISCOVERY` and `HYBRID`
> require 5–7 entity-agnostic `HYPOTHESIS_ONLY` wild hypotheses with symmetric scenario paths,
> alternative explanations, proxy plans, and cheap tests—even for a named single company or asset.
> `THESIS_CHALLENGE` may omit the garden. Absence of an obvious variant perception is not a valid
> No-Edge pre-check failure when the question remains bounded and falsifiable.
> `UNIVERSE_SEARCH` requires both an `OPPORTUNITY_PATH` and a `PRICING` crux. Read
> `references/research-question-types.md` before framing broad, comparative, or multi-path questions.

> **Opportunity integrity:** a root-thesis `NO_EDGE` verdict does not erase a valid
> substitute, competitor, bottleneck-owner, infrastructure-owner, second-order, or short seed.
> Every seed must pass the same-agent + same-round + same-crux citation back-check. Evidence maturity
> and screening eligibility are separate: a screenable path also needs a healthy origin crux, root
> convergence, and a structured catalyst inside the root horizon. Report and default dispatch group
> exact duplicate entities without combining evidence across paths. Read
> `references/opportunity-protocol.md` for the exact schema and admission rules.
> The exploration ledger is deliberately earlier than OpportunitySeed admission:
> `HYPOTHESIS_ONLY -> TRACED -> EVIDENCE_BACKED`.
> These are descriptive research-maturity labels, not promotion states. A spark can inspire a new
> separately validated seed; it can never be mutated into one or counted as a candidate. Such a
> seed may carry `origin_hypothesis_id` only as lineage: the ID must exist and its origin crux must
> match, while the seed still passes same-agent + same-round + same-crux evidence admission.
> When comparable non-negative upside/downside magnitudes are explicitly supplied, the exploration
> ledger may compute `downside / (upside + downside)` as a break-even success threshold. It does not
> estimate success probability, expected return, target price, direction, or position size; missing
> inputs remain `UNKNOWN`.
> Introduced in v0.10 and retained in v0.13.0, expiry and falsifier remain explicit audit fields;
> the runtime does not silently invent a terminal state, delete a hypothesis, or promote it on
> their basis.
> Read `references/hypothesis-protocol.md` before changing the exploration ledger, role payloads,
> maturity transitions, proxy evidence, priority heuristic, or report projection.
> `OPPORTUNITY_DISCOVERY` and `HYBRID` frames must use the entity-agnostic 5–7 path Landscape Map in
> `references/landscape-map-protocol.md`. Both research roles must probe every path; any `UNPROBED`
> path blocks convergence and `EDGE_FOUND`. Every mapped OpportunitySeed must bind the matching
> `landscape_path_id` and `origin_crux`.
> `UNIVERSE_SEARCH` is coverage-convergent, not direction-convergent: after every path is probed by
> both roles, every crux has valid evidence anchors, the adversary is dry, and two consecutive
> rounds add neither a seed nor seed evidence, unresolved global cruxes become `MONITORABLE`.
> The root evidence direction remains `UNDETERMINED`; heterogeneous candidate evidence must never
> be pooled into a universe-level bull/bear call or `EDGE_FOUND`. Candidate direction, pricing, and
> investability remain per-seed CandidateScreen questions.
> A seed cannot reach `READY_FOR_SCREENING` without an observable pricing anchor, expectation gap,
> economic exposure, structured catalyst window, falsifier, and two independent source
> organizations. Only the deterministic `VERIFIED_FOR_HUMAN` state may be offered for human DRAFT
> Thesis creation; report validity, root actionability, or human rationale cannot bypass this gate.
> Read `references/pricing-gap-protocol.md` before emitting candidate pricing anchors; narrative
> claims such as “the market underestimates this” do not satisfy the structured as-of anchor gate.

> **Report integrity:** every report separates a deterministic singular `formal_action` from one
> optional `exploration_action` or null. The formal action alone may advance workflow state.
> Exploration actions are bounded information-gain tests with a hypothesis ID, source class,
> query/document cap, success condition, stop condition, and explicit authorization requirement.
> Every newly composed Decision Brief begins with the exact deterministic Facts Box; the host
> validator rejects missing, duplicated, moved, or modified box content. Legacy deterministic
> Insight Cards may retain their fixed field projection. Free narrative must still preserve
> exploration status, observation versus inference, alternative explanation, falsifier, trace, and
> evidence boundary, but it must not force those concepts into fixed headings or a fixed order.
> Neither form embeds raw role output or softens a STOP, WAIT, fuse break, CandidateScreen blocker,
> or promotion gate. The anti-template rule applies to free narrative, not deterministic status
> icons or compatibility renderers. Read `references/report-contract.md`.

> **CandidateScreen integrity:** screen only after root-thesis convergence. Run
> `agents/candidate_analyst.md` and `agents/candidate_skeptic.md` in isolated contexts on the
> same seed packet and as-of date. Each dimension is SUPPORTED or REJECTED only when both agents
> agree with fresh evidence from independent source organizations; disagreements remain CONTESTED.
> `THESIS_CANDIDATE` first creates `DRAFT_REQUIRES_SOURCE_VERIFICATION`. After snapshot-bound
> claim verification it may become `DRAFT_REQUIRES_HUMAN`. A human must start a fresh
> `-deepthink2` topic, which inherits no support score or verdict. Read
> `references/candidate-screen-protocol.md` before screening.
> For `UNIVERSE_SEARCH` and `COMPARATIVE`, the first unscreened deterministic Top-3 batch is the
> default continuation, not an optional appendix. Zero screenable candidates is a valid result.
> Additional batches require an explicit `--screen`; do not inflate the batch merely to produce
> more names.
> IANA example/test hosts, localhost, and loopback URLs are invalid evidence even when they contain
> a path. Google/Vertex/Bing grounding redirect wrappers are also invalid: resolve and store the
> publisher's final URL. Source-organization diversity is derived from publisher domains, not agent-written
> `source` labels. A `--screen-isolation verified` claim is not proof. `THESIS_CANDIDATE` requires
> a validated `candidate-screen-isolation.v1` receipt binding the stored dispatch, exact role
> prompts and exact submitted payloads. Antigravity receipts require distinct process IDs,
> distinct invocation IDs, and successful exits. Codex collaboration receipts require two
> completed independent agent contexts with distinct host-returned canonical agent IDs and
> distinct invocation IDs. Without a valid receipt the screen remains at most `WATCHLIST`, even
> when the caller claims verified isolation. Antigravity users should run
> `scripts/agy_candidate_screen_runner.py` rather than manually submitting two role payloads. Tool permission bypass is never implicit: add
> `--allow-agent-tools` only when the caller has explicitly authorized non-interactive agent tools.
> Both screen roles use cheap-first order: economic exposure, expectation gap, tradability, and
> catalyst first. A NO or UNKNOWN core answer stops expanded research for that seed; the role still
> returns all eight dimensions and marks unresearched fields UNKNOWN. Missing work never becomes YES.

> **Candidate maturation integrity:** after convergence, an `EVIDENCE_BACKED` lead may receive one
> deterministic, content-addressed CandidateGapTask per entity path. The original seed contract and
> evidence are immutable; every aligned, contradicted, and not-aligned attempt is appended with a
> four-search budget. Only independently published `SUPPORTED` evidence bound to a `COMPLETED`
> resolution may enter the effective-seed projection. A contradiction, `SOURCE_EXHAUSTED`, or
> `WAITING_EVENT` is terminal and cannot be hidden by automatic replanning. Read
> `references/candidate-maturation-protocol.md` before continuing a blocked candidate.

> **Source-content integrity:** capture each decisive URL with `scripts/evidence_snapshot.py`
> or an equivalent host fetcher, then run `agents/claim_verifier.md` independently. SUPPORTS and
> CONTRADICTS require a short exact span that physically occurs in the content-hashed snapshot;
> tampered hashes and invented quotes are rejected. Full page bodies are not persisted in state.
> `VERIFIED` means claim-to-snapshot alignment, not that the publisher or claim is objectively true.
> Read `references/claim-verification-protocol.md` before verification.

For method evaluation, read `references/benchmark-protocol.md`, run
`scripts/benchmark_current.py --check`, and use only the suites resolved from
`benchmarks/current.json`. If it returns `UNBENCHMARKED_METHOD_CHANGE`, the
resolved suites are controls for `last_calibrated_method_identity`, not
effectiveness evidence for the operational method. Never infer the current arm
from a filename or the latest Git commit.
Never expose blind assessments, expected paths, or post-as-of outcomes to a research role, and never
let a research result score itself. Insight validity, causal-path validity, and exploration-trace
completeness may be benchmarked alongside hypothesis-laundering and formal/exploration-action
confusion. These are reasoning, lineage, and report-usability metrics—not alpha, expected return,
full-universe discovery recall, or permission to lower a promotion gate.

When handing a state to `tradenothing-next`, read `references/project-handoff-protocol.md` and use
`scripts/project_handoff.py --check` before export. Never hand the product a Markdown conclusion,
raw role transcripts, an unverified JSON copy, or a historical state repaired after the fact.
Lesson selection remains a separate human action in the product.
Every new deepthink2 run pins a deterministic `method_identity` over the operational skill bundle
and an explicit `run_purpose` before research begins. Resume fails closed after method drift, and
project-handoff v4 refuses samples without that identity or purpose and preserves candidate-gap
histories. Older importers must reject v4 instead of dropping those fields. Only
`PRODUCTION_RESEARCH` is eligible for the product effectiveness cohort.

**Data tiers (取数分层):** Tier-2 = WebSearch (the sub-agents' primary qualitative engine — broad,
robust, carries URLs that flow into the ledger/References). Tier-1 = `scripts/tier1_providers.py`
(no-key, citable hard anchors): `--fred DGS10` (macro), `--edgar NVDA --form 10-K` (US filings),
`--comtrade 156 0 854143 2023` (trade by HS). The dead DDG-regex `verified_crawler` is superseded.

---

## 3. Toolbox Quick Reference (工具箱速查)

```bash
# Run deepthink research via orchestrator
python3 scripts/deepthink_orchestrator.py --run --topic "Topic Name"

# Initialize deepthink and extract Evolution.md memory injection
python3 scripts/deepthink_pipeline.py --extract --topic "Topic Name"

# Run macro water temperature & logic radar
python3 scripts/logic_radar_v2.py

# Dispatch and submit two-sided OpportunitySeed screens
python3 scripts/deepthink_orchestrator_v2.py --screen --topic "Topic Name" --as-of "YYYY-MM-DD"
# Gap-directed WATCHLIST rescreen: explicit seed and a strictly later as-of are mandatory.
python3 scripts/deepthink_orchestrator_v2.py --screen --topic "Topic Name" \
  --seed-id "OS-..." --as-of "YYYY-MM-DD"

# Plan and execute one bounded post-convergence CandidateGapTask
python3 scripts/deepthink_orchestrator_v2.py --plan-candidate-gaps --topic "Topic Name"
python3 scripts/deepthink_orchestrator_v2.py --submit-gap-evidence --topic "Topic Name" \
  --task-id "CGT-..." --supplement '<json>'

# Antigravity: execute both screen roles in distinct OS processes and submit a bound receipt
python3 scripts/agy_candidate_screen_runner.py --topic "Topic Name" --as-of "YYYY-MM-DD"
# Add --allow-agent-tools only after explicit authorization for non-interactive agy tool access.
python3 scripts/deepthink_orchestrator_v2.py --submit-screen --topic "Topic Name" --as-of "YYYY-MM-DD" \
  --screen-isolation verified --analyst '<json>' --skeptic '<json>'

# Preserve value after an unconverged fuse without weakening the formal report gate
python3 scripts/deepthink_orchestrator_v2.py --resolution-memo --topic "Topic Name"
python3 scripts/deepthink_orchestrator_v2.py --resume-blocked --topic "Topic Name" --extra-rounds 3

# Snapshot-bound claim verification for THESIS_CANDIDATE
python3 scripts/deepthink_orchestrator_v2.py --verification-plan --topic "Topic Name"
python3 scripts/evidence_snapshot.py --url "SPECIFIC_URL" --output snapshots.json
python3 scripts/deepthink_orchestrator_v2.py --verify-claims --topic "Topic Name" --snapshots snapshots.json
python3 scripts/deepthink_orchestrator_v2.py --submit-verification --topic "Topic Name" \
  --snapshots snapshots.json --verifier '<json>' --verifier-isolation verified

# Create/adopt immutable run identity for low-level manual orchestration
python3 scripts/deepthink_orchestrator_v2.py --create-run --topic "Topic Name" \
  --run-purpose PRODUCTION_RESEARCH
python3 scripts/deepthink_orchestrator_v2.py --adopt-run --state-path "/.../v2_state.json"
# Thereafter replace --topic with --run-id RUN-... on low-level commands.

# Consensus distance calculation
python3 scripts/consensus_distance.py --code 300118 --target 12.5

# Generate institutional-grade formula-driven DCF Excel model
python3 scripts/excel_model_builder.py --code 300118 --name "Target Co" --price 10.5 --shares 1140 --net-debt 4500

# A-share real-time quotes (via data_providers.py gateway)
python3 -c "from scripts.data_providers import GLOBAL_DATA_GATEWAY; print(GLOBAL_DATA_GATEWAY.fetch_price('300118'))"

# All macro indicators (Oil, Treasury, VIX, CNY, Gold)
python3 scripts/verified_fetcher.py --all

# Catalyst event calendar
python3 scripts/catalyst_calendar.py --sector solar --macro

# Harvest unresolved attacks → local Issues only (default has no external side effect)
python3 scripts/deepthink_pipeline.py --harvest --topic "Topic Name"

# Explicit opt-in to notifications
python3 scripts/deepthink_pipeline.py --harvest --topic "Topic Name" --notify --webhook

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

When `TRADE_NOTHING_EVOLUTION_PATH` is unset, resolve the first non-empty file from the skill-local
memory, `<TRADE_NOTHING_VAULT_DIR>/Methodology/Evolution.md`, then
`~/Documents/Trade_Nothing_Vault/Methodology/Evolution.md`. Runtime memory is never installed or
copied with the skill.

---

*Trade Nothing v0.13.0 — Hunt Alpha, Not Consensus.*
*Adversarial multi-agent architecture with full lifecycle negative feedback loops.*


## 5. Core Safety Guardrails (核心安全护栏与逻辑红线)

> [!IMPORTANT]
> **【逻辑诚实与数学一致性公理】**：
> 1. **v2 支持度只能读取 `crux_engine.py` 生成的状态；它不是统计概率，不得用于 Kelly、目标价、收益率或仓位。**
> 2. **没有具体 URL、来源与日期的数字不得进入评分；重复的 URL+claim+number 不得重复计分。**
> 3. **`continue` 或 `fuse_break` 都禁止生成正式报告；必须如实呈报未收敛 crux。**
> 4. **外部提醒和 webhook 默认关闭，只有用户或宿主显式传入 `--notify` / `--webhook` 才可触发。**
> 5. **Legacy v1 的 LFI/AFI/EGI/后验只能作为未校准历史启发式展示，不得包装成真实胜率。**
> 6. **CandidateScreen 分歧不得取平均；THESIS_CANDIDATE 必须先完成来源内容对齐，且永远不得自动建仓或继承原命题分数。**
> 7. **THESIS_CANDIDATE 在页面快照与 claim 对齐完成前不得进入人工升级；哈希或精确片段校验失败必须保持阻塞。**
> 8. **Framer 只能内联返回 JSON；未经用户明确授权不得写入 Google Drive、云文档或自选路径。缺少前提审计、反证条件或催化窗口时，`--init` 必须返回 `frame_rejected`。**
> 9. **默认用户报告不得包含 Detective/Inquisitor/Judge 原始输出、搜索日志或写作占位符；这些只留在 state 审计层。**
> 10. **`fuse_break` 禁止正式报告和自动续跑，但必须提供非正式 Resolution Memo；扩展轮次必须由用户显式授权。**
> 11. **Framer 必须由父上下文内联执行，禁止派生子代理和搜索；任何阶段超时必须输出非正式 runtime failure memo，禁止无界等待、伪造输出或自动重试。**
> 12. **题型、逻辑图和 crux 角色决定总命题聚合方式；`NO_EDGE`、证据方向与可行动性必须分开，禁止恢复 `NO_EDGE / AVOID`。**
> 13. **报告合法、根问题 `READY_FOR_SCREENING` 与候选可升级是三件事；只有候选级 `VERIFIED_FOR_HUMAN` 可以进入人工 DRAFT Thesis。**
> 14. **`wild_hypotheses`、`hypothesis_sparks`、`proxy_trails` 与 `HYPOTHESIS_ONLY` 永远不得进入 Judge 评分、来源计数、收敛或晋级；但不得因证据尚弱而从探索账本静默删除。**
> 15. **`research_intent` 必须独立于题型声明；`OPPORTUNITY_DISCOVERY` / `HYBRID` 必须先生成 5–7 个实体无关假说，`THESIS_CHALLENGE` 才可省略。**
> 16. **报告必须物理区分唯一正式动作与可选探索动作；探索动作只用于经人明确授权的有界求证，不能绕过 fuse、CandidateScreen、快照核验或人工闸门。**
> 17. **Inquisitor 必须同时构造 bull surprise、base、bear failure 路径；不得预设固定暴跌幅度、底价、目标价或伪概率来制造红队强度。**
