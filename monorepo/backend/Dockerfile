# syntax=docker/dockerfile:1.7
# ============================================================
# Dockerfile — API de ProyectosYA (FastAPI)
#
# Etapas:
#   builder  → compila e instala dependencias en un venv aislado
#   runtime  → imagen final de producción (default)
#   dev      → runtime + uvicorn --reload para desarrollo local
#
# Build de producción:  docker build -t proyectosya-api .
# Build de desarrollo:  docker build --target dev -t proyectosya-api:dev .
# ============================================================


# ------------------------------------------------------------
# Etapa 1: builder
# Instala las dependencias en /opt/venv. Las herramientas de
# compilación se quedan en esta etapa y no llegan a la imagen final.
# ------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# venv aislado: se copia entero al runtime, sin arrastrar el build-essential
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# PyTorch primero y por separado: sentence-transformers lo instalaría desde
# PyPI, que empaqueta el stack CUDA completo (cuBLAS, cuDNN, NCCL, triton) y
# suma varios GB que nunca usamos, porque el modelo corre en CPU. Esto aplica
# tanto a amd64 como a arm64: PyTorch publica wheels con CUDA para las dos.
# El índice /whl/cpu entrega la variante CPU-only.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --index-url https://download.pytorch.org/whl/cpu torch

# Capa separada de la copia del código: mientras requirements.txt no cambie,
# esta capa se reutiliza y el rebuild es de segundos.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt


# ------------------------------------------------------------
# Etapa 2: runtime (producción)
# ------------------------------------------------------------
FROM python:3.12-slim AS runtime

# libgomp1: runtime de OpenMP que necesitan onnxruntime y torch
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Caché de modelos de HuggingFace. Montar un volumen aquí evita
    # redescargar BAAI/bge-m3 (~2 GB) cada vez que se recrea el contenedor.
    HF_HOME=/models

COPY --from=builder /opt/venv /opt/venv

# Usuario sin privilegios: el proceso no necesita root
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /models \
    && chown app:app /models

WORKDIR /app
COPY --chown=app:app . .

USER app
EXPOSE 8000

# start-period generoso: el primer arranque descarga y carga bge-m3 en
# memoria antes de aceptar tráfico.
HEALTHCHECK --interval=30s --timeout=5s --start-period=300s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# Un solo worker a propósito: el scheduler de ingesta arranca dentro del
# lifespan (app/main.py), así que cada worker adicional duplicaría la ingesta
# desde Mercado Público. Para escalar horizontalmente hay que sacar el
# scheduler a un proceso aparte primero.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


# ------------------------------------------------------------
# Etapa 3: dev
# Pensada para usarse con bind mount del código desde el host.
# ------------------------------------------------------------
FROM runtime AS dev

# root en desarrollo: el bind mount trae los uid/gid del host y con un
# usuario fijo los permisos chocan en Linux. En producción se usa `app`.
USER root

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
