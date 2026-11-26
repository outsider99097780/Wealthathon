# WEALTHATHON Agent Instructions

## 1. Objective
Assist the team in portfolio construction, market analysis, risk management, and portfolio rebalancing during the WEALTHATHON simulation.

## 2. Repository Structure
- `data/`: Input data, market information, macroeconomic news and portfolio holdings.
- `skill/`: Financial analysis methods, quantitative models and analytical instructions.
- `workflow/`: Analysis procedures, execution sequences and investment constraints.
- `result/`: Portfolio allocation, rebalancing recommendations and decision reports.

## 3. Execution Rules
- Read the relevant workflow before starting any analysis.
- Identify and use the relevant skills in `skill/`.
- Retrieve required input data from `data/`.
- Follow investment constraints and competition rules.
- Do not fabricate missing data.
- Clearly distinguish facts, assumptions and estimates.
- Save final analysis and recommendations in `result/`.

## 4. Repository Protection
- Do not modify the existing directory structure.
- Do not overwrite original input data.
- Do not modify skills or workflows without explicit authorization.

## 5. Output Requirements
- Recommended asset weights.
- Changes from current portfolio weights.
- Expected return and risk analysis.
- Rationale for investment decisions.
- Key assumptions and uncertainties.

## 比赛指令

在仓库根目录识别以下聊天指令，自动读取 `workflow/simulation.md`、`workflow/constraints.md` 和 `.agents/skills/portfolio-analysis/SKILL.md`，使用 Python 引擎。每次先从文件恢复状态。操作员只需上传材料并输入指令。

| 指令 | 程序动作 |
|---|---|
| Build initial portfolio | build |
| Analyze news | news |
| Rebalance | rebalance |
| Finish simulation | finish |
| 确认成交、部分成交或撤销余单 | confirm |

按操作手册的聊天输出格式返回，完整依据保存在 result。未确认的建议不得写入实际成交或实际持仓。
