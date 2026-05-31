<div align="center">

<img src="assets/images/hero_banner.jpg" alt="Trade Nothing Hero Banner" width="800" style="border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);" />

# Trade Nothing

### *只交易你的认知。*

一个对抗式多智能体技能，把你的 AI 变成一台冷酷的投研机器。<br/>
它不告诉你买什么。它告诉你**所有人在哪里错得最离谱**。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Agent-Agnostic](https://img.shields.io/badge/Agent-Agnostic-blueviolet.svg)](#多平台适配)

[English](README.md) · [中文](README_zh.md) · [架构](docs/architecture.md) · [贡献](CONTRIBUTING.md)

</div>

---

## 问题

每个 AI 都能总结一只股票。没有一个能**对抗性地思考**它。

让任何大模型分析一家公司，你得到的都是同一个东西：一份措辞精美、结构完整、毫无用处的报告——它从头到尾都在同意自己。它读卖方报告、反刍共识、然后自信地把中位数观点包装成洞察。它携带着训练数据里的每一种认知偏差——确认偏误、锚定效应、叙事谬误——而且语法完美。

**这不是研究。这是一面镜子。**

历史上最伟大的投资者——索罗斯、德鲁肯米勒、Burry——不是靠更聪明击败市场的。他们靠的是看到所有人拒绝看到的东西。他们问的是：*"群体在哪里最自信地犯错？针对这种自信的非对称下注是什么？"*

Trade Nothing 是一个技能，它强迫你的 AI 智能体问同样的问题——然后试图**亲手摧毁自己的答案**。

---

## 哲学

<div align="center">
  <img src="assets/images/philosophy.jpg" alt="Alpha Gap Concept - Consensus vs Reality" width="600" style="border-radius: 8px; margin: 20px 0;" />
</div>

> *"你不是一个解释已经发生事实的评论员。你是一个在迷雾中寻找错配的猎手。你的敌人是线性外推、群体共识和完美报告。"*

"Trade Nothing" 这个名字是一个刻意的悖论。它有三层含义：

**1. 只交易你的认知 (Trade nothing but your mind)**

最有价值的资产不是资本——是你思考的质量。这个工具磨砺思维，不推荐股票。

**2. 有时最好的交易就是不交易 (The best trade is no trade)**

如果系统找不到非对称赔率（>1:3）加上迫在眉睫的催化剂，正确的输出就是 "No Edge"。一个总是找到买入信号的系统是坏掉的。

**3. 交易那个"空无"——错配的缝隙 (Trade the nothing — the gap)**

Alpha 活在市场定价和现实之间的缝隙里。系统的设计目标就是找到并度量这个缝隙。

### 四个敌人

| 敌人 | 我们如何对抗 |
|------|------------|
| **确认偏误** | 部署一个审问者，它*唯一的工作*就是摧毁看多论点 |
| **线性外推** | 强制 4 情景思维：悲观、基准、乐观、黑天鹅 |
| **叙事谬误** | 要求每个论点都是可证伪陈述，并配置熔断线 |
| **共识漂移** | 量化共识距离——*这个想法有多平庸？* |

---

## 它如何工作

<div align="center">
  <img src="assets/images/architecture.jpg" alt="Adversarial Architecture - Detective vs Inquisitor" width="650" style="border-radius: 8px; margin: 20px 0;" />
</div>

Trade Nothing 部署**两个物理隔离的 AI 子智能体**，进行结构化的对抗辩论：

```
你: "-deepthink 英伟达 AI 基础设施"

                    ┌─────────────────┐
                    │   编排者 / 法官   │
                    │  (Orchestrator)  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼                              ▼
    ┌─────────────────┐            ┌─────────────────┐
    │   🔍 侦探        │            │  ⚔️ 审问者       │
    │  (Detective)     │            │  (Inquisitor)   │
    │                  │            │                  │
    │ "这里存在错误     │            │ "这个逻辑会       │
    │  定价，因为..."   │            │  崩塌，因为..."    │
    └────────┬────────┘            └────────┬────────┘
             │                              │
             │    物理隔离 — 不共享任何       │
             │    中间推理过程或上下文        │
             └──────────┬───────────────────┘
                        ▼
              ┌─────────────────┐
              │  贝叶斯概率更新   │
              │  LFI 收敛检测    │
              │  (3-12 轮)       │
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │  📄 研究报告      │
              │  + 📊 DCF 模型   │
              │  (.xlsx)         │
              └─────────────────┘
```

### 为什么物理隔离至关重要

当同一个模型"角色扮演"看多和看空时，它在 2 轮之内就会收敛到一个舒适的中间地带。论证变成表演。辩论变成戏剧。

Trade Nothing 强制**真正的认知摩擦**：每个子智能体运行在独立的上下文中，无法访问对方的中间推理。它们只通过结构化输出与编排者通信。编排者作为法官，追踪贝叶斯后验概率和**逻辑摩擦指数（LFI）**——度量每一轮辩论实际贡献了多少新信息。

辩论的终止条件：
- LFI 降至 0.15 以下（边际递减）**且**至少完成 3 轮 → 收敛
- 或硬熔断在第 12 轮触发（防止无限循环）

---

## 快速开始

### 1. 安装依赖

```bash
git clone https://github.com/Thhoho/trade-nothing.git
cd trade-nothing
pip install -r requirements.txt
```

### 2. 🤖 智能体接入指南 (For AI Agents / Claude / Antigravity)

如果你是 AI 智能体或正在使用智能体助手（如 Claude Code、Antigravity、OpenHands 等）：
*   **直接读取技能**：无条件首先读取项目根目录下的 [SKILL.md](SKILL.md)，其中包含最完整的智能体运行指令与攻防提示词规范。
*   **软链接激活**：将本项目直接软链接到智能体的技能目录（例如 `~/.gemini/skills/trade-nothing/`）。
*   **唤醒指令**：在聊天窗口中直接向智能体输入：*“激活 trade-nothing 技能，对宁德时代固态电池时间表启动深度质证”*，或简写为 `-deepthink "宁德时代固态电池时间表"`。

---

### 3. 使用示例与核心命令

#### 🤺 启动多智能体对抗深度质证 (主打核心功能)
自动在物理隔离的沙箱中 mobilization 两个子智能体：**侦探 (Detective)** 构建看多论据，**审问者 (Inquisitor)** 准备致命漏洞进行极限施压，由 **编排法官 (Orchestrator)** 进行后验概率判定，直至达到 Bayesian 均衡并自动编译出由三部分组成的投资决策看板：
```bash
# 启动对指定投资标的/行业命题的深度博弈质证
python3 scripts/deepthink_orchestrator.py --run --topic "宁德时代固态电池时间表"
```

#### 📊 独立量化估值与仓控工具箱 (无需 Agent 即可运行)
如果你想作为传统量化工具独立运行或单独调试：
```bash
# 自动生成 4 情景非对称决策定价矩阵 + 凯利公式最大下注仓位计算
python3 scripts/scenario_matrix.py --demo

# 一键获取全球宏观“水温”看板（美债 10Y、布油、VIX、汇率、黄金）并标定置信度
python3 scripts/verified_fetcher.py --all

# 获取 A 股实时行情报价、主要估值倍数与核心财务数据
python3 scripts/fetch_akshare.py --code 300118 --financial

# 物理编译并导出机构级 Excel 自动配平的 DCF 估值模型
python3 scripts/excel_model_builder.py --help
```

---

## DeepThink 五阶段管线

<div align="center">
  <img src="assets/images/pipeline.jpg" alt="Five-Phase DeepThink Pipeline" width="700" style="border-radius: 8px; margin: 20px 0;" />
</div>

当你触发 `-deepthink` 时，系统执行一条严谨的 5 阶段管线：

### 阶段 1：负向先验注入 🧠
> *"系统从过去的失败中学到了什么？"*

扫描 `Evolution.md`，提取与当前标的相关的历史错误、校准结果和认知偏差日志。注入为**硬约束**——两个子智能体必须无条件遵守。

### 阶段 2：并行动员 🚀
> *"释放猎手和刺客。"*

在隔离的上下文中生成侦探和审问者。侦探用真实数据构建看多论点（财报、产业链、内部人动向）。审问者准备攻击向量（周期分析、反身性陷阱、黑天鹅情景）。

### 阶段 3：对抗辩论循环 🤺
> *"在火中锻造论点。"*

3 到 12 轮结构化辩论。每一轮：
1. 侦探呈堂证据和更新后的论点
2. 审问者发起致命攻击
3. 编排者裁决，更新贝叶斯后验，计算 LFI
4. 若 LFI < 0.15 且轮次 ≥ 3 → 收敛。否则 → 下一轮。

### 阶段 4：定量硬化 📊
> *"数字不会说谎。但它们可以被精心排列。"*

生成：4 情景概率矩阵、期望收益计算、凯利最优仓位、共识距离度量、机构格式 DCF 模型。

### 阶段 5：收割与反馈 🔄
> *"每一个未解决的问题都是一个未来的研究任务。"*

未反驳的攻击向量转化为追踪 Issue。可测试的预测变成校准断言。系统会安排提醒检查自己的预测是否正确。

---

## 工具箱

| 脚本 | 功能 | 独立运行? |
|------|------|:--------:|
| `deepthink_engine.py` | 状态机：收敛逻辑、贝叶斯更新、LFI 计算 | ✅ |
| `deepthink_pipeline.py` | 从 Evolution.md 提取记忆，收割未解决攻击 | ✅ |
| `scenario_matrix.py` | 4 情景概率矩阵 + 凯利仓位 + 期望值 | ✅ |
| `consensus_distance.py` | 量化你的论点与市场共识的差距 | ✅ |
| `catalyst_calendar.py` | 宏观/行业事件日历（"为什么是现在？"） | ✅ |
| `excel_model_builder.py` | 机构级 DCF → `.xlsx`，公式驱动 | ✅ |
| `fetch_akshare.py` | A 股行情 + 财务（腾讯 → AkShare 多源回退） | ✅ |
| `verified_fetcher.py` | 宏观指标（美债/油价/VIX/汇率/黄金）+ 置信度评分 | ✅ |
| `fetch_polymarket.py` | Polymarket 预测市场数据 | ✅ |
| `logic_radar_v2.py` | 断言追踪器：自动将过去的预测与现实校准 | ✅ |
| `logic_radar_daemon.py` | 后台守护：监控宏观阈值，触达时发送系统通知 | ✅ |
| `deepthink_timer.py` | 强制思考暂停的交互式倒计时 | ✅ |

所有脚本输出结构化 JSON。所有路径通过环境变量配置。无硬编码个人路径。跨平台（macOS / Linux / Windows）。

---

## 多平台适配

Trade Nothing 是**平台无关**的。它定义的是*协议*，不是 API 绑定：

| 运行时 | 子智能体调度方式 | 隔离级别 | 状态 |
|--------|---------------|:-------:|:----:|
| **Antigravity** | `define_subagent` + `invoke_subagent` | 🟢 完全 | ✅ 原生 |
| **Claude Code** | `Task` 工具（并行生成） | 🟢 完全 | ✅ 已测试 |
| **Gemini CLI** | 上下文分叉 / Shell 子进程 | 🟢 完全 | ✅ 兼容 |
| **Hermes / OpenHands** | `AgentDelegateAction` | 🟢 完全 | ✅ 兼容 |
| **单模型模式** | 角色切换提示注入 | 🟡 伪隔离 | ⚠️ 降级 |

> **为什么隔离级别重要？** 在"单模型"模式下，同一组权重生成看多和看空论证。模型知道自己上一轮说了什么，自然会漂移向和解。完全隔离意味着每个智能体真正被对方的攻击**吓到**。

---

## 配置

所有路径自动解析。仅在需要时通过环境变量覆盖：

| 变量 | 默认值 | 用途 |
|------|-------|------|
| `TRADE_NOTHING_SKILL_DIR` | 自动检测 | 技能根目录 |
| `TRADE_NOTHING_SCRATCH_DIR` | `~/.trade-nothing/scratch` | 运行时状态 |
| `TRADE_NOTHING_OUTPUT_DIR` | `~/trade-nothing-outputs` | 报告和模型输出 |
| `TRADE_NOTHING_VAULT_DIR` | `~/trade-nothing-vault` | 研究数据库 |
| `TRADE_NOTHING_EVOLUTION_PATH` | `<skill>/Methodology_Evolution.md` | 历史记忆 |
| `TRADE_NOTHING_AUTO_CONTINUE` | 未设置 | 跳过交互计时器（无头/CI） |

---

## 适合谁

- **独立投资者**：想让 AI 挑战自己的论点，而不是确认它
- **研究分析师**：在发表前需要结构化的对抗审查
- **Agent 开发者**：想研究和扩展一个非平凡的多智能体技能
- **所有厌倦了 AI 输出自信、格式完美、但错误的分析的人**

## 不适合谁

- 想要荐股或交易信号的人
- 想要 AI 验证已经做好的决定的人
- 对系统频繁得出 "No Edge" 结论感到不适的人

---

## 贡献

参见 [CONTRIBUTING.md](CONTRIBUTING.md)。特别欢迎：
- 新数据源接入（美股、加密货币、大宗商品）
- Agent 运行时适配器（Langchain、CrewAI、AutoGen）
- 替代收敛算法
- 多语言翻译

## 许可证

[MIT](LICENSE) — 用它，Fork 它，把它变得更好。

---

<div align="center">

*最好的交易往往是不交易。*

*但当你交易时——带着从自己最严厉的批评者手中生还的信念去交易。*

</div>
