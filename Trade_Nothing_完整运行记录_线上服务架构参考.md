# Trade Nothing DeepThink 完整运行记录

> 会话时间：2026-05-28  
> 引擎版本：Trade Nothing v0.9.3  
> 运行环境：Claude Code (macOS)  
> 目的：面向线上服务架构的流程参考

---

## 一、系统架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                        CLI / API 入口                            │
│              deepthink_orchestrator.py                           │
│        (确定性状态机 — 控制流由代码掌控，LLM 仅作内容生产)          │
└──────────────────────┬───────────────────────────────────────────┘
                       │
     ┌─────────────────┼─────────────────┐
     ▼                 ▼                 ▼
┌─────────┐   ┌─────────────┐   ┌───────────────┐
│ Phase 1 │   │  Phase 3    │   │ Phase 4        │
│ --run   │   │ --submit-   │   │ --compile-     │
│ 初始化   │   │   round     │   │  report        │
└────┬────┘   └──────┬──────┘   └───────┬───────┘
     │               │                  │
     ▼               ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    deepthink_engine.py                           │
│    状态管理 + Dung 抽象论证框架 + Bayesian 更新 + 收敛判定        │
│                                                                  │
│  LFI = 0.6×AFI + 0.4×(1-ES)                                    │
│  AFI (Argumentation Friction): Dung 图模糊信念损失               │
│  ES  (Evidence Saturation): Shannon 熵 + Jaccard 新颖度          │
│                                                                  │
│  Posterior = Odds/(1+Odds), Odds_new = Odds_old × Σ BF_i       │
│  BF 矩阵: Hard Proxy Data(4.0) > Factual(3.0) > Channel(2.0)   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
     ┌─────────────────┼─────────────────┐
     ▼                 ▼                 ▼
┌───────────┐  ┌──────────────┐  ┌───────────────┐
│ Dung 图   │  │ Bayesian     │  │ Convergence   │
│ 求解器    │  │ 更新矩阵     │  │ 判定          │
│ (连续模糊  │  │ (Bayes       │  │ (MIN_ROUNDS=3 │
│  不动点)  │  │  Factor)     │  │  MAX=12       │
└───────────┘  └──────────────┘  │  LFI<0.25)    │
                                 └───────────────┘
```

### 四个核心脚本

| 脚本 | 职责 |
|------|------|
| `deepthink_orchestrator.py` | 确定性状态机 — 四个命令：`--run` / `--submit-round` / `--preflight` / `--compile-report` |
| `deepthink_engine.py` | 数学引擎 — 状态管理、Dung 图计算、Bayesian 更新、收敛判定 |
| `deepthink_pipeline.py` | 辅助 — 提取 Evolution.md 记忆、生成子智能体 Prompt、收获未反驳攻击 |
| `dungs_argumentation.py` | Dung 抽象论证框架 — 连续模糊不动点求解器 |

---

## 二、完整执行流程

### Step 0: 宏观环境扫描

```bash
cd ~/.claude/skills/trade-nothing
python3 scripts/verified_fetcher.py --all
```

**输出**：
```json
[
  {"indicator": "US_10Y",   "value": 4.48,    "threshold_status": "🟢 NORMAL"},
  {"indicator": "BRENT_OIL","value": 94.54,   "threshold_status": "🟢 NORMAL"},
  {"indicator": "VIX",      "value": 16.72,   "threshold_status": "🟢 NORMAL"},
  {"indicator": "USDCNY",   "value": 6.78,    "threshold_status": "🟢 NORMAL"},
  {"indicator": "GOLD",     "value": 4422.60, "threshold_status": null}
]
```

---

### Step 1: 初始化引擎（`--run`）

```bash
python3 scripts/deepthink_orchestrator.py --run \
  --topic "2026下半年最具爆发潜力的板块与资产类别"
```

**内部流程**：

1. `deepthink_pipeline.py --extract --topic "..."` → 从 `Methodology_Evolution.md` 提取历史负面先验
2. `deepthink_engine.py --start --topic "..."` → 创建空白状态文件
3. `deepthink_pipeline.py --generate-prompts --topic "..."` → 生成 Round 1 Prompt

**初始状态文件** (`~/.trade-nothing/scratch/state/<slug>_state.json`)：
```json
{
  "rounds": [],
  "started_at": "2026-05-28T20:25:02",
  "topic": "2026下半年最具爆发潜力的板块与资产类别",
  "unrefuted_attacks": [],
  "accumulated_evidence": [],
  "accumulated_claims": [],
  "odds": 1.0,
  "posterior": 50.0
}
```

**Orchestrator 输出**：
```json
{
  "status": "dispatch_subagents",
  "phase": "round_1_pending",
  "topic": "2026下半年最具爆发潜力的板块与资产类别",
  "round": 1,
  "negative_priors": "⚠️ Active memory source (Evolution.md) not found. Standard initialization applied.",
  "detective_prompt": "Role: Trade Nothing v0.9.3 - The Detective [Round 1]...",
  "inquisitor_prompt": "Role: Trade Nothing v0.9.3 - The Inquisitor [Round 1]...",
  "forbidden_consensus": [
    "核心在于成本控制和渠道建设",
    "受制于宏观流动性收紧，板块估值承压",
    "行业竞争激烈，龙头企业优势明显",
    "行业需求增速放缓，进入存量博弈阶段",
    "公司在进行技术转型，短期研发费用拖累业绩"
  ],
  "instruction": "请按以下步骤执行：1. 使用 detective_prompt 派发隔离的 Detective 子智能体..."
}
```

**子智能体派发**（Claude Code 环境）：
- 使用 `Agent` 工具，`subagent_type: general-purpose`
- **物理隔离**：Detective 和 Inquisitor 无共享上下文
- 两个 Agent 各自搜索 Web 获取最新数据，构造结构化 JSON 输出

---

### Step 2: Round 1 提交（`--submit-round`）

```bash
python3 scripts/deepthink_orchestrator.py --submit-round \
  --topic "2026下半年最具爆发潜力的板块与资产类别" \
  --detective-json '<Detective R1 JSON output>' \
  --inquisitor-json '<Inquisitor R1 JSON output>'
```

**引擎内部计算** (`deepthink_engine.py:342-543`)：

#### 2.1. 解析子智能体输出
```python
# orchestrator.py _extract_arguments_from_detective()
# 从 evidence_chain 提取 claim_node 作为 Dung 图节点
arguments = [item["claim_node"] for item in detective_json["evidence_chain"]]

# orchestrator.py _extract_attacks_from_inquisitor()
# 从 lethal_attack_vectors 提取 (attack, target) 作为有向边
attacks = [(vec["attack"], vec["target_claim_node"]) 
           for vec in inquisitor_json["lethal_attack_vectors"]]

# orchestrator.py _extract_evidence()
# 从 evidence_chain 提取 (category, direction, strength) 三元组
evidence = [{"category": ..., "direction": "Bull", "strength": "Strong"}]
```

#### 2.2. Dung 图求解（`dungs_argumentation.py`）
```python
class DungSolver:
    def compute_fuzzy_valuations(self, max_iter=50, dampening=0.5):
        # 连续模糊不动点求解
        # V[x] = confidence(x) × Π(1 − weight(y)×V[y])  对所有攻击者 y
        # 阻尼迭代: next_V[x] = 0.5×val + 0.5×V[x]
        # 收敛阈值: max_delta < 1e-5
        
    def get_grounded_friction(self) -> float:
        # AFI = (1/|A|) × Σ(1 − V(x))
        # 图中所有论点的平均信念损失
```

#### 2.3. 证据饱和度计算
```python
# Shannon 熵变化
categories = [e.get("category") for e in accumulated_evidence]
entropy = -Σ p(cat) × log₂(p(cat))

# Jaccard 新颖度
novelty = 1 - |new_tokens ∩ prior_tokens| / |new_tokens ∪ prior_tokens|

# 证据饱和度
ΔH = (entropy - prev_entropy) + novelty
if ΔH > 0:
    ES = 1 - exp(-0.5 × round / ΔH)
else:
    ES = 1.0
```

#### 2.4. LFI 计算
```python
LFI = 0.6 × AFI + 0.4 × (1.0 - ES)
```

#### 2.5. Bayesian 更新矩阵
```python
BAYES_FACTOR_MATRIX = {
    "Hard Proxy Data":  {"Bull": {"Strong": 4.0, "Weak": 2.0}},
    "Factual Disclosed":{"Bull": {"Strong": 3.0, "Weak": 1.5}},
    "Channel Checks":   {"Bull": {"Strong": 2.0, "Weak": 1.2}},
    "Narrative":        {"Bull": {"Strong": 1.0, "Weak": 1.0}}
}

# 更新赔率
for e in new_evidence:
    bf = get_bayes_factor(e["category"], e["direction"], e["strength"])
    odds *= bf

# Vision 模式: 每个已验证的 Vision Node 追加 ×1.5 非对称期权因子
if mode == "vision":
    for arg in grounded_extension:
        if classify_argument(arg) == "vision":
            odds *= 1.5

posterior = (odds / (1.0 + odds)) * 100.0
```

#### 2.6. 收敛判定
```python
MIN_ROUNDS = 3
MAX_ROUNDS = 12
LFI_THRESHOLD = 0.15   # audit mode
# vision mode uses 0.25

def check_convergence(round_num, lfi, open_attacks, mode):
    if round_num >= MAX_ROUNDS:
        return {"decision": "fuse_break"}
    if round_num < MIN_ROUNDS:
        return {"decision": "continue"}   # 必须至少3轮
    if open_attacks > 0:
        return {"decision": "continue"}   # 未反驳攻击必须处理
    if lfi >= threshold:
        return {"decision": "continue"}   # 摩擦未平息
    return {"decision": "converge"}
```

**Round 1 引擎输出**：
```json
{
  "action": "continue",
  "round_completed": 1,
  "next_round": 2,
  "lfi": 0.3959,
  "afi": 0.12,
  "es": 0.1901,
  "posterior": "99.71%",
  "bayesian_trace": "R1:99.71%",
  "total_rounds": 1,
  "remaining_before_fuse": 11,
  "reason": "轮次 1 < 最低要求 3，必须继续进行质证硬化。",
  "egi": -0.5,
  "mode": "vision"
}
```

**Round 1 辩论摘要**：

| 角色 | 核心主张 |
|------|---------|
| **Detective** | 全球电网互联设备（大功率变压器/HVDC/高压开关）是AI基础设施链条中唯一尚未被定价的物理瓶颈。变压器交货期128-210周，美国16GW数据中心仅31%在建。中国电力设备制造商（全球60%产能，交货期仅10-12个月）将经历戴维斯双击。 |
| **Inquisitor** | 五大攻击维度：(1) 台湾LNG-氦气双重物理依赖→AI芯片供应链单点崩溃；(2) AI奇点叙事破产（95%试点失败）；(3) Q3非做多窗口（盈利修正比率0.76）；(4) 15.6%盈利增速的统计口径缺陷；(5) 杠铃策略的单点物理故障。 |

---

### Step 3: Round 2 提交

```bash
python3 scripts/deepthink_orchestrator.py --submit-round \
  --topic "2026下半年最具爆发潜力的板块与资产类别" \
  --detective-json '<Detective R2 JSON output>' \
  --inquisitor-json '<Inquisitor R2 JSON output>'
```

**Round 2 引擎输出**：
```json
{
  "action": "continue",
  "round_completed": 2,
  "next_round": 3,
  "lfi": 0.1394,
  "afi": 0.0692,
  "es": 0.7555,
  "posterior": "100.0%",
  "bayesian_trace": "R1:99.71% → R2:100.0%",
  "reason": "轮次 2 < 最低要求 3，必须继续进行质证硬化。",
  "egi": -0.83,
  "mode": "vision"
}
```

LFI 已降至 0.1394 < 0.25（vision 阈值），但引擎仍要求至少 3 轮。

**Round 2 辩论摘要**：

| 角色 | 核心主张 |
|------|---------|
| **Detective** | R2新维度：**政策信号——Section 232变压器关税从50%降至15%**。4大反驳：(1) 台湾$44.4B美国LNG对冲+TSMC Arizona加速；(2) hyperscaler Q1 CAPEX $131.6B证明加速而非减速；(3) Q3板块分化——变压器制造商处于盈利上修象限；(4) 75-80%需求来自电网现代化非AI。 |
| **Inquisitor** | R2新维度：**反身性（Reflexivity）**——共识拥挤自毁。5大审计：(1) Q1出口增速含基数水分（亚洲仅+8.01%）；(2) 叙事已从盲区变为拥挤（六大机构覆盖）；(3) hyperscaler CAPEX面临ROI临界点（Amazon FCF崩溃95%）；(4) 境外毛利率崩塌（平高电气-13.45%）；(5) 供给侧产能以15-17%年增速扩张被低估。 |

---

### Step 4: Round 3 提交 & 收敛

```bash
python3 scripts/deepthink_orchestrator.py --submit-round \
  --topic "2026下半年最具爆发潜力的板块与资产类别" \
  --detective-json '<Detective R3 JSON output>' \
  --inquisitor-json '<Inquisitor R3 JSON output>'
```

**Round 3 引擎输出**：
```json
{
  "action": "converge",
  "round_completed": 3,
  "lfi": 0.1215,
  "afi": 0.0696,
  "es": 0.8006,
  "posterior": "100.0%",
  "bayesian_trace": "R1:99.71% → R2:100.0% → R3:100.0%",
  "total_rounds": 3,
  "reason": "LFI=0.1215 < 0.25 (vision模式)，论证冲突完全收敛，未反驳致命漏洞归零。逻辑硬化达成。"
}
```

**收敛条件全部满足** ✅：
- round = 3 ≥ MIN_ROUNDS = 3
- LFI = 0.1215 < 0.25 (vision)
- open_attacks = 0
- posterior = 100.0%

**Round 3 辩论摘要**：

| 角色 | 核心主张 |
|------|---------|
| **Detective** | R3新维度：**价格传导机制制度化——国网铜联动公式**。5大反驳：(1) Q1变压器完整季度+34.3%，大容量+49.5%，2500GVA+243.1%；(2) 国电南瑞PE 24.7x处于历史18%分位，MS目标价32.25(+28%)；(3) hyperscaler Q1 CAPEX $131.6B(+70.3%)，Jassy明确不保守；(4) Q1毛利率拐点：保变电气+2.95pp至12.24%；(5) Citi缺口仍达1699 GVA，熟练工培训3-5年+GOES硅钢垄断是硬约束。 |
| **Inquisitor** | R3新维度：**流动性-资金面戴维斯双杀**——与R1的engineering_limit和R2的reflexivity完全正交。4大审计：(1) Section 232从未对变压器整机征50%——这是政策事实错误；(2) 台湾LNG对冲仅为非约束性LOI（2030年才交付）；(3) 边际定价谬误——PE定价于边际AI需求，即使75%需求来自稳态替换，AI消失仍导致30-50%估值压缩；(4) 北向资金连续撤离+公募连续19季净赎回。 |

---

### Step 5: 强制预检门（`--preflight`）

```bash
python3 scripts/deepthink_orchestrator.py --preflight \
  --topic "2026下半年最具爆发潜力的板块与资产类别"
# exit code 0
```

**预检逻辑**（`deepthink_orchestrator.py:298-350`）：
```python
# 1. 检查 state.json 存在
# 2. 检查 rounds >= 3
# 3. 调用 check_convergence() 二次验证
# 不通过 → sys.exit(2) 阻断报告生成
```

**输出**：
```json
{
  "status": "PASSED",
  "total_rounds": 3,
  "lfi_final": 0.1215,
  "posterior": 100.0,
  "convergence": {
    "decision": "converge",
    "reason": "LFI=0.1215 < 0.25 (vision模式)，论证冲突完全收敛，未反驳致命漏洞归零。逻辑硬化达成。"
  },
  "mode": "vision"
}
```

---

### Step 6: 编译报告数据（`--compile-report`）

```bash
python3 scripts/deepthink_orchestrator.py --compile-report \
  --topic "2026下半年最具爆发潜力的板块与资产类别"
```

**从 state.json 物理读取**（`deepthink_orchestrator.py:357-421`）：
```python
def cmd_compile_report(topic):
    state = _load_state(topic)
    rounds = state["rounds"]
    last_round = rounds[-1]
    
    # 所有数值从 state.json 物理读取，严禁 LLM 手写
    lfi_final = round(last_round["lfi"], 4)       # 0.1215
    posterior = round(state["posterior"], 2)        # 100.0
    total_rounds = len(rounds)                       # 3
    bayesian_trace = " → ".join(f"R{r['round']}: {r['posterior']}%" for r in rounds)
    egi = round(last_round.get("egi", 0.0), 2)      # -0.90
```

**输出**：
```json
{
  "status": "report_data_ready",
  "topic": "2026下半年最具爆发潜力的板块与资产类别",
  "physical_values": {
    "total_rounds": 3,
    "lfi_final": 0.1215,
    "posterior_percent": 100.0,
    "bayesian_trace": "R1: 99.71% → R2: 100.0% → R3: 100.0%",
    "egi": -0.90,
    "mode": "vision",
    "convergence_decision": "converge",
    "convergence_reason": "LFI=0.1215 < 0.25 (vision模式)，论证冲突完全收敛，未反驳致命漏洞归零。逻辑硬化达成。",
    "open_attacks_count": 0,
    "unrefuted_attacks": []
  }
}
```

**LLM 仅提供定性内容**（variant perception、scenario 描述、催化剂分析等），数值全部由物理引擎填入。

---

## 三、完整指标演化表

| 参数 | Round 1 | Round 2 | Round 3 | 趋势 |
|------|---------|---------|---------|------|
| **LFI** | 0.3959 | 0.1394 | **0.1215** | ↓ 持续收敛 |
| **AFI** | 0.1200 | 0.0692 | 0.0696 | ↓ 信念损失减少 |
| **ES** | 0.1901 | 0.7555 | 0.8006 | ↑ 证据趋于饱和 |
| **后验概率** | 99.71% | 100.0% | 100.0% | → 维持极高水平 |
| **EGI** | -0.50 | -0.83 | -0.90 | ↓ 预期差扩大 |
| **Novelty** | 1.0 (baseline) | 积分衰减 | 积分衰减 | — |
| **Entropy** | 新增 | 累积增长 | 接近上限 | ↑ 信息量增加 |
| **Open Attacks** | 0 | 0 | 0 | → 无未反驳 |
| **辩论维度 (D)** | 电网瓶颈数据 | 政策信号（关税反转） | 价格传导制度化 | 3个正交维度 |
| **辩论维度 (I)** | 工程物理极限 | 反身性（共识自毁） | 流动性戴维斯双杀 | 3个正交维度 |

---

## 四、Dung 抽象论证框架数学原理

### 4.1. 模糊信念估值（Fuzzy Valuation）

```
对于每个论点 x:
  V⁰[x] = confidence(x)   // 初始信念 = 节点置信度

  每次迭代:
    val = confidence(x) × Π(1 − weight(y) × Vᵏ[y])  对所有攻击者 y
    Vᵏ⁺¹[x] = 0.5 × val + 0.5 × Vᵏ[x]  // 阻尼因子确保收敛

  收敛条件: max(|Vᵏ⁺¹[x] − Vᵏ[x]|) < 1e-5
  最大迭代: 50 轮
```

### 4.2. 节点置信度

| 节点类型 | 置信度 | 示例 |
|----------|--------|------|
| `[Audit Node]` / `[Proxy Data Anchor]` | 1.0 | 物理数据锚点 |
| `[Vision Node]` | 0.8 | 前瞻远见主张 |
| `[Narrative Node]` | 0.6 | 叙事/情绪指标 |
| `System:Penalty` | 1.0 | 系统惩罚节点 |

### 4.3. 攻击强度

| 攻击类型 | 强度 |
|----------|------|
| `System:AuditHardenedPenalty` | 1.0 |
| `[Audit Attack]` | 0.95 |
| `[Vision Audit]` | 0.80 |
| Default | 0.85 |

### 4.4. Grounded Extension

```
Extension = {x | V[x] ≥ 0.5}  — 信念 ≥ 0.5 的论点被接受
```

### 4.5. 综合指标计算公式

```
AFI = (1/|A|) × Σ(1 − V(x))     论证摩擦指数（信念损失）
Entropy = −Σ p(cat) × log₂(p(cat))    香农信息熵
Novelty = 1 − |new ∩ prior| / |new ∪ prior|    雅卡尔新颖度
ΔH = (entropy − prev_entropy) + novelty
ES = 1 − exp(−0.5 × round / ΔH)       证据饱和度
LFI = 0.6 × AFI + 0.4 × (1 − ES)     逻辑摩擦指数（核心收敛指标）
EGI = (Narrative − Audit) / (Narrative + Audit)    预期差指数 [−1, 1]
```

---

## 五、面向线上服务的架构建议

### 5.1. API 路由设计

```
POST /api/v1/deepthink/run
  Body: { "topic": "..." }
  Response: {
    "session_id": "cuid",
    "status": "dispatch_subagents",
    "detective_prompt": "...",
    "inquisitor_prompt": "...",
    "forbidden_consensus": [...]
  }

POST /api/v1/deepthink/submit-round
  Body: {
    "session_id": "cuid",
    "detective_json": { ... },
    "inquisitor_json": { ... }
  }
  Response: {
    "status": "dispatch_subagents" | "ready_for_report",
    "engine_output": {
      "action": "continue" | "converge" | "fuse_break",
      "round_completed": 2,
      "lfi": 0.1394,
      "posterior": "100.0%",
      ...
    },
    // 仅 continue 时返回
    "detective_prompt": "...",
    "inquisitor_prompt": "..."
  }

POST /api/v1/deepthink/preflight
  Body: { "session_id": "cuid" }
  Response: { "status": "PASSED" | "BLOCKED" }

POST /api/v1/deepthink/compile-report
  Body: { "session_id": "cuid" }
  Response: {
    "physical_values": {
      "total_rounds": 3,
      "lfi_final": 0.1215,
      "posterior_percent": 100.0,
      "bayesian_trace": "...",
      ...
    }
  }

GET /api/v1/deepthink/status?session_id=cuid
  Response: { "status": "idle" | "active" | "ready_for_report" }
```

### 5.2. 子智能体调度（关键设计）

```
核心原则: Detective 和 Inquisitor 必须在物理隔离的上下文中运行

实现方案 A: 双 LLM API 调用
  - Detective → model A (temperature=0.3, 乐观偏置)
  - Inquisitor → model B (temperature=0.7, 怀疑偏置)
  - 两者无共享上下文，仅通过 Orchestrator JSON 通信

实现方案 B: 单模型 + 上下文隔间
  - 两个独立的 conversation session
  - 分别注入 Detective/Inquisitor persona
  - Orchestrator 收集双方输出后统一提交

关键约束:
  - 严禁同一上下文内角色扮演（会导致伪对抗和2轮内趋同）
  - 严禁 Detective 看到 Inquisitor 的中间推理
```

### 5.3. 状态持久化

每个 session → state JSON 文件，结构：
```json
{
  "rounds": [
    {
      "round": 1,
      "lfi": 0.3959,
      "afi": 0.12,
      "es": 0.1901,
      "entropy": 1.2,
      "novelty": 1.0,
      "posterior": 99.71,
      "open_attacks": 0,
      "new_evidence_count": 7,
      "egi": -0.5,
      "mode": "vision",
      "grounded_extension": ["[Audit Node: ...]", "[Vision Node: ...]"],
      "timestamp": "2026-05-28T20:25:02"
    }
  ],
  "odds": 1000.0,
  "posterior": 100.0,
  "unrefuted_attacks": [],
  "accumulated_evidence": [...],
  "accumulated_claims": [...]
}
```

### 5.4. 安全护栏

| 护栏 | 机制 |
|------|------|
| 最低轮次 | `MIN_ROUNDS = 3`，不满足必须继续 |
| 最大轮次 | `MAX_ROUNDS = 12`，超过自动熔断 |
| LFI 收敛阈值 | 0.15 (audit) / 0.25 (vision) |
| 未反驳攻击 | `open_attacks > 0` → 必须继续辩论 |
| 预检门 | `--preflight` 调用 `check_convergence()` 二次验证，不通过 exit code 2 |
| 数值隔离 | 所有 LFI/后验概率等数值由引擎物理写入 state.json，LLM 严禁手写 |
| 平庸共识过滤 | TF-IDF 余弦相似度 ≥ 0.70 (vision) / 0.85 (audit) 即拦截 |
| Vision 模式 | audit 模式审计惩罚节点自动注入，处罚无锚点的主张 |

### 5.5. 时序图

```
Client              Orchestrator API              LLM Service
  │                      │                            │
  ├──POST /run──────────►│                            │
  │                      ├──engine.start()            │
  │                      ├──pipeline.extract()        │
  │                      ├──pipeline.prompts()        │
  │◄──detective_prompt───┤                            │
  │◄──inquisitor_prompt──┤                            │
  │                      │                            │
  ├──Detective───────────┼──►LLM API (isolated)       │
  │  (独立上下文)         │◄──detective_json           │
  │                      │                            │
  ├──Inquisitor──────────┼──►LLM API (isolated)       │
  │  (独立上下文)         │◄──inquisitor_json          │
  │                      │                            │
  ├──POST /submit────────┤                            │
  │                      ├──engine.checkpoint()       │
  │                      │   ├──DungSolver            │
  │                      │   ├──Bayesian update       │
  │                      │   ├──LFI calculation       │
  │                      │   └──check_convergence()   │
  │                      │                            │
  │◄── action: continue ─┤                            │
  │   + new prompts      │                            │
  │                      │                            │
  │   ... (loop 2 more rounds) ...                    │
  │                      │                            │
  │◄── action: converge ─┤                            │
  │                      │                            │
  ├──POST /preflight────►│                            │
  │◄── status: PASSED ───┤                            │
  │                      │                            │
  ├──POST /compile──────►│                            │
  │◄── physical_values ──┤                            │
  │                      │                            │
  │   [LLM generates qualitative report text]         │
  │                      │                            │
  ▼                      ▼                            ▼
```

---

## 六、相关文件路径

| 文件 | 路径 |
|------|------|
| 引擎状态文件 | `~/.claude/skills/trade-nothing/scripts/.state/<slug>_state.json` |
| 调研索引 | `~/.claude/skills/trade-nothing/scripts/.research_index.json` |
| 历史记忆 | `~/.claude/skills/trade-nothing/Methodology_Evolution.md` |
| 宏观扫描输出 | `~/.trade-nothing/scratch/` |
| 未反驳攻击 Issue | `~/.trade-nothing/scratch/<slug>/issue_*.md` |
| Skill 根目录 | `~/.claude/skills/trade-nothing/` |

---

*Trade Nothing v0.9.3 — 确定性状态机 + 物理隔离对抗辩论 + 连续模糊 Dung 图收敛框架*
