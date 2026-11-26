# 比赛操作

在仓库根目录打开 Codex。首次运行使用 Python 3.10 或更新版本执行 `python -m pip install -r workflow/requirements.txt`。用 `python workflow/test_simulation.py` 验证。正式操作如下。

| 时点 | 上传材料与指令 | 聊天回复 |
|---|---|---|
| 开赛 | Benchmark、宏观 PDF，输入 Build initial portfolio | 资产、买入金额、数量 |
| 季中 | 新闻截图，输入 Analyze news；需要时补当前价格 | HOLD 或 BUY/SELL、资产、金额、数量 |
| 前三季末 | 平台季度收益、最新资产价格，输入 Rebalance | 仅列交易；无交易显示 HOLD |
| 交易后 | 回复成交编号、方向、实际数量、成交价和实际费用；标出剩余委托待成交或已撤 | 确认已入账及仍待处理的委托 |
| 最终季末 | 上传最终收益及价格，输入 Finish simulation | 最终收益、固定基准收益、超额收益及重大差异 |

关闭聊天后，在同一仓库继续。每次先运行 `python workflow/engine.py status`，读取季度、阶段与待成交建议。保留整个 data 和 result，包括隐藏的恢复日志。紧急错误或重大核对差异优先报告。

## Codex 执行协议

1. 每次重读 constraints.md、状态、两份 CSV、历史报告和本季宏观信息。规则文本的范围、定义或单位发生变化时，先核对解析和模型。以实际规则文件为唯一数值来源。固定基准按初始权重建仓持有；若官方采用其他口径，暂停相对业绩结论并核对。
2. 读取附件。表格按表头、单位和原始精度解析。PDF 逐页检查正文与图表；扫描页和截图使用视觉识别，保留页码、标题、事件时间、单位和原文。区分百分数与百分点、单季与累计、本币与美元、份额与合约。只在能确定 USD 每单位价值时换算。看不清的必需字段只询问该字段。复核资产名、权重合计、平台最小交易单位。把原附件放在持久可访问路径；程序按内容哈希存档。输入不全时先把原件和已核实的提取稿保存在 data 对应季度的新文件，续接同一事件。不得改写队友文件。
3. 调用 .agents/skills/portfolio-analysis/SKILL.md。将证据、定性分析和有依据的定量输入整理为临时 UTF-8 JSON。运行 `python workflow/engine.py ACTION PACKET.json`；状态查询不带 packet。必须读取退出状态和输出。不得绕开不可行解或验证错误手工报单。
4. 每个分析包均含 sources（原始附件路径列表）、as_of（平台行情观察时点）、analysis（完整 Markdown 分析）。同一新闻不同裁剪或转发先以事件时间、主体和正文对照本季宏观文件；重复只返回原建议的状态，切勿再次下单。所有价格要属于本次决策时点；截图没有必要报价时只询问缺失价格。收盘价用于盘中决策必须有本次用户明确确认。保留价格来源、时间和每项判断依据。
5. build 提供 benchmark，每行依次是资产名、初始 USD 单价、基准小数权重、交易单位；transcript 为宏观原文。news 提供 transcript、prices（资产名到当前价）。rebalance 和 finish 提供 prices、returns（每个资产名及 PORTFOLIO 到本季度小数收益）。有累计值时先按两期增长因子换算，保留原值。禁止混合总回报和价格回报。所有优化包都需要 scenarios（一个或多个同期限收益字典）、downside（逐资产正的压力跌幅），可选 history（同频同口径、按时间对齐的历史收益字典列表）。
6. 季末先从实际成交 CSV、现金及新价格预核 NAV 与平台收益；重查费用、分红、汇率、存取款和错季。存在影响建议的差异先报告并补证；本版账本只处理买卖和成交费用，有其他现金流时暂停决策。analysis 记录归因、偏差金额、风险和解释。前三次季末分别写入下一轮 quarterN 的 outcomeN 和 price-changeN；末季使用 quarter4 的独立 final 后缀。最后只做业绩归档。
7. 发出建议后等待实际成交。confirm 包包含 id（status.pending.id）、fills 列表（asset、side、trade_id、quantity、price、fee）、close 布尔值。支持部分成交、多批成交及空 fills 撤单。按平台成交顺序填报。费用未知先询问。状态为 repair 时用新报价附件走 repair，补齐开季约束后再继续。每次都核对执行警告和未成交余额。事件或报告中的建议均不能替代成交。
