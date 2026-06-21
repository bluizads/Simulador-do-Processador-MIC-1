#!/usr/bin/env python3
"""
MIC-1 Simulator — Pygame
===========================
Simulador da microarquitetura MIC-1 (Tanenbaum, Cap. 4).

Componentes visíveis na tela:
  - Datapath: registradores, barramentos A/B/C, ALU+Shifter, Memória
  - Cache de Instruções (I-Cache) com hits/misses em tempo real
  - Cache de Dados (D-Cache) com hits/misses em tempo real
  - Painel de registradores (hex/dec/bin)
  - Microcódigo ROM ou Dump de Memória (alterna com TAB)
  - Log de execução
  - Editor de Assembly IJVM embutido

Controles:
  ESPAÇO   — próximo ciclo (step)
  P        — play/pause (execução contínua)
  R        — reset
  ↑ / ↓    — ajustar velocidade
  E        — abrir/fechar editor de assembly
  Ctrl+Enter (no editor) — montar e carregar
  TAB      — alternar painel direito (microcódigo / memória)
  ESC      — sair
"""

from __future__ import annotations
import sys
import logging
from pathlib import Path

from app.app import App

sys.path.insert(0, str(Path(__file__).parent))
logging.basicConfig(level=logging.WARNING)


def main() -> int:
    app = App('examples/fibonacci.asm')
    app.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())
