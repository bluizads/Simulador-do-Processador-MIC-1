#!/usr/bin/env bash
set -euo pipefail
echo ""
echo "  MIC-1 Simulator (Pygame) v2.0"
echo "  ================================"
echo ""

python3 --version 2>/dev/null || { echo "[ERRO] Python 3 nao encontrado."; exit 1; }

echo "[*] Instalando pygame..."
pip3 install --quiet pygame 2>/dev/null || pip install --quiet pygame

echo "[*] Iniciando simulador..."
echo "    Controles: ESPACO=Passo  P=Play  R=Reset  E=Editor  ESC=Sair"
echo ""
python3 main.py
