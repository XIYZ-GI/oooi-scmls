# 四个构建目标共用一个文件：`engine`、`backend`、`generation`、`frontend`。
#
# 引擎的 Python 扩展只编译一次，后端与生成服务都从 `engine` 阶段复制同一个 wheel，
# 因此两个镜像里的模拟器版本必然一致。docker compose 通过 `target` 选择目标。

# ===== 阶段 1：编译 Rust 模拟引擎的 Python 扩展 =====
FROM rust:1.88-slim-bookworm AS engine

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv python3-dev \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/build \
    && /opt/build/bin/pip install --no-cache-dir maturin==1.9.1

WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY engine ./engine
RUN PYO3_PYTHON=/opt/build/bin/python \
    /opt/build/bin/maturin build --release --features python \
      --manifest-path engine/Cargo.toml --out /wheels

# ===== 阶段 2：模拟器 / 打标器 / 搜索后端 =====
FROM python:3.11-slim-bookworm AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY server/requirements.txt ./requirements.txt
COPY --from=engine /wheels/*.whl /tmp/
RUN pip install --no-cache-dir -r requirements.txt /tmp/*.whl \
    && rm -rf /tmp/*.whl
COPY server/app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ===== 阶段 3：移动线生成推理服务 =====
FROM python:3.11-slim-bookworm AS generation

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCSCAI_DATA_DIR=/app/data \
    MCSCAI_MODELS_DIR=/app/models

WORKDIR /app
COPY training/requirements.txt ./requirements.txt
# 默认装 CPU 版 PyTorch；要换 CUDA 版本时替换成官方对应的 index-url 即可，
# 镜像会大很多，但推理仍走同一份代码。
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.6.0 \
    && pip install --no-cache-dir -r requirements.txt
COPY --from=engine /wheels/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl
COPY training ./training

EXPOSE 8001
CMD ["uvicorn", "training.web.app:app", "--host", "0.0.0.0", "--port", "8001"]

# ===== 阶段 4：前端工作台静态页面 =====
FROM node:22-bookworm-slim AS frontend-build

WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM nginx:latest AS frontend

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /src/dist /usr/share/nginx/html

EXPOSE 80
