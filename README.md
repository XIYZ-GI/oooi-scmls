# OOOI-SCMLS

我的世界基岩版**航械移动线**的红石模拟器、结构打标工具、
模型训练与推理服务，以及配套的网页与安卓客户端。

「移动线」是一类用活塞把一整列方块连续推动的可移动红石线路。
这个项目要解决的是：
给定一块网格和若干目标列，自动设计出能按需求把每列负载连续推过十块的结构，并把设计结果放到真实的红石物理里验证。

## 能做什么

| 页面 | 地址 | 说明 |
| --- | --- | --- |
| 模拟工作台 | `/` | 三维放置方块、逐刻运行、事件时间线、结构库（保存/重命名/排序/导入导出） |
| 移动线打标器 | `/#labeler` | 上传结构、标注目标与推动点、自动时序计算、回放与导出 |
| 搜索与训练 | `/#search` | 用模拟器做本机结构搜索，观察候选与评分 |
| AI 移动线生成 | `/#generate` | 选模型、填需求、生成候选、三维回放与导出成品结构 |

另有安卓应用（`android/`）把同一套生成页面与推理塞进手机，模型离线运行。

## 技术栈

* **模拟引擎**：Rust + PyO3（`engine/`），确定性红石模拟，同一份代码编译给
  Python 后端与安卓端使用。
* **后端**：Python + FastAPI + SQLite（`server/`），模拟会话、结构库、打标样本、
  自动时序、搜索任务。
* **生成服务**：Python + PyTorch CPU（`training/web/`），逐格自回归解码，
  八视角确定性候选。
* **前端**：React + TypeScript + Vite + Three.js（WebGPU／WebGL）+ Tailwind（`frontend/`）。
* **部署**：Docker Compose，三个服务一台上机就能跑。

## 目录结构

```
oooi-scmls/
├── engine/               Rust 红石模拟引擎（PyO3 扩展 + 安卓 JNI 复用）
├── server/               后端：模拟、结构库、打标、自动时序、搜索
├── frontend/             前端工作台：模拟器、打标器、搜索、AI 生成
├── web-generator/        移动线生成网页（安卓内置的就是这一份）
├── training/             模型与推理：网络、判定器、八视角解码、生成服务
├── data-synthesizers/    v1.1-preview 训练数据的四份合成器代码
├── models/               两个发布模型的推理权重与注册表
├── benchmarks/           四套百题（综合航械题 400 道）
├── scripts/              构建脚本、数据集冻结、训练、评估、发布
├── android/              安卓应用：WebView 套壳 + Rust + PyTorch Lite
├── docker/               Dockerfile（四个构建目标）
├── docs/                 部署指南、项目说明、模型与安卓说明
└── docker-compose.yml    一键起后端 + 生成服务 + 前端
```

## 快速开始

需要 Docker 与 Docker Compose（`docker compose` 子命令）。

```bash
git clone <本仓库地址> oooi-scmls
cd oooi-scmls

# 可选：改端口
cp .env.example .env

# 构建并启动（首次会编译 Rust 引擎和前端页面，需要几分钟）
sudo docker compose build
sudo docker compose up -d
```

启动后打开：

* 网页工作台 <http://localhost:15175>
* 打标器 <http://localhost:15175/#labeler>
* 搜索与训练 <http://localhost:15175/#search>
* AI 移动线生成 <http://localhost:15175/#generate>
* 后端接口文档 <http://localhost:8010/api/docs>

部署到公网服务器、换端口、备份数据库、只更新权重等场景见
[docs/部署指南.md](docs/部署指南.md)。

## 模型

`models/` 里放两个可以直接用的推理权重，需求特征与判定口径完全一致，
网页的模型选择器可以自由切换：

| 版本 | 参数量 | 相对位置编码 |
| --- | --- | --- |
| `oooi-scmls-v1-preview` | 10,808,901 | 解码器九档「距离分档＋符号表」 |
| `oooi-scmls-v1.1-preview` | 10,887,548 | 三轴有符号整数格距独立查表的精确编码 |

两个版本都是十二维需求（几何九项、目标三项），不读目标 z、每轮刻数、连续轮数与
每目标负载数——这几个字段只决定验收标准。详细成绩、注册表字段与重新发布权重的步骤见
[models/README.md](models/README.md)。

## 训练数据与合成器

`oooi-scmls-v1.1-preview` 的 170,226 条训练记录由 `data-synthesizers/` 里的四份代码
合成（23,612 + 57,856 + 77,374 + 11,384）。仓库只交付**合成器代码**，不交付数据本体；
怎么构建依赖、怎么跑、怎么把产出接进训练，见
[data-synthesizers/README.md](data-synthesizers/README.md) 与
[docs/模型训练与评估.md](docs/模型训练与评估.md)。

## 本机开发（不用 Docker）

```bash
# 1. 构建 Rust 引擎扩展与前端静态页面（需要 Rust、maturin、Node 20+）
./scripts/build_local_artifacts.sh

# 2. 后端
python3 -m venv .venv && . .venv/bin/activate
pip install -r server/requirements.txt server/wheels/*.whl
uvicorn app.main:app --app-dir server --reload --port 8010

# 3. 生成服务
pip install -r training/requirements.txt
MCSCAI_DATA_DIR=data MCSCAI_MODELS_DIR=models \
  uvicorn training.web.app:app --reload --port 8001

# 4. 前端（开发模式，代理到 8010）
npm --prefix frontend install && npm --prefix frontend run dev
```

## 边界

* 只模拟项目列出的九种方块与活塞臂：粘液块、蜂蜜块、玻璃、铁块、红石块、
  观察者、普通活塞、粘性活塞及活塞臂。不模拟其他方块、实体或区块。
* 不实现 Java 版的 QC、BUD 等机制，也不实现红石粉、红石火把、拉杆、中继器、比较器。
* 模拟会话保存在服务内存里，结构库、打标样本、生成任务持久化到 SQLite；
  数据库不做账号分区，访问同一服务的设备共享结构与标注。
* 生成是逐格自回归解码，CPU 上单任务通常几秒到几十秒，与网格体积和候选数成正比。

## 许可证

MIT，见 [LICENSE](LICENSE)。方块贴图来自 Mojang 的 `bedrock-samples`（同样是 MIT）。
