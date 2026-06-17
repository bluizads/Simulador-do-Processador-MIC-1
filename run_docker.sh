#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_docker.sh — Executa o MIC-1 Simulator via Docker (Linux/macOS)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

echo ""
echo "  MIC-1 Simulator — Docker"
echo "  ========================="
echo ""

# Verifica docker
if ! command -v docker &>/dev/null; then
    echo "[ERRO] Docker não encontrado."
    echo "Instale em: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Permite conexão X11 do container
echo "[*] Liberando acesso X11..."
xhost +local:docker 2>/dev/null || true

# Build se necessário
echo "[*] Build da imagem..."
docker build -t mic1-simulator . --quiet

# Run
echo "[*] Iniciando simulador..."
echo ""
docker run --rm \
    -e DISPLAY="$DISPLAY" \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -e SDL_AUDIODRIVER=dummy \
    --name mic1-sim \
    mic1-simulator

echo "[*] Simulador encerrado."
