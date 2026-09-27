# 项目说明

## 项目概览

OOOI-SCMLS 是一个以《我的世界》基岩版航械为对象的红石模拟与三维调试项目。
它把「确定性红石模拟」「结构标注」「模型训练」和「网页／手机端推理」串成一条闭环：

1. 用 Rust 写的模拟引擎逐刻推演活塞、观察者、粘液块与蜂蜜块的相互作用；
2. 用网页工作台手工放置方块，或用打标器上传现成结构并标注目标与推动点；
3. 用本机搜索和神经网络模型生成满足需求的移动线结构；
4. 生成的候选再回到同一个引擎里逐刻验证，通过才允许入库或导出。

## 功能概述

### 模拟工作台（`/#`）

* 三维放置、删除、旋转方块，支持「朝向玩家」开关与滑动旋转朝向；
* 逐刻运行、变速播放、暂停、复位、撤销／重做；
* 事件时间线与选中方块检查器；
* 结构库：新建、重命名、排序、导入导出、批量删除与撤销恢复；
* 手机端有专门的底部抽屉布局，触控热区与手势经过单独处理。

模拟只覆盖项目列出的九种方块与活塞臂，不模拟其他方块、实体或区块，
也不实现 Java 版的 QC、BUD 等机制。

### 移动线打标器（`/#labeler`）

* 上传 `.mcstructure` 等结构文件，损坏文件会被隔离而不是写进库；
* 在三维视图里标注目标点与推动点，自动计算时序分组；
* 点标注、刷新读取、JSON 导出恢复、改名与删除撤销；
* 每个样本保留原始文件与回放，方便复核。

### 搜索与训练（`/#search`）

用本机模拟器做结构搜索：按种子批量变异、评估、记录候选与评分，
任务可暂停、继续、取消、删除与恢复。

### AI 移动线生成（`/#generate`）

* 选模型（两个发布版本可自由切换）、填网格与目标需求、选候选数量；
* 后端逐格自回归解码生成候选，八视角确定性生成，超出八个的候选按温度采样；
* 每个候选给出三维回放、判定结果与失败原因，通过的候选可导出成
  `.mcstructure`，可选是否把十块负载与外部推动器一起写进结构；
* 生成任务支持改名、取消、删除，草稿与历史结果持久化。

### 安卓应用（`android/`）

把同一套生成网页塞进 WebView，并把模型与模拟器搬进手机本地离线运行，
详见[安卓应用](安卓应用.md)。

## 项目目录结构

```
oooi-scmls/
├── Cargo.toml / Cargo.lock      Rust 工作区声明与锁定版本
├── docker-compose.yml           后端 + 生成服务 + 前端，一键起
├── docker/
│   └── Dockerfile               四个构建目标：engine / backend / generation / frontend
├── engine/                      Rust 红石模拟引擎
│   ├── Cargo.toml               crate 声明与 PyO3 可选特性
│   └── src/
│       ├── lib.rs               对外导出
│       ├── python.rs            PyO3 扩展入口（Simulator 类）
│       ├── python_snapshot.rs   快照的 Python 序列化
│       ├── python_preflight.rs  放置前预检的 Python 接口
│       ├── types/               方块、朝向、坐标等基础类型
│       ├── world/               世界状态、运动组与错误定义
│       ├── mechanics/           粘附、动力与运动规则
│       └── simulation/          命令、事件、活塞、观察者、刻推进、快照与预检
├── server/                      FastAPI 后端
│   ├── requirements.txt
│   └── app/
│       ├── main.py              应用装配
│       ├── models/              请求／响应模型
│       ├── routes/              健康检查、模拟、WebSocket、结构库、打标回放、自动时序
│       ├── services/            模拟会话、打标时序、目标负载、结构文件解析
│       ├── repositories/        结构库与打标回放的数据访问
│       └── search/              本机搜索：任务、变异、评估、学习、工作进程
├── frontend/                    React 工作台
│   ├── nginx.conf               容器内静态托管与反向代理
│   └── src/
│       ├── app/                 应用外壳与哈希路由（模拟器 / 打标器 / 搜索 / 生成）
│       ├── components/          世界画布、工具面板、检查器、时间线、场景管理、命令面板
│       ├── features/generator/  AI 移动线生成页
│       ├── features/labeler/    移动线打标器
│       ├── features/search/     搜索与训练页
│       ├── hooks/               模拟会话、结构库等状态逻辑
│       └── lib/                 方块表、朝向计算、类名合并等纯函数
├── web-generator/               移动线生成网页（安卓内置同一份）
├── training/                    模型与推理
│   ├── model.py                 条件自回归生成器（含两种相对位置编码）
│   ├── position.py              九档「距离分档＋符号表」
│   ├── exact_position.py        精确三维相对位置编码与因果交叉解码层
│   ├── relations/               关系分数、空间注意力与编码／解码层
│   ├── data.py                  需求特征与结构序列化
│   ├── serialization.py         结构编码、摘要与 JSON 落盘
│   ├── task.py                  需求校验
│   ├── inference.py             单条需求命令行推理
│   ├── evaluator.py             完整候选判定（三轮十负载）
│   ├── load_placement.py        负载摆放口径
│   ├── train.py                 训练损失
│   ├── domain_rules/            航械设计约束（独立于物理实现）
│   ├── compact/                 截面等距变换
│   ├── accelerated/             增量解码、批量解码与八视角对称生成
│   └── web/                     生成服务：接口、任务队列、模型注册表、回放与导出
├── data-synthesizers/           v1.1-preview 训练数据的四份合成器代码
├── models/                      两个发布模型的推理权重、注册表与说明
├── benchmarks/                  四套百题（综合航械题 400 道）
├── scripts/
│   ├── build_local_artifacts.sh 构建引擎 wheel 与前端静态产物
│   ├── download_textures.sh     下载固定版本的官方方块贴图
│   ├── evaluation_sets.py       四套百题的内部键与正式名称
│   └── training/                数据集冻结、训练、评估、发布
├── android/                     安卓应用（WebView + Rust + PyTorch Lite）
└── docs/                        本目录
```

## 数据流

```
数据合成器 ──records.sqlite3──▶ scripts.training.dataset ──dataset.jsonl──▶ 训练
                                                                    │
                                                              run/final.pt
                                                                    │
                                                          scripts.training.evaluate
                                                                    │
                                                          scripts.training.deploy
                                                                    ▼
                                        models/*.pt + models.json ──▶ 生成服务
                                                                    │
                                                        网页 / 安卓应用推理
                                                                    │
                                                           模拟引擎逐刻判定
```

## 关键约定

* **判定口径只有一份**：`training/evaluator.py`。网页生成、命令行推理、训练评估
  全部调用它，协议是「连续三轮、每列目标推过十块负载、每轮不设刻数上限」。
* **需求特征只有一份**：`training/data.py` 的 `condition`。模型读哪些字段由网络配置
  声明，网页据此隐藏不起作用的输入框。
* **相对位置编码只有一份**：`training/relations/`。两个发布模型共用同一套注意力实现，
  区别只在关系分数怎么算。
* **模型注册表只有一份**：`models/models.json`。权重路径与摘要都写在这里，
  服务启动时逐条校验。

## 构建与运行

见[部署指南](部署指南.md)。要点：`sudo docker compose build` 然后
`sudo docker compose up -d`，只改了挂载数据或权重时用 `sudo docker compose restart`。

## 当前范围限制

* 只模拟本文件列出的九种方块及活塞臂，不模拟其他方块、实体或区块。
* 不实现 Java 版 QC、BUD 等机制，也不实现红石粉、红石火把、拉杆、中继器、比较器。
* 模拟会话保存在服务内存中；结构库、打标样本与生成任务持久化到 SQLite。
* 数据库不做账号分区，访问同一服务的设备共享结构与标注。
* 生成是逐格自回归解码，与网格体积和候选数量成正比；大网格建议先减少候选数试跑。
* 未实现任意复杂目标的通用生成与通用厚度优化。
