# ARCHIVED: Trade Nothing v0.12 全链路流程审计

> 历史审计材料；不属于 v0.13 发布 skill 的现行方法契约。

> 审计日期: 2026-08-04 | 审计范围: `~/.claude/skills/trade-nothing/` | 基于"中国AI算力中心"6轮实战产出

---

## 一、总览图

```
┌─────────────────────────────────────────────────────────────────────┐
│  Phase 0: --frame                                                  │
│  父上下文内联执行 framer.md (DEEP, 无搜索, 无子代理)                 │
│  IN:  topic 字符串                                                  │
│  OUT: JSON { decision_question, question_type, logic_graph,          │
│             horizon, as_of_date, unit_of_analysis, thesis_seed,       │
│             premise_audit, 2-5 candidate_cruxes (每条带               │
│             logic_role/monitor_anchor/falsifier/evidence_plan/        │
│             catalyst_window), no_edge_precheck,                       │
│             hypothesis_garden (OPPORTUNITY_DISCOVERY/HYBRID时5-7条),  │
│             forbidden_consensus, suggested_max_rounds }               │
│                                                                       │
│  ⚠️ 校验闸: _validate_frame() — 前提缺URL、crux缺反证、              │
│    催化剂不在视界内→ frame_rejected                                   │
│  ⚠️ is_researchable=false → NO_EDGE 直接终止                         │
├─────────────────────────────────────────────────────────────────────┤
│  Phase 1: --init --frame-json '{...}'                               │
│  IN:  Framer JSON                                                    │
│  ENGINE WORK:                                                        │
│    1. crux_engine.new_state() → 创建 state (cruxes/rounds/config)    │
│    2. hypothesis_engine.initialize() → 初始化 hypothesis_ledger      │
│    3. landscape_engine.initialize() → 初始化 landscape_map           │
│    4. _bind_hypotheses_to_landscape() → WH↔路径 绑定                │
│    5. dispatch_prompts(state, round=1) → 生成3份prompt               │
│  OUT: { status: "dispatch_subagents", round: 1,                      │
│          detective_prompt, inquisitor_prompt, judge_prompt,           │
│          open_cruxes, dispatch_cruxes, landscape_assignments }        │
│  STATE: → 写入 _v2_state.json (CAS revision gate)                    │
├─────────────────────────────────────────────────────────────────────┤
│  Phase 2: 对抗辩论循环 (Rounds 1..N)                                 │
│                                                                       │
│  ┌─ 2a. DISPATCH (每轮) ────────────────────────────────────────┐   │
│  │ 宿主隔离派发:                                                  │   │
│  │  Detective (DEEP) ← detective_prompt (crux限定)                │   │
│  │  Inquisitor (DEEP) ← inquisitor_prompt (crux限定)              │   │
│  │  每个agent每轮: ≤ 2*|crux|次搜索/crux, ≤3 seeds, ≤3 sparks    │   │
│  │  IN:  prompt(含OPEN crux context, 负面先验, 证据路线)           │   │
│  │  OUT: JSON { crux_evidence/crux_attacks, opportunity_seeds,     │   │
│  │              hypothesis_sparks, proxy_trails, landscape_findings │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌─ 2b. JUDGE (每轮, DEEP) ─────────────────────────────────────┐   │
│  │ 宿主派发 Judge ← judge_prompt (忽略探索对象)                    │   │
│  │ IN:  Detective JSON + Inquisitor JSON + OPEN crux列表           │   │
│  │ OUT: JSON { crux_signals: { Cx: { signal∈[-1,1], rationale,    │   │
│  │        citations[], best_bull, best_bear } }, new_cruxes[] }     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌─ 2c. --submit --det '...' --inq '...' --judge '...' ─────────┐   │
│  │ ENGINE WORK (cmd_submit):                                        │   │
│  │  a. _sanitize_judge_for_agent_support() — 剔除无agent证据的signal│
│  │  b. _round_policy() — 决定dispatch/open/free_roam/新crux策略    │
│  │  c. _admit_new_cruxes() — 入队新crux(需Inquisitor攻击+引用)      │
│  │  d. _enforce_round_scope() — 越界signal→0                        │
│  │  e. landscape_engine.ingest_round() — 路径覆盖摄入              │
│  │  f. hypothesis_engine.ingest_round() — 假说/Proxy摄入            │
│  │  g. opportunity_engine.harvest_round() — 收割OpportunitySeed     │
│  │  h. tracking_engine.sync_tracking_ledger() — 赔率轨同步 ⭐v0.12  │
│  │  i. crux_engine.submit_round() — 辩论支持度更新+收敛判定        │
│  │  j. opportunity_engine.refresh_candidate_states() — 刷新候选状态 │
│  │  k. _save() → 物理写入state                                      │
│  │                                                                   │
│  │  OUT:                                                            │
│  │   converge → ready_for_report 或 dispatch_candidate_screeners     │
│  │   continue → dispatch_subagents (返回新一轮prompts)               │
│  │   fuse_break → blocked_max_rounds (Resolution Memo)               │
│  └──────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│  Phase 3: Candidate Maturation (后收敛)                              │
│                                                                       │
│  ┌─ 3a. --plan-candidate-gaps ───────────────────────────────────┐   │
│  │ 候选补证: 为EVIDENCE_BACKED候选生成bounded task                  │
│  │ IN: state (blocked seeds)                                        │
│  │ OUT: CandidateGapTask[] (每个含target_claim/search_budget)       │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌─ 3b. --submit-gap-evidence ───────────────────────────────────┐   │
│  │ 提交补证结果; 成功则候选可能→READY_FOR_SCREENING                  │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌─ 3c. --screen ───────────────────────────────────────────────┐   │
│  │ 派发 Candidate Analyst + Candidate Skeptic (隔离, 最多3个候选) │
│  │ IN: seed packet (含 economic_exposure/expectation_gap/          │
│  │     pricing_anchor/catalyst/falsifier/evidence)                  │
│  │ OUT: 8维双边评分矩阵 { ECONOMIC_EXPOSURE, EXPECTATION_GAP,       │
│  │     VALUATION_CONTEXT, TRADABILITY, GOVERNANCE, CROWDING,        │
│  │     CATALYST, FALSIFIER } × { analyst, skeptic }                 │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌─ 3d. --submit-screen ────────────────────────────────────────┐   │
│  │ 双边表决: SUPPORTED(双方YES) / REJECTED(双方NO) / CONTESTED    │
│  │ → WATCHLIST / THESIS_CANDIDATE / REJECTED                       │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌─ 3e. Claim Verification ─────────────────────────────────────┐   │
│  │ --verification-plan → --verify-claims → --submit-verification   │
│  │ 页面快照+精确片段对齐; THESIS_CANDIDATE → VERIFIED_FOR_HUMAN    │
│  └──────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│  Phase 4: --report                                                  │
│  ENGINE WORK:                                                       │
│    1. 校验: converge=true, landscape coverage complete,              │
│       evidence gate (每条crux ≥2个独立来源URL)                      │
│    2. build_report_view_model(state) → 结构化view                   │
│    3. render_facts_box() → 嵌入Decision Brief顶部的锁定事实          │
│    4. _render_audit() → Evidence Ledger                             │
│    5. _render_candidate_cards() → Candidate Cards                    │
│  OUT: { facts_box_markdown, evidence_ledger_markdown,                │
│          candidate_cards_markdown, report_view_model }                │
│                                                                       │
│  LLM工作(父上下文):                                                  │
│    - 原样嵌入facts_box_markdown                                      │
│    - 基于view_model写≤120行叙事(Decision Brief)                      │
│    - 严禁修改数值/状态词/crux内容/候选计数/正式动作                  │
├─────────────────────────────────────────────────────────────────────┤
│  Phase 3.7: Tracking Track (赔率轨) ⭐v0.12 每轮自动运行             │
│                                                                       │
│  ┌─ tracking_engine.sync_tracking_ledger() ──────────────────────┐   │
│  │ 每轮submit后自动执行:                                            │
│  │  a. 遍历所有 opportunity_seeds                                    │
│  │  b. tracking_assessment(): 阻塞且赔率实质+链≥3+检查点→ACTIVE     │
│  │  c. 已有ACTIVE的seed: 检查是否升级到正式轨(→ESCALATED)           │
│  │     或已被筛选否决(→CLOSED)                                      │
│  │  d. 从Inquisitor payload提取failure_signal                       │
│  │  e. 写入 state["tracking_ledger"]                                 │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  报告渲染: tracking_engine.active_tracked(state) → 跟踪清单表         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、各节点详细输入/输出

### 2.1 Framer (--frame, 父上下文内联)

| 属性 | 内容 |
|------|------|
| **执行位置** | 父上下文inline (严禁子代理/搜索) |
| **超时** | 120s |
| **模型** | DEEP (framer.md) |
| **输入** | topic字符串 + 可选start_packet |
| **输出** | JSON (见下schema) |

**核心输出字段:**
```
decision_question    → 待决策问题的精确表述
question_type        → CONJUNCTIVE|DISJUNCTIVE|CAUSAL_CHAIN|COMPARATIVE|UNIVERSE_SEARCH
research_intent      → THESIS_CHALLENGE|OPPORTUNITY_DISCOVERY|HYBRID
logic_graph          → { root_id, nodes[{id,node_type,label}], edges[{from,to,relation}] }
horizon              → 3-6M (或其他)
as_of_date           → ISO date (证据截止日)
forecast_target_date → 未来预测目标日(可选)
unit_of_analysis     → 分析单元
thesis_seed          → 一句话非共识种子
premise_audit[]      → { id, claim, status(HYPOTHESIS|URL_CLAIMED_UNVERIFIED), as_of, source_url, required_primary_source, use }
candidate_cruxes[2-5]→ { id, label, logic_role, definition, monitor_anchor, falsifier, evidence_plan[], catalyst_window }
  evidence_plan[]    → { plan_id, publisher_class, target_claim, search_query }
  catalyst_window    → { event, expected_by(ISO), date_status, basis_claim_id }
hypothesis_garden[5-7]→ (OPPORTUNITY_DISCOVERY/HYBRID时) WildHypothesis[]
forbidden_consensus[] → 禁止辩论的平庸共识
no_edge_precheck     → { is_researchable(bool), basis_type, basis_claim_ids[], reason }
suggested_max_rounds → 建议最大轮次
```

**校验闸门 (_validate_frame):**
- 缺少decision_question/horizon/as_of_date → frame_rejected
- premise_audit为空/缺失 → frame_rejected
- URL_CLAIMED_UNVERIFIED状态但缺concrete URL → frame_rejected
- candidate_cruxes不在2-5个 → frame_rejected
- 每条crux缺monitor_anchor/falsifier/catalyst → frame_rejected
- catalyst不在3-6M视界内 → frame_rejected
- no_edge_precheck.basis_claim_ids未覆盖所有catalyst → frame_rejected
- logic_graph节点不连通/relation不匹配 → frame_rejected
- UNIVERSE_SEARCH缺OPPORTUNITY_PATH+PRICING crux → frame_rejected
- 时间语义合同违规 → frame_rejected

---

### 2.2 Init (--init, 创建状态机)

| 属性 | 内容 |
|------|------|
| **执行位置** | Python脚本 (deepthink_orchestrator_v2.py) |
| **输入** | Framer JSON + --runtime-isolation |
| **输出** | dispatch_subagents + 3份prompt |

**状态机构建流程:**
```
1. crux_engine.new_state(topic, question, horizon, cruxes)
   → state = { topic, decision_question, horizon, question_type, logic_graph,
               cruxes: { Cx: { status:"PENDING", retired:false, p_history:[0.5],
                               citations:[], seen_evidence_keys:[], best_bull/bear:null } },
               rounds: [], decision_trace: [], config: {MAX_ROUNDS, K, DECAY...} }

2. state["hypothesis_ledger"] = hypothesis_engine.initialize(frame)
   → { hypotheses: [{ hypothesis_id:"WH-...", hypothesis, state:"HYPOTHESIS_ONLY",
                      causal_chain[], scenario_paths{}, asymmetry_case{}, ... }] }

3. state["landscape_map"] = landscape_engine.initialize(frame)
   → { paths: [{ path_id, archetype, linked_crux_id, hypothesis, state:"UNPROBED" }] }

4. _bind_hypotheses_to_landscape()
   → hypothesis.context.landscape_path_ids ← path_id
   → path.hypothesis_id ← matching hypothesis

5. dispatch_prompts(state, round=1)
   → { detective_prompt, inquisitor_prompt, judge_prompt,
       open_cruxes[], dispatch_cruxes[], landscape_assignments{} }
```

---

### 2.3 每轮辩论 (Rounds 1..N)

#### 2.3a 侦探 (Detective, DEEP)

**Prompt结构:**
```
[Detective · detective.md · model=deep] Round N
决策问题: ... | 视野: ... | as-of: ...
分析单元: ... | 立题事实状态: PROVISIONAL_UNVERIFIED
立题前提账本: [...]
本轮重点质证以下OPEN crux: [C1-C4]
已收敛crux上下文: [...]
历史负面先验: [...]
平庸共识禁区: [...]
🔗 产业链检查（按需）
💎 OpportunitySeed 收割（max 3）
✨ 假说探索轨（max 3 sparks + 3 trails）
🗺 Landscape Map 路径质证（硬分配）
🧮 有界研究预算（硬上限）
🎯 本轮调度契约: free_roam=false, new_cruxes_allowed=true
硬约束: 每个数据点必须带来源+具体URL+日期
```

**输出JSON:**
```json
{
  "round": 1,
  "market_consensus": "...",
  "variant_perception": "...",
  "bull_thesis": "...",
  "crux_evidence": [{
    "crux_id": "C1",
    "claim": "...",
    "evidence": [{
      "claim": "...", "number": "...", "source": "组织名",
      "url": "https://...", "date": "2026-07-01", "source_tier": "primary"
    }]
  }],
  "opportunity_seeds": [{
    "candidate": "公司/路径名",
    "relation_type": "BOTTLENECK_OWNER",
    "origin_crux": "C1",
    "origin_hypothesis_id": "WH-...",
    "landscape_path_id": "LP-...",
    "causal_path": "...→...→...",
    "economic_exposure": "...",
    "why_market_may_miss": "...",
    "pricing_anchor": { "type": "...", "as_of": "...", "metric": "...", "current_value": "..." },
    "catalyst": "...",
    "falsifier": "...",
    "asymmetry_case": { "upside_shape": "...", "convexity": "...", "downside_shape": "...", "time_to_signal": "...", "basis": "..." },
    "scenario_paths": { "bull": "...", "base": "...", "bear": "..." },
    "causal_chain": ["节点1", "节点2", "节点3"],
    "payoff": { "upside": "100%", "downside": "30%", "unit": "PCT_RETURN" },
    "evidence": [/* 逐字复用本agent本轮同crux的结构化证据 */]
  }],
  "hypothesis_sparks": [{
    "spark_id": "...", "hypothesis": "...", "causal_chain": [...],
    "strongest_alternative_explanation": "...",
    "cheap_discriminating_test": "...",
    "state": "HYPOTHESIS_ONLY"
  }],
  "proxy_trails": [{
    "proxy_id": "...", "hypothesis_id": "...", "direction": "SUPPORTS",
    "proxy": "...", "alternative_explanation": "...", "evidence": [...]
  }],
  "landscape_findings": [{
    "path_id": "LP-...", "linked_crux_id": "C1",
    "state": "SUPPORTED", "finding": "...", "evidence": [...]
  }],
  "supply_chain_map": "..."
}
```

#### 2.3b 审问者 (Inquisitor, DEEP)

**Prompt结构:** 同Detective的common部分 + Inquisitor特有指令(free-roam名额/新crux申请/odds_calibration)

**输出JSON额外字段:**
```json
{
  "crux_attacks": [{
    "crux_id": "C1",
    "attacks": [{ "claim": "...", "evidence": [...] }]
  }],
  "premortem_death_path": { "trigger": "...", "transmission": "...", "monitor": "..." },
  "lethal_attack_vectors": [...],
  "recommended_kill_switch": {...},
  "new_attack_dimension_this_round": "...",
  // OpportunitySeeds 含 odds_calibration:
  "opportunity_seeds": [{
    "...": "...",
    "odds_calibration": {
      "success_enablers": "路径成功的前提条件",
      "primary_failure_mode": "最可能的失败方式",
      "failure_signal": "观察到什么信号就放弃跟踪"
    }
  }]
}
```

#### 2.3c 法官 (Judge, DEEP)

**输入:** Detective JSON + Inquisitor JSON + OPEN crux列表

**输出JSON:**
```json
{
  "round": 1,
  "crux_signals": {
    "C1": {
      "signal": 0.5,
      "rationale": "Bull cited 京算利用率80%+ with concrete URL, Bear responded with 信通院用算占比",
      "citations": [{
        "claim": "...", "number": "80%", "source": "人民网",
        "url": "http://...", "date": "2026-07-06"
      }],
      "best_bull": "京算Token工厂利用率30-40%→80%+",
      "best_bear": "信通院用算占比36.8%"
    }
  },
  "new_cruxes": [{
    "id": "C5", "label": "...", "logic_role": "THESIS_HINGE",
    "source_attack_crux_id": "C1",
    "supporting_citation": { /* 逐字复制自Inquisitor本轮的crux_attacks */ },
    "definition": "...", "monitor_anchor": "...", "falsifier": "...",
    "catalyst_window": { "event": "...", "expected_by": "2026-10-31", ... }
  }]
}
```

**引擎侧处理 (cmd_submit):**

| 步骤 | 函数 | 输入 | 输出 | 写入state |
|------|------|------|------|-----------|
| signal净化 | `_sanitize_judge_for_agent_support()` | judge, det, inq | 剔除无agent证据的signal/引用 | - |
| 轮次策略 | `_round_policy()` | state, round_num | {open_cruxes, dispatch_cruxes, free_roam_allowed, new_cruxes_allowed} | - |
| 新crux入队 | `_admit_new_cruxes()` | state, judge.new_cruxes, policy, inq | admitted_ids[], deferred[] | cruxes[C5], logic_graph |
| 范围约束 | `_enforce_round_scope()` | judge, state, policy | allowed_scored_cruxes[] | - |
| Landscape摄入 | `landscape_engine.ingest_round()` | state, round, det, inq | audit | landscape_map paths state |
| 假说摄入 | `hypothesis_engine.ingest_round()` | state, round, det, inq | audit | hypothesis_ledger |
| 场景路径 | `hypothesis_engine.ingest_scenario_paths()` | state, round, inq | audit | scenario_path_ledger |
| 种子收割 | `opportunity_engine.harvest_round()` | state, round, det, inq | harvest audit | opportunity_seeds[] |
| **赔率轨** | `tracking_engine.sync_tracking_ledger()` | state, round, inq | ledger | **tracking_ledger{}** |
| 支持度更新 | `crux_engine.submit_round()` | state, round, signals | convergence decision | cruxes p_history, decision_trace |
| 候选刷新 | `opportunity_engine.refresh_candidate_states()` | state | - | - |
| 持久化 | `_save()` | topic, state | - | _v2_state.json |

---

### 2.4 报告产出 (--report)

**输入:** 收敛状态 + challenge_only标志 + report_view

**报告闸门 (任一不通过则阻断):**
1. `last_convergence.decision != "converge"` → blocked_unconverged
2. landscape有UNPROBED路径 → blocked_landscape_coverage
3. 任一条crux不足2个独立来源URL → blocked_evidence_gate
4. 机会型研究有READY_FOR_SCREENING候选未筛选 → 自动dispatch CandidateScreen

**确定性产物 (脚本物理生成):**

| 产物 | 内容 | 行数控制 |
|------|------|---------|
| `facts_box_markdown` | Edge状态/方向/可行动性, crux表格, 候选计数/状态, 正式动作, 探索动作 | ~40行 |
| `evidence_ledger_markdown` | 完整证明账本 + 引用列表 + 探索记录 + 候选矩阵 | 无固定上限 |
| `candidate_cards_markdown` | 跟踪清单表 + 研究管线表 + 每个候选的5段式卡片 | 每个候选~40行 |
| `report_view_model` | 结构化JSON(所有数值/状态/卡片) | n/a |

**LLM叙事层 (父上下文):**
- 原样嵌入facts_box_markdown
- 基于view_model写Decision Brief: 标题(反映核心发现) + 2-4条洞见 + 对称场景 + 观察清单
- ≤120行叙事 + ≤150行总Brief
- 数值/状态词/crux行/候选计数/正式动作不得修改
- 引用只能来自结构化输入, 内联标注 `[来源, 日期](URL)`

---

## 三、v0.12 赔率轨 (Tracking Track) 专节

### 3.1 触发时机
`cmd_submit()` → 每轮 `harvest_round` 之后、`submit_round` 之前，无条件调用 `tracking_engine.sync_tracking_ledger(state, round_num, odds_payload=inquisitor)`

### 3.2 准入条件 (fail-open)
```
tracking_assessment():
  ✓ seed_id 存在
  ✓ 不是 REJECTED
  ✓ 未达 READY/WATCHLIST/THESIS_CANDIDATE/VERIFIED_FOR_HUMAN (即仍在阻塞状态)
  ✓ odds_summary(seed) 非空 (asymmetry_case.basis 已声明)
  ✓ 因果链 ≥ 3 个节点
  ✓ catalyst + falsifier 都非空 (升级/放弃检查点)
```

### 3.3 状态机
```
ACTIVE ──seed升级至正式轨──→ ESCALATED
ACTIVE ──seed被筛选否决──→ CLOSED (close_reason="rejected_by_screen")
```

### 3.4 输入输出

| 环节 | 输入 | 输出 |
|------|------|------|
| 准入判断 | seed(state) | { admitted: bool, reasons: [] } |
| 失败信号 | Inquisitor.opportunity_seeds[].odds_calibration.failure_signal (按candidate名称匹配) | entry["failure_signal"] |
| 账本同步 | state.opportunity_seeds, state.tracking_ledger | 新ACTIVE / ESCALATED / CLOSED |
| 报告渲染 | state.tracking_ledger (ACTIVE条目) + seed(path_analysis) + seed(odds_summary) | 表格行: 候选/赔率姿态/检查点升级/检查点放弃/失败信号/下一动作 |

### 3.5 关键约束
- **跟踪 ≠ 推荐**: 不改变crux评分/收敛/筛选/晋级
- **证据轨保持fail-closed**: 跟踪轨只是让阻塞种子"可见但不晋级"
- **赔率姿态来自hypothesis继承**: 种子继承链接WildHypothesis的asymmetry_case/scenario_paths/causal_chain/payoff

---

## 四、审计发现

### 🔴 严重问题

#### A1. 赔率轨的失效模式: 依赖假设花园先建立

**问题:** 跟踪轨道的准入依赖 `odds_summary(seed)` 非空 → 需要 `asymmetry_case.basis` → 来自链接的 WildHypothesis。但如果 Framer 生成的 WildHypothesis 没有声明 `asymmetry_case.basis`，或者 seed 没有正确链接 `origin_hypothesis_id`，所有阻塞种子都可能进不了跟踪清单。

**证据:** 本次"算力中心"运行的6个候选全部卡在 `insufficient_independent_seed_sources`，且全部出现在跟踪清单中，说明当前框架下 hypothesis→seed 继承链路是 work 的。但这是脆弱耦合——如果 Detective/Inquisitor 提交的 seed 没有带 `origin_hypothesis_id`，或者 hypothesis_ledger 中没有匹配条目，整个跟踪轨就静默失效。

**建议:** 在 `tracking_assessment()` 中增加降级路径：如果无法从 hypothesis 继承 odds，允许 seed 自身携带 `asymmetry_case` 声明（seed schema 已经支持），并在准入日志中区分 `odds_from_hypothesis` vs `odds_from_seed_declared`。

#### A2. 失败信号匹配依赖候选名称的字符串精确匹配

**问题:** `_failure_signals_from_payload()` 用 `opportunity_engine._text(raw.get("candidate"))` 做名称匹配。Inquisitor 提交的 seed 中 candidate 名称必须与先前 Detective 提交的 seed 完全一致（经过 `_text()` 归一化后），否则 failure_signal 就会丢失。

**代码位置:** `tracking_engine.py:106-116`
```python
signals[name] = signal  # name来自Inquisitor seed, 匹配ledger entry的candidate
```

**风险:** 如果 Inquisitor 改写了 candidate 名称（例如 "中际旭创" vs "中际旭创(300308)"），信号就会静默丢失，没有任何警告。

**建议:** 至少增加 fuzzy match 警告日志，或者用 seed_id 做精确关联而非 candidate 名称。

#### A3. `submit_round` 在 tracking sync 之后才更新

**问题:** `cmd_submit()` 中的执行顺序是:
```python
harvest = opportunity_engine.harvest_round(...)     # 1. 收割新seed
tracking_engine.sync_tracking_ledger(...)             # 2. 同步跟踪账本
conv = crux_engine.submit_round(...)                  # 3. 更新crux支持度
```

如果第3步 `submit_round` 触发了某个 crux 的 RESOLVED → 这会影响 `opportunity_engine.promotion_assessment()` 的结果 → 从而影响候选的 `candidate_state`。但 tracking 已经在第2步完成了，它使用的是旧状态。这意味着在最后一轮（收敛轮），新升级的候选可能没有被 tracking ledger 及时标记为 ESCALATED。

**影响:** 同一轮内从阻塞变为可筛选的候选会延迟一轮才在跟踪清单中反映状态变化。

**建议:** 在 `submit_round` 后再跑一次 `sync_tracking_ledger`，或者在 `cmd_report` 中刷新 tracking ledger。

---

### 🟡 中等问题

#### B1. 报告渲染三层独立函数存在数据不一致风险

**问题:** `report_v2.py` 有三个独立渲染函数——`render_facts_box()`, `_render_candidate_cards()`, `_render_audit()`——它们各自独立调用 `build_report_view_model()` 或直接处理 state。虽然都使用相同的 state，但某些计算（如 `_citation_quality()`）在 `_render_audit` 中重复做了，在 `_render_candidate_cards` 中没有。

**具体:** `_render_audit` 调用 `_citation_quality(state)` 做独立的引用去重和编号，而 `render_facts_box` 用的是 `view_model` 的 `candidate_counts`。两者计算路径不同，理论上可能出现同一个候选在两个视图中显示不同状态。

**建议:** 所有渲染函数统一使用 `build_report_view_model()` 的输出，不在渲染层重复做 state 计算。

#### B2. `refresh_candidate_states` 被多次调用但不在 tracking 前

**问题:** `refresh_candidate_states` 在 `cmd_submit` 中被调用了两次（harvest_round 后 + submit_round 后），但它改变的是 `opportunity_seeds` 中的 `candidate_state` 字段。而 `tracking_engine.sync_tracking_ledger` 在两次 refresh 之间执行，使用的是 `opportunity_engine.promotion_assessment()` 的实时计算结果。

**风险:** 如果 `refresh_candidate_states` 更新的字段与 `promotion_assessment` 的计算基础相同，则行为一致；如果不同，则 tracking 可能看到不一致的候选状态。

**建议:** 将 `sync_tracking_ledger` 移到所有 refresh 之后。

#### B3. 赔率链节点拆分过于简单

**问题:** `_split_causal_path()` 用 `→`、`->`、`>` 和 `；`/`;` 拆分因果路径字符串。这在实践中可能错误拆分包含 `>` 的公司名或指标（如 "利用率>80%"）。

**代码位置:** `opportunity_engine.py` 中的拆分逻辑。

**建议:** 至少先保护括号和引号内的内容，或者优先使用 `causal_chain` 列表（不从字符串拆分）。

#### B4. UNIVERSE_SEARCH 题型没有 binding crux

**问题:** 当 `question_type == "UNIVERSE_SEARCH"` 时，`submit_round` 中的 `binding_crux` 为 `None`，报告渲染中相关行为正确（不展示binding crux行），但 `_render_audit` 的结论部分仍然显示 "约束性 crux" 的逻辑分支。实际运行中这套逻辑工作正常（本次算力中心运行就是 UNIVERSE_SEARCH 且输出了正确报告），但代码路径的测试覆盖可能不足。

---

### 🟢 轻微问题 / 改进建议

#### C1. 探索轨与正式轨的隔离是 "约定式" 而非 "强制式"

Judge prompt 要求忽略探索对象，但 Judge 是 LLM，没有物理强制。如果 Judge 错误地将 exploration evidence 当作 crux evidence 评分，`_sanitize_judge_for_agent_support()` 会尝试用 agent evidence 做 back-check，但如果 exploration 引用的恰好也是 agent 同轮提交的证据（可能），则可能漏过。

**当前缓解:** `_sanitize_judge_for_agent_support` 按 citation_identity 匹配 agent evidence，如果 exploration 对象不在 agent 的 `crux_evidence/crux_attacks` 中，其 citation 会被剔除。这提供了部分保护。

**建议:** 长期可考虑在 Judge prompt 中提供 exploration objects 的黑名单（citation identity 列表），或者让 Judge 不接收 exploration 内容。

#### C2. 跟踪账本无过期/清理机制

`CLOSED` 和 `ESCALATED` 条目永远留在 `tracking_ledger` 中不清理。对长期运行的研究 topic 这会造成 state 膨胀。

**建议:** 在 `cmd_report` 或 `_save` 中增加清理逻辑，CLOSED 超过 N 轮的条目移到 `tracking_ledger_archive`。

#### C3. Facts Box 的 "候选状态" 行可能过长

当候选数量 > 6 时，`render_facts_box` 只截取前6个（`[:6]`），但 `candidate_counts.lead_count` 仍然是总数。这可能导致用户困惑：只看到6个候选的状态描述，但总数显示更多。

**当前行为:** `_clean('；'.join(... view.get('candidate_cards', [])[:6] ...))` —— 超过6个的直接丢弃，没有任何 "另有 N 个" 的提示。

#### C4. 测试覆盖

- `test_tracking_engine.py` (9个测试) — 覆盖了准入/拒绝/同步/渲染核心路径 ✅
- `test_path_analysis.py` (6个测试) — 覆盖了链拆分/继承/赔率计算 ✅
- 但缺少: tracking 在完整 `cmd_submit` 流程中的集成测试、UNIVERSE_SEARCH 的 tracking 行为测试、多轮 tracking 状态迁移的端到端测试

---

## 五、产品哲学对标检查

### 5.1 初衷对照

| 初衷 | 当前实现 | 对齐度 |
|------|---------|--------|
| "从有限的证据里充满想象的挖掘机会" | Framer生成5-7条WildHypothesis(HYPOTHESIS_ONLY), Detective/Inquisitor每轮最多3条sparks+3条trails | ⚠️ 部分对齐: imagination在探索轨, 但正式轨的证据门仍然conservative |
| "找到一条真实确定的逻辑" | path_analysis 标记逻辑链每个节点的证据触达/待验证/待观测状态 | ⚠️ 部分对齐: 标记仅是文本重叠, 不验证逻辑有效性 |
| "赔率思维" (asymmetric payoff) | tracking track 准入要求 odds_summary 非空; 报告展示赔率姿态+break-even | ✅ 已对齐 |
| "机会发现引擎" 不是 "证据验证机器" | 双轨并行: 正式轨fail-closed + 赔率轨fail-open | ✅ 架构对齐, 但正式轨权重仍远大于赔率轨 |
| "在趋势前期充满信念拿到涨幅" | 检查点机制(catalyst+falsifier)提供时间窗口监控 | ✅ 已对齐 |

### 5.2 核心张力

**问题**: 正式轨的 fail-closed 设计(9道证据门, K=0.9, weakest-link聚合, MIN_VALID_CITATIONS=2, 2轮dry=evidence exhaustion)在统计上系统性偏向拒绝机会。赔率轨是重要的 counterbalance, 但它只是"让阻塞种子可见", 不主动生成新机会。

**缓解措施 (v0.12 already done)**:
1. 赔率轨独立于正式轨, 不被证据门影响
2. 报告先展示跟踪清单(赔率姿态), 再展示管线表(证据状态)
3. Inquisitor的 odds_calibration 将破坏性能量转化为可监控的 failure_signal

**仍存在的风险**:
- 赔率轨的准入仍依赖 odds(从hypothesis继承), 如果WildHypothesis没有声明asymmetry_case, 整条轨静默失效
- 没有"机会发现率"指标来衡量引擎是否过度拒绝
- 正式轨的 weakest-link 聚合对CONJUNCTIVE题型一票否决

### 5.3 各环节上下文审计

| 环节 | 上下文充分性 | 噪音评估 | 判定 |
|------|------------|---------|------|
| **Framer** | 只有topic字符串, 无搜索能力 | 无噪音, 但信息不足 | ⚠️ 脆弱: 依赖模型先验知识, 对细分主题可能不准确 |
| **Init** | 完整frame JSON, 全面校验 | 校验逻辑densely但必要 | ✅ 准确 |
| **Detective/Inquisitor** | ~5000 tokens prompt: 全部crux状态+证据路线+负面先验+探索指令+预算指令 | 预算/探索指令每轮重复, 占~30% token | ⚠️ 功能正确但浪费token; 探索JSON随轮次增长 |
| **Judge** | Detective+Inquisitor JSON + crux列表 | 低噪音 | ✅ 准确 |
| **cmd_submit** | 14步引擎处理 | tracking时序已修正 | ✅ 准确(修复后) |
| **cmd_report** | 收敛状态 + 闸门校验 | 渲染层有重复计算但无功能影响 | ⚠️ 可优化但非关键 |
| **LLM叙事** | facts_box(锁定) + view_model(结构化) | 低噪音 | ✅ 准确 |

### 5.4 指标校准检查

| 指标 | 当前值 | 含义 | 风险 |
|------|--------|------|------|
| K (gain) | 0.9 | 一次strong signal (±1) → ±0.9 log-odds | 2轮可推动crux从0.5→0.84, 前两轮影响过大 |
| DECAY | 0.88 | 每轮evidence-bearing update后回撤 | 适度, 防止单轮锁定 |
| L_MAX | ln(4) ≈ 1.39 | 单crux概率限幅 [0.20, 0.80] | 合理: 辩论支持度不能声称极端确定 |
| MIN_VALID_CITATIONS | 2 | crux至少需要2个独立来源URL才可retire | 合理: 防止单一来源偏见 |
| EVIDENCE_EXHAUSTION_DRY_ROUNDS | 2 | 连续2轮无新证据→MONITORABLE | ⚠️ 可能过早: 重要证据可能在第3轮才出现 |
| MIN_CHAIN_NODES | 3 | 跟踪准入最小逻辑链长度 | 合理 |
| signal分辨率 | {-1, -0.5, 0, 0.5, 1} | 5级离散 | 粗粒度但故意为之: 防止伪精度 |

---

## 六、已修复问题清单 (2026-08-04)

### P0 (时序/匹配脆弱性)
| # | 问题 | 修复 | 文件 |
|---|------|------|------|
| A3 | tracking sync 在 submit_round 之前, 收敛轮状态变化被延迟反映 | 移到 submit_round + refresh_candidate_states 之后; cmd_report 再加一次sync | `deepthink_orchestrator_v2.py:1323-1349` |
| A2 | failure_signal 按候选名称字符串匹配, Inquisitor 改写名称就丢失 | 改用 entity_identity → seed_id 精确匹配, 名称匹配仅作降级fallback | `tracking_engine.py:_failure_signals_from_payload()` |

### P1 (鲁棒性/一致性)
| # | 问题 | 修复 | 文件 |
|---|------|------|------|
| A1 | 赔率轨准入完全依赖 hypothesis→seed 继承链, 一个环节缺失就静默失效 | 增加 `_odds_fallback`: 有链≥3+检查点但无asymmetry_case的种子以"退化赔率"准入 | `tracking_engine.py:_odds_fallback()` |
| B3 | `_split_causal_path` 只用箭头做分隔符, 数字中的 `>` 可能误拆 | 增加 `;`/`；` 分隔符; 用placeholder保护数值型 `>` (如 "利用率>80%") | `opportunity_engine.py:_split_causal_path()` |
| B1 | report_v2 三个渲染函数独立处理state, 潜在不一致 | 确认 view_model 是共同数据源; 在 cmd_report 增加 pre-render tracking sync | `deepthink_orchestrator_v2.py:cmd_report` |

### P2 (可维护性/边界情况)
| # | 问题 | 修复 | 文件 |
|---|------|------|------|
| C2 | 跟踪账本 CLOSED/ESCALATED 条目永远不清理 → state膨胀 | 增加 `_prune_closed_entries`: CLOSED超过6轮的条目移到 `tracking_ledger_archive` | `tracking_engine.py:_prune_closed_entries()` |
| C3 | Facts Box 候选超过6个时静默截断, 无提示 | 增加 "另有 N 个候选（见候选卡片）" 提示 | `report_v2.py:render_facts_box()` |
| — | `_node_phrases` 最短2字符导致大量误匹配 (如 "算力" 匹配所有含 "算力中心" 的claim) | 最短提升到3字符; 更新 path_analysis 文档说明 "evidence_touched 是文本重叠, 非逻辑验证" | `opportunity_engine.py:_node_phrases()` + `path_analysis()` docstring |

### 测试更新
- `test_tracking_engine.py`: 更新 `_failure_signals_from_payload` 调用签名为 `(payload, state)`; 更新 `test_missing_odds_blocks_admission` 测试fallback行为
- `test_path_analysis.py`: 更新 evidence claim 以匹配>=3字符短语阈值; 更新 expected observable 计数
- 全部 159 个测试通过 ✅
