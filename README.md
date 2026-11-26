# 第一轮

将xlsx的数据写入benchmark（可以直接丢给AI来写入）

> 此处注意，你的vscode本地需要安装officer reader，就可以直接用excel视图看csv！如果不想安装，那就需要在每个csv文件所在的目录下面新增一个xlsx文件，并每次都让AI把csv的内容写入

将PDF内容复制进macro-default.md

# 2-4轮

将新的市场数据输入price-change，我们的投资收益结果写入outcome，breaking news复制进macro

# benchmark

基准数据在每个季度都要调用，所以不放在季度子文件夹中

# 分析过程

AI的分析过程存储在process中，在process文件夹，AI可以自由创建数据结构，用于存储脚本、中间数据等

# 结果

用md输出，既给人看也给下一季度的AI看
