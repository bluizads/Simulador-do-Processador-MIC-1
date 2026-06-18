# ─────────────────────────────────────────────────────────────────────────────
# MIC-1 Simulator — Dockerfile
# Roda a interface gráfica Pygame via X11 forwarding.
#
# Build:
#   docker build -t mic1-simulator .
#
# Run (Linux):
#   xhost +local:docker
#   docker run -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix mic1-simulator
#
# Run (Windows com VcXsrv):
#   docker run -e DISPLAY=host.docker.internal:0 mic1-simulator
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

LABEL maintainer="MIC-1 Simulator"
LABEL description="Simulador didático da microarquitetura MIC-1 com Pygame"

# Dependências do sistema para Pygame + X11
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Pygame / SDL2
    libsdl2-2.0-0 \
    libsdl2-image-2.0-0 \
    libsdl2-mixer-2.0-0 \
    libsdl2-ttf-2.0-0 \
    # X11 para exibição gráfica
    libx11-6 \
    libxext6 \
    libxrender1 \
    # Fontes
    fonts-dejavu-core \
    # Utils
    xauth \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Criar usuário não-root
RUN useradd -m simulator
WORKDIR /app

# Instalar pygame
COPY requirements.txt .
RUN pip install --no-cache-dir pygame==2.6.0

# Copiar código
COPY --chown=simulator:simulator . .

USER simulator

# Variáveis de ambiente para SDL2 sem áudio (evita erro em containers)
ENV SDL_AUDIODRIVER=dummy
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
