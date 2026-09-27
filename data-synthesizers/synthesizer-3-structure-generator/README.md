# 数据合成器 3 · 结构生成器

入训记录：**77,374 条**。

主体是 `training/structure_generator/`：引导生长、几何与布局、推拉机制规划、供电、
预筛与验收集成，`batch/` 子包提供多进程批量构造（`python -m training.structure_generator.batch`）
与断点存储、历史索引、导出。

**源码来源说明**：从当时保存的源码快照逐文件提取，可信度最高。
历史数据文件与运行配置不在交付范围内。

入口见上一级 `../README.md`。
