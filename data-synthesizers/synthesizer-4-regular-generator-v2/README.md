# 数据合成器 4 · 规律密集构造

入训记录：**11,384 条**。

主体是 `training/regular_generator_v2/`：规律密集结构（板、矩形、连续区域、紧凑块、
扇出、同步与混合计划）的构造、度量与多级准入；同一份代码里还带了一版**带反馈生长**
的 `training/structure_generator/`（分层接力、反馈消融与验证），批量入口同样是
`python -m training.structure_generator.batch`。

**源码来源说明**：从当时冻结的运行源码提取。历史数据文件与运行配置不在交付范围内。

入口见上一级 `../README.md`。
