<div align="center">

# 🎯 Trade Nothing — 只交易你的认知

**对抗式多智能体深度投研技能**

*猎杀 Alpha，而非追逐共识。*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

[English](README.md) · [中文](README_zh.md) · [架构文档](docs/architecture.md)

</div>

---

## 这是什么？

Trade Nothing 是一个 **Agent Skill（智能体技能）**，部署物理隔离的对抗性 AI 子智能体（侦探 🔍 + 审问者 ⚔️），在结构化辩论轮次中产出投资研究报告。它不是让 AI 写股票推荐——而是**将对抗性思维武器化**，找到市场最大的错误定价。

> *"你不是一个解释已经发生事实的评论员，你是一个在迷雾中寻找错配的猎手。你的敌人是线性外推、群体共识和完美报告。"*

### 核心特性

- 🤺 **对抗辩论**：侦探（看多）vs 审问者（看空），在物理隔离的上下文中运行——不是伪角色扮演
- 📊 **贝叶斯收敛**：通过 LFI（逻辑摩擦指数）驱动的概率更新决定辩论轮数
- 🔧 **12 轮硬熔断**：防止无限循环，同时确保最少 3 轮对抗压力
- 📈 **定量硬化**：4 情景矩阵、凯利仓位、DCF 模型构建器、共识距离计算器
- 🌐 **平台无关**：适配 Claude Code、Gemini CLI、Antigravity、Hermes 或任何支持子智能体的框架
- 🔄 **全生命周期反馈**：历史校准、事前验尸分析、断言自动追踪与验证

---

## 快速开始

### 1. 安装

```bash
git clone https://github.com/YOUR_USERNAME/trade-nothing.git
cd trade-nothing
pip install -r requirements.txt
```

### 2. 配置你的 Agent

将 `trade-nothing/` 目录复制或符号链接到你的 Agent 技能目录：

| Agent 运行时 | 技能位置 |
|-------------|---------|
| **Antigravity** | `~/.gemini/skills/trade-nothing/` |
| **Claude Code** | 在项目上下文中引用 `SKILL.md` |
| **Gemini CLI** | 通过系统提示传入 `SKILL.md` |
| **Hermes** | 配置为 Agent 技能目录 |

### 3. 运行

告诉你的 Agent：

```
-deepthink "英伟达 AI 基础设施"
```

或直接运行工具：

```bash
# 情景矩阵演示
python3 scripts/scenario_matrix.py --demo

# 宏观水温一键获取
python3 scripts/verified_fetcher.py --all

# A 股实时数据 + 财务
python3 scripts/fetch_akshare.py --code 300118 --financial

# Polymarket 预测市场
python3 scripts/fetch_polymarket.py --query "China"
```

---

## 哲学

**Trade Nothing** = 只交易你的认知，不交易你的情绪。

这个名字反映了核心信念：最有价值的交易来自于**没有交易**——当条件不具备时。系统的设计目标是让你不舒服——如果每次分析都产生"买入"信号，说明对抗引擎没有工作。

- **反确认偏误**：审问者的存在就是为了摧毁你的论点
- **反线性外推**：情景矩阵强制非线性思维
- **反完美主义**：事前验尸分析假设失败然后倒推
- **反共识**：共识距离计算器量化"这个想法有多平庸？"

---

## 贡献

参见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

[MIT](LICENSE)
