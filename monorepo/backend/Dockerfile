# syntax=docker/dockerfile:1.7
# ============================================================
# Dockerfile — API de ProyectosYA (FastAPI)
#
# Un solo archivo para los dos entornos:
#   docker build -t proyectosya-api .                 → producción
#   docker build --target dev -t proyectosya-api:dev  → desarrollo
#
# `runtime` va ÚLTIMA a propósito: `docker build` sin --target construye la
# última etapa del archivo, no una llamada "default". Con `dev` al final —como
# estaba antes— cualquier plataforma que construya sin especificar target
# despliega la imagen de desarrollo: con --reload, como root y con torch dentro.
#
# La diferencia de fondo entre los dos entornos es de dónde salen el embedding
# y el reranker. En producción se sirven por API (EMBEDDING_PROVIDER=huggingface,
# RERANKER_PROVIDER=pinecone) y la imagen no lleva ni torch ni onnxruntime. En
# local se corren en proceso (ambos en "local"): no necesita cuentas de terceros
# ni gasta créditos mientras se desarrolla, pero pesa ~1,4 GB más.
# ============================================================


# ------------------------------------------------------------
# Etapa 1: builder — dependencias de runtime
# Las herramientas de compilación se quedan acá y no llegan a ninguna imagen final.
# ------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# venv aislado: se copia entero a la imagen final, sin arrastrar build-essential
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Capa separada de la copia del código: mientras requirements.txt no cambie,
# esta capa se reutiliza y el rebuild es de segundos.
#
# El `id=` del montaje de caché no es opcional: BuildKit lo deriva del target si
# falta, pero el constructor de Railway lo exige explícitamente y falla el build
# con "flag is missing an id argument".
COPY requirements.txt .
RUN --mount=type=cache,id=pip,target=/root/.cache/pip \
    pip install -r requirements.txt


# ------------------------------------------------------------
# Etapa 2: builder-dev — suma los modelos que corren en proceso
# ------------------------------------------------------------
FROM builder AS builder-dev

# PyTorch primero y por separado: sentence-transformers lo instalaría desde
# PyPI, que empaqueta el stack CUDA completo (cuBLAS, cuDNN, NCCL, triton) y
# suma varios GB que nunca usamos, porque el modelo corre en CPU. Esto aplica
# tanto a amd64 como a arm64: PyTorch publica wheels con CUDA para las dos.
# El índice /whl/cpu entrega la variante CPU-only.
COPY requirements-dev.txt .
RUN --mount=type=cache,id=pip,target=/root/.cache/pip \
    pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install -r requirements-dev.txt


# ------------------------------------------------------------
# Etapa 3: base — lo común a las dos imágenes finales, sin dependencias
# ------------------------------------------------------------
FROM python:3.12-slim AS base

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Usuario sin privilegios: el proceso no necesita root
RUN useradd --create-home --uid 1000 app

WORKDIR /app

# Informativo. El puerto real lo decide $PORT en tiempo de ejecución.
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, sys, urllib.request; \
p = os.environ.get('PORT', '8000'); \
sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/health', timeout=4).status == 200 else 1)"


# ------------------------------------------------------------
# Etapa 4: dev — con modelos locales, para usar con bind mount del código
# ------------------------------------------------------------
FROM base AS dev

# root en desarrollo: el bind mount trae los uid/gid del host y con un
# usuario fijo los permisos chocan en Linux. En producción se usa `app`.
USER root

# libgomp1: runtime de OpenMP que necesitan onnxruntime y torch. Solo acá:
# la imagen de producción no lleva ninguno de los dos.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder-dev /opt/venv /opt/venv
COPY . .

# Caché de modelos de HuggingFace. El volumen models_cache del compose se monta
# acá: sin él, bge-m3 (~2 GB) se redescarga cada vez que se recrea el contenedor.
ENV HF_HOME=/models
RUN mkdir -p /models

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --reload"]


# ------------------------------------------------------------
# Etapa 5: runtime (producción) — ÚLTIMA, para que sea el target por defecto
# ------------------------------------------------------------
FROM base AS runtime

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app . .

USER app

# Forma shell y no exec, para que ${PORT} se expanda: las plataformas gestionadas
# (Railway, Heroku, Cloud Run) asignan un puerto por variable de entorno y no
# alcanzan el contenedor si escucha en otro. El `exec` deja a uvicorn como PID 1,
# que es lo que hace que reciba el SIGTERM del apagado y cierre ordenadamente.
#
# Un solo worker a propósito: el scheduler de ingesta arranca dentro del
# lifespan (app/main.py), así que cada worker adicional duplicaría la ingesta
# desde Mercado Público. Para escalar horizontalmente hay que sacar el
# scheduler a un proceso aparte primero (PENDIENTES 3.4).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
