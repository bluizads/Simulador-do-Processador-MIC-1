#!/usr/bin/env python3
"""
MIC-1 Simulator — Pygame
===========================
Simulador didático da microarquitetura MIC-1 (Tanenbaum, Cap. 4).

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

sys.path.insert(0, str(Path(__file__).parent))

import pygame

from cpu.cpu import CPU, CPUState, CycleState
from memory.memory import Memory
from microcode.microinstruction import MicrocodeROM, MemOp
from assembler.assembler import Assembler
from cache.cache import Cache, CacheMapping, ReplacementPolicy

logging.basicConfig(level=logging.WARNING)

# ── Resolução e FPS ─────────────────────────────────────────────────────────
WIDTH, HEIGHT = 1400, 860
FPS = 60

# ── Paleta ───────────────────────────────────────────────────────────────────
BG       = (13,  17,  23)
PANEL    = (15,  23,  42)
PANEL2   = (17,  27,  50)
BORDER   = (30,  41,  59)
TEXT     = (226, 232, 240)
TEXT_DIM = (100, 116, 139)
TEXT_MUT = (51,  65,  85)

REG_BG     = (28,  58,  94)
REG_BORD   = (45,  89,  134)
REG_H_BG   = (61,  40,  0)
REG_H_BORD = (180, 83,  9)
REG_ACTIVE = (251, 191, 36)

ALU_BG   = (45,  26,  74)
ALU_BORD = (124, 58,  237)
MEM_BG   = (26,  58,  42)
MEM_BORD = (34,  197, 94)

BUS_A  = (220, 38,  38)
BUS_B  = (22,  163, 74)
BUS_C  = (37,  99,  235)

CYAN   = (56,  189, 248)
GREEN  = (34,  197, 94)
RED    = (239, 68,  68)
YELLOW = (251, 191, 36)
PURPLE = (167, 139, 250)
ORANGE = (251, 146, 60)
PINK   = (244, 114, 182)

HIT_COLOR  = (34,  197, 94)   # verde = hit
MISS_COLOR = (239, 68,  68)   # vermelho = miss


def font(size: int, bold: bool = False) -> pygame.font.Font:
    name = pygame.font.match_font("consolas,dejavusansmono,monospace")
    f = pygame.font.Font(name, size)
    if bold:
        f.set_bold(True)
    return f


# ── Simulador ────────────────────────────────────────────────────────────────

class Simulator:
    """Encapsula CPU, memória, ROM e caches."""

    STACK_BASE = 0x1000

    def __init__(self) -> None:
        self.memory  = Memory(size=64 * 1024)
        self.rom     = MicrocodeROM()
        self.cpu     = CPU(self.memory, self.rom)

        # I-Cache: mapeamento direto, 64 sets, bloco=4 palavras
        self.icache = Cache(
            size_bytes=1024, block_size=4, ways=1,
            mapping=CacheMapping.DIRECT,
            policy=ReplacementPolicy.LRU,
            name="I-Cache",
        )
        # D-Cache: 2-way set associative, 32 sets
        self.dcache = Cache(
            size_bytes=1024, block_size=4, ways=2,
            mapping=CacheMapping.SET_ASSOC,
            policy=ReplacementPolicy.LRU,
            name="D-Cache",
        )

        self.last_state: CycleState | None = None
        self.cycle_log: list[str] = []

        # Últimos eventos de cache para animação
        self.last_icache_hit: bool | None = None
        self.last_dcache_hit: bool | None = None
        self.cache_flash_timer = 0.0

    def load_program(self, binary: bytes) -> None:
        self.reset()
        self.memory.load_program(binary, 0)

    def reset(self) -> None:
        self.cpu.reset()
        self.memory.reset()
        self.icache.reset_stats()
        self.dcache.reset_stats()
        self.last_state = None
        self.last_icache_hit = None
        self.last_dcache_hit = None
        self.cycle_log.clear()

    def step(self) -> bool:
        if self.cpu.state in (CPUState.HALTED, CPUState.ERROR):
            return False
        try:
            state = self.cpu.step()
            self.last_state = state

            # Simula acesso à I-Cache em cada fetch de instrução
            if state.microinstruction.mem_op & MemOp.FETCH:
                pc = self.cpu.registers.read("PC")
                hit, _ = self.icache.access(pc >> 2)   # endereço de palavra
                self.last_icache_hit = hit

            # Simula acesso à D-Cache em leituras/escritas de dados
            if state.mem_address is not None:
                if state.microinstruction.mem_op & MemOp.READ or state.microinstruction.mem_op & MemOp.WRITE:
                    hit, _ = self.dcache.access(
                        state.mem_address >> 2,
                        write=bool(state.microinstruction.mem_op & MemOp.WRITE),
                    )
                    self.last_dcache_hit = hit

            self.cache_flash_timer = 0.5

            self.cycle_log.append(
                f"#{state.cycle_number:4d}  "
                f"MPC={state.mic_pc:03X}  "
                f"{state.description[:55]}"
            )
            if len(self.cycle_log) > 300:
                self.cycle_log.pop(0)
            return True
        except Exception as e:
            self.cycle_log.append(f"ERRO: {e}")
            return False

    @property
    def mem_op(self) -> int:
        return self.last_state.microinstruction.mem_op if self.last_state else 0


# ── Programa demo padrão ─────────────────────────────────────────────────────

FILE_SOURCE = 'examples/fibonacci.asm'


# ── Aplicação principal ───────────────────────────────────────────────────────

class App:
    SOURCE: str

    @staticmethod
    def get_source() -> None:
        with open(FILE_SOURCE) as f:
            App.SOURCE = f.read()


    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("MIC-1 Simulator — Pygame")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock  = pygame.time.Clock()

        # Fontes
        self.f_big   = font(17, bold=True)
        self.f_title = font(14, bold=True)
        self.f_label = font(12, bold=True)
        self.f_mono  = font(12)
        self.f_small = font(10)
        self.f_tiny  = font(9)

        self.sim = Simulator()

        # Controle de execução
        self.running_continuous = False
        self.clock_hz  = 4
        self._accum    = 0.0

        # Painel direito (0=microcódigo, 1=memória)
        self.right_panel = 0

        # Editor
        self.editor_open   = False
        self.editor_text   = App.SOURCE
        self.editor_cursor = len(App.SOURCE)
        self.editor_msg    = ""
        self.editor_msg_ok = True

        # Registradores destacados
        self.active_regs:  set[str] = set()
        self.flash_timer = 0.0

        # Carga inicial
        self._assemble_and_load(App.SOURCE, close_editor=False)

        # Layout dos registradores no diagrama
        self._build_reg_layout()

    # ── Montagem ─────────────────────────────────────────────────────────────

    def _assemble_and_load(self, source: str, close_editor: bool = True) -> None:
        result = Assembler().assemble(source)
        if result.success:
            self.sim.load_program(result.binary)
            self.editor_msg = (
                f"OK: {len(result.binary)} bytes, "
                f"{len(result.symbol_table)} símbolos"
            )
            self.editor_msg_ok = True
            if close_editor:
                self.editor_open = False
        else:
            msgs = " | ".join(
                f"L{e.line}: {e.message}" for e in result.errors[:3]
            )
            self.editor_msg    = f"ERRO: {msgs}"
            self.editor_msg_ok = False

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build_reg_layout(self) -> None:
        """Posições dos blocos de registrador no diagrama."""
        x, w, h, gap = 32, 108, 34, 6
        positions = [
            ("PC",  30), ("MBR", 70), ("MAR", 110), ("MDR", 150),
            ("SP",  200), ("LV",  240), ("CPP", 280),
            ("TOS", 320), ("OPC", 360), ("H",   410),
        ]
        self.reg_rects: dict[str, pygame.Rect] = {}
        for name, y in positions:
            self.reg_rects[name] = pygame.Rect(x, y, w, h)

    # ── Loop ─────────────────────────────────────────────────────────────────

    def run(self) -> None:
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            if not self._handle_events():
                break
            self._update(dt)
            self._draw()
            pygame.display.flip()
        pygame.quit()

    def _handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if self.editor_open:
                    self._editor_key(event)
                    continue
                if   event.key == pygame.K_ESCAPE: return False
                elif event.key == pygame.K_SPACE:  self._do_step()
                elif event.key == pygame.K_p:      self.running_continuous = not self.running_continuous
                elif event.key == pygame.K_r:
                    self.sim.reset()
                    self.active_regs.clear()
                    self.running_continuous = False
                elif event.key == pygame.K_UP:   self.clock_hz = min(60, self.clock_hz + 1)
                elif event.key == pygame.K_DOWN: self.clock_hz = max(1, self.clock_hz - 1)
                elif event.key == pygame.K_e:    self.editor_open = True
                elif event.key == pygame.K_TAB:  self.right_panel ^= 1
        return True

    def _editor_key(self, ev: pygame.event.Event) -> None:
        k = ev.key
        ctrl = bool(ev.mod & pygame.KMOD_CTRL)
        if k == pygame.K_ESCAPE:
            self.editor_open = False
        elif k == pygame.K_RETURN and ctrl:
            self._assemble_and_load(self.editor_text)
        elif k == pygame.K_RETURN:
            self._insert("\n")
        elif k == pygame.K_BACKSPACE:
            if self.editor_cursor > 0:
                self.editor_text   = self.editor_text[:self.editor_cursor-1] + self.editor_text[self.editor_cursor:]
                self.editor_cursor -= 1
        elif k == pygame.K_DELETE:
            if self.editor_cursor < len(self.editor_text):
                self.editor_text = self.editor_text[:self.editor_cursor] + self.editor_text[self.editor_cursor+1:]
        elif k == pygame.K_LEFT:  self.editor_cursor = max(0, self.editor_cursor-1)
        elif k == pygame.K_RIGHT: self.editor_cursor = min(len(self.editor_text), self.editor_cursor+1)
        elif k == pygame.K_HOME:
            ls = self.editor_text.rfind("\n", 0, self.editor_cursor) + 1
            self.editor_cursor = ls
        elif k == pygame.K_END:
            le = self.editor_text.find("\n", self.editor_cursor)
            self.editor_cursor = le if le >= 0 else len(self.editor_text)
        elif k == pygame.K_TAB:
            self._insert("    ")
        elif ev.unicode and ev.unicode.isprintable():
            self._insert(ev.unicode)

    def _insert(self, s: str) -> None:
        self.editor_text   = self.editor_text[:self.editor_cursor] + s + self.editor_text[self.editor_cursor:]
        self.editor_cursor += len(s)

    def _do_step(self) -> None:
        ok = self.sim.step()
        if ok and self.sim.last_state:
            self.active_regs = set(self.sim.last_state.changed_registers)
            self.flash_timer = 0.45
        if not ok:
            self.running_continuous = False

    def _update(self, dt: float) -> None:
        if self.flash_timer > 0:
            self.flash_timer -= dt
            if self.flash_timer <= 0:
                self.active_regs.clear()

        if self.sim.cache_flash_timer > 0:
            self.sim.cache_flash_timer -= dt

        if self.running_continuous and not self.editor_open:
            self._accum += dt
            interval = 1.0 / self.clock_hz
            while self._accum >= interval:
                self._accum -= interval
                self._do_step()
                if self.sim.cpu.state in (CPUState.HALTED, CPUState.ERROR):
                    self.running_continuous = False
                    break

    # ── Desenho principal ─────────────────────────────────────────────────────

    def _draw(self) -> None:
        self.screen.fill(BG)
        self._draw_topbar()
        self._draw_datapath()
        self._draw_reg_panel()
        self._draw_cache_panel()
        self._draw_right_panel()
        self._draw_log()
        if self.editor_open:
            self._draw_editor()

    # ── Barra superior ────────────────────────────────────────────────────────

    def _draw_topbar(self) -> None:
        r = pygame.Rect(0, 0, WIDTH, 44)
        pygame.draw.rect(self.screen, PANEL, r)
        pygame.draw.line(self.screen, BORDER, (0, 44), (WIDTH, 44), 1)

        self._txt("MIC-1", 12, 12, self.f_big, CYAN)

        st = self.sim.cpu.state.name
        sc = {
            "RUNNING": GREEN, "HALTED": RED, "ERROR": RED,
            "RESET": TEXT_DIM, "PAUSED": YELLOW,
        }.get(st, TEXT_DIM)
        if self.running_continuous:
            st, sc = "EXECUTANDO", GREEN
        self._txt(f"CPU: {st}", 105, 14, self.f_label, sc)
        self._txt(f"Ciclo: {self.sim.cpu.cycle_count:,}", 290, 14, self.f_label, TEXT)
        self._txt(f"MPC: {self.sim.cpu.mic_pc:03X}", 450, 14, self.f_label, YELLOW)
        self._txt(f"Vel: {self.clock_hz} Hz", 570, 14, self.f_small, TEXT_DIM)

        help_str = "SPC=Passo  P=Play  R=Reset  ↑↓=Vel  E=Editor  TAB=Painel  ESC=Sair"
        self._txt(help_str, WIDTH - 590, 15, self.f_small, TEXT_MUT)

    # ── Datapath ──────────────────────────────────────────────────────────────

    def _draw_datapath(self) -> None:
        # Área do datapath
        ax, ay, aw, ah = 8, 52, 420, HEIGHT - 230
        pygame.draw.rect(self.screen, PANEL, (ax, ay, aw, ah), border_radius=4)
        pygame.draw.rect(self.screen, BORDER, (ax, ay, aw, ah), 1, border_radius=4)
        self._txt("DATAPATH  MIC-1", ax+10, ay+6, self.f_label, CYAN)

        snap = self.sim.cpu.registers.snapshot()

        # Barramentos verticais
        rx     = ax + 30           # borda direita dos registradores
        bus_ax = rx + 100                 # barramento A
        bus_bx = rx + 180                 # barramento B
        top_y  = ay + 30
        alu_y  = ay + 500

        pygame.draw.line(self.screen, BUS_A, (bus_ax, 480), (bus_ax, alu_y+8), 3)
        pygame.draw.line(self.screen, BUS_B, (bus_bx, top_y), (bus_bx, alu_y+8), 3)
        self._txt("A", bus_ax-8, 520, self.f_small, BUS_A)
        self._txt("B", bus_bx+4, top_y+140, self.f_small, BUS_B)

        # Registradores
        for name, rect in self.reg_rects.items():
            r = rect.move(ax + 30, ay)
            self._draw_reg_block(name, r, snap.get(name, 0))

        # Linhas dos registradores para os barramentos
        for name, rect in self.reg_rects.items():
            r = rect.move(ax, ay)
            pygame.draw.line(self.screen, (30,60,30), (r.right + 30, r.centery+2), (bus_bx, r.centery+2), 1)

        # ALU (trapézio)
        alux = bus_bx - 100
        aluw, aluh = 120, 66
        pts = [
            (alux, alu_y), (alux+aluw, alu_y),
            (alux+aluw-18, alu_y+aluh), (alux+18, alu_y+aluh),
        ]
        last = self.sim.last_state
        alu_act = last is not None
        pygame.draw.polygon(self.screen, (76,29,149) if alu_act else ALU_BG, pts)
        pygame.draw.polygon(self.screen, ALU_BORD, pts, 2)
        self._txt("ALU+SHIFT", alux+12, alu_y+5,  self.f_small, ALU_BORD)
        op = last.microinstruction.alu_op.name if last else "—"
        self._txt(op[:10],    alux+12, alu_y+22, self.f_mono,  TEXT)
        n_f = last.n_flag if last else False
        z_f = last.z_flag if last else False
        fc  = YELLOW if (n_f or z_f) else TEXT_DIM
        self._txt(f"N={int(n_f)} Z={int(z_f)}", alux+12, alu_y+44, self.f_small, fc)

        # Barramento C
        bus_cx = alux + aluw + 22
        pygame.draw.line(self.screen, BUS_C, (alux+aluw//2, alu_y+aluh), (bus_cx, alu_y+aluh), 2)
        pygame.draw.line(self.screen, BUS_C, (bus_cx, alu_y+aluh), (bus_cx, top_y), 3)
        self._txt("C", bus_cx+4, top_y+90, self.f_small, BUS_C)
        for _, rect in self.reg_rects.items():
            r = rect.move(ax, ay)
            pygame.draw.line(self.screen, (20,40,80), (r.right + 30, r.centery-5), (bus_cx, r.centery-5), 1)

        # Memória principal
        mx  = bus_cx + 20
        mw  = ax + aw - mx - 8
        if mw > 40:
            mem_r = pygame.Rect(mx, ay+28, mw, 130)
            pygame.draw.rect(self.screen, MEM_BG,   mem_r, border_radius=3)
            pygame.draw.rect(self.screen, MEM_BORD, mem_r, 2, border_radius=3)
            self._txt("MEMÓRIA", mem_r.x+5, mem_r.y+4, self.f_small, MEM_BORD)
            data = self.sim.memory.snapshot()
            for i in range(5):
                a2 = i * 4
                v  = int.from_bytes(data[a2:a2+4], "big")
                hl = last is not None and last.mem_address == a2
                self._txt(f"{a2:04X}:{v:08X}", mem_r.x+5, mem_r.y+22+i*18, self.f_tiny,
                          YELLOW if hl else TEXT_DIM)
            if last and last.mem_address is not None:
                op2 = "WR" if last.mem_is_write else "RD"
                self._txt(f"{op2}@{last.mem_address:04X}", mem_r.x+5, mem_r.y+115, self.f_small, YELLOW)

        # Legenda
        ly = ay + ah - 62
        for i, (col, lbl) in enumerate([
            (BUS_A,"Bus A (H→ALU)"), (BUS_B,"Bus B (regs→ALU)"), (BUS_C,"Bus C (ALU→regs)")
        ]):
            y2 = ly + i*18
            pygame.draw.line(self.screen, col, (ax+10, y2+7), (ax+30, y2+7), 3)
            self._txt(lbl, ax+36, y2, self.f_small, TEXT_DIM)

    def _draw_reg_block(self, name: str, rect: pygame.Rect, value: int) -> None:
        active = name in self.active_regs
        is_h   = name == "H"
        bg     = (60,60,10) if active else (REG_H_BG if is_h else REG_BG)
        bord   = REG_ACTIVE if active else (REG_H_BORD if is_h else REG_BORD)
        pygame.draw.rect(self.screen, bg,   rect, border_radius=3)
        pygame.draw.rect(self.screen, bord, rect, 2 if active else 1, border_radius=3)
        self._txt(name, rect.x+4, rect.y+2, self.f_small, TEXT_DIM)
        bits   = 8 if name == "MBR" else 32
        digits = bits // 4
        v      = value & ((1 << bits)-1)
        self._txt(f"{v:0{digits}X}", rect.x+4, rect.y+16, self.f_mono,
                  REG_ACTIVE if active else CYAN)

    # ── Painel de registradores ───────────────────────────────────────────────

    def _draw_reg_panel(self) -> None:
        ax, ay, aw, ah = 435, 52, 246, HEIGHT-230
        pygame.draw.rect(self.screen, PANEL, (ax,ay,aw,ah), border_radius=4)
        pygame.draw.rect(self.screen, BORDER,(ax,ay,aw,ah), 1, border_radius=4)
        self._txt("REGISTRADORES", ax+8, ay+6, self.f_label, CYAN)

        snap  = self.sim.cpu.registers.snapshot()
        names = ["PC","MAR","MDR","MBR","SP","LV","CPP","TOS","OPC","H"]
        y = ay+28

        for name in names:
            val  = snap.get(name, 0)
            bits = 8 if name == "MBR" else 32
            mask = (1<<bits)-1
            v    = val & mask
            sgn  = v-(1<<bits) if v>=(1<<(bits-1)) else v

            row  = pygame.Rect(ax+6, y, aw-12, 35)
            act  = name in self.active_regs
            pygame.draw.rect(self.screen, (40,40,10) if act else PANEL2, row, border_radius=3)
            pygame.draw.rect(self.screen, BORDER, row, 1, border_radius=3)

            nc = REG_ACTIVE if act else TEXT_DIM
            self._txt(name, row.x+5, row.y+2, self.f_small, nc)

            digits = bits // 4
            self._txt(f"0x{v:0{digits}X}", row.x+5, row.y+17, self.f_mono,
                      REG_ACTIVE if act else CYAN)
            self._txt(f"={sgn}", row.x+digits*8+18, row.y+19, self.f_tiny, TEXT_MUT)

            y += 39

        # Estatísticas
        self._txt(f"Ciclos: {self.sim.cpu.cycle_count:,}", ax+8, y+4, self.f_small, TEXT_DIM)
        mc = self.sim.cpu.mic_pc
        self._txt(f"MPC: {mc:03X}", ax+8, y+18, self.f_small, YELLOW)

    # ── Painel de Cache ───────────────────────────────────────────────────────

    def _draw_cache_panel(self) -> None:
        """Exibe I-Cache e D-Cache com hits/misses e barra visual."""
        ax, ay = 685, 52
        aw, ah = 240, HEIGHT - 230

        pygame.draw.rect(self.screen, PANEL,  (ax, ay, aw, ah), border_radius=4)
        pygame.draw.rect(self.screen, BORDER, (ax, ay, aw, ah), 1, border_radius=4)
        self._txt("CACHE", ax+8, ay+6, self.f_label, ORANGE)

        y = ay + 30

        for cache_obj, name, flash_val, color in [
            (self.sim.icache, "I-Cache", self.sim.last_icache_hit, CYAN),
            (self.sim.dcache, "D-Cache", self.sim.last_dcache_hit, PINK),
        ]:
            # Título do cache
            self._txt(name, ax+8, y, self.f_label, color)
            y += 18

            hits   = cache_obj.hits
            misses = cache_obj.misses
            total  = hits + misses
            rate   = hits / total if total > 0 else 0.0

            # Barra de hit rate
            bar_w = aw - 20
            bar_h = 14
            bar_r = pygame.Rect(ax+8, y, bar_w, bar_h)
            pygame.draw.rect(self.screen, BORDER, bar_r, border_radius=3)
            fill_w = int(bar_w * rate)
            if fill_w > 0:
                rate_color = (
                    HIT_COLOR  if rate >= 0.7 else
                    YELLOW     if rate >= 0.4 else
                    MISS_COLOR
                )
                pygame.draw.rect(self.screen, rate_color,
                                 pygame.Rect(ax+8, y, fill_w, bar_h), border_radius=3)
            self._txt(f"{rate*100:.1f}%", ax + bar_w - 30, y, self.f_tiny, TEXT)
            y += 18

            # Contadores
            self._txt(f"Hits:   {hits:5d}", ax+8,      y, self.f_small, HIT_COLOR)
            self._txt(f"Misses: {misses:5d}", ax+8, y+14, self.f_small, MISS_COLOR)
            self._txt(f"Total:  {total:5d}", ax+8, y+28, self.f_small, TEXT_DIM)
            y += 44

            # Flash do último acesso
            if flash_val is not None and self.sim.cache_flash_timer > 0.1:
                msg   = "▶ HIT"  if flash_val else "▶ MISS"
                mcol  = HIT_COLOR if flash_val else MISS_COLOR
                self._txt(msg, ax+8, y, self.f_label, mcol)
            y += 20

            # Config do cache
            self._txt(
                f"{cache_obj.num_sets}sets × {cache_obj.num_ways}way",
                ax+8, y, self.f_tiny, TEXT_MUT,
            )
            y += 18

            # Visualização de sets (miniatura)
            max_sets_vis = min(cache_obj.num_sets, 16)
            cell_w = max(4, (aw-20) // max_sets_vis)
            cell_h = 10
            for si in range(max_sets_vis):
                cset  = cache_obj.sets[si]
                valid = any(ln.valid for ln in cset.lines)
                col   = (34,100,60) if valid else (30,41,59)
                pygame.draw.rect(self.screen, col,
                                 pygame.Rect(ax+8+si*cell_w, y, cell_w-1, cell_h),
                                 border_radius=1)
            if cache_obj.num_sets > max_sets_vis:
                self._txt("...", ax+8+max_sets_vis*cell_w+2, y, self.f_tiny, TEXT_MUT)
            y += cell_h + 4

            # Separador
            pygame.draw.line(self.screen, BORDER, (ax+8, y), (ax+aw-8, y), 1)
            y += 10

        # Rodapé com config
        self._txt("I-Cache: mapeamento direto", ax+8, y,    self.f_tiny, TEXT_MUT)
        self._txt("D-Cache: 2-way assoc LRU",  ax+8, y+12, self.f_tiny, TEXT_MUT)

    # ── Painel direito (microcódigo / memória) ────────────────────────────────

    def _draw_right_panel(self) -> None:
        ax, ay, aw, ah = 930, 52, WIDTH-935, HEIGHT-230
        pygame.draw.rect(self.screen, PANEL,  (ax,ay,aw,ah), border_radius=4)
        pygame.draw.rect(self.screen, BORDER, (ax,ay,aw,ah), 1, border_radius=4)

        if self.right_panel == 0:
            self._txt("MICROCÓDIGO ROM  [TAB=Memória]", ax+8, ay+6, self.f_label, PURPLE)
            self._draw_microcode(ax, ay, aw, ah)
        else:
            self._txt("MEMÓRIA PRINCIPAL  [TAB=Micro]", ax+8, ay+6, self.f_label, GREEN)
            self._draw_memory(ax, ay, aw, ah)

    def _draw_microcode(self, ax, ay, aw, ah) -> None:
        last = self.sim.last_state
        mpc  = self.sim.cpu.mic_pc

        # Detalhe atual
        detail = last.description if last else "Aguardando execução..."
        dr = pygame.Rect(ax+6, ay+28, aw-12, 32)
        pygame.draw.rect(self.screen, PANEL2, dr, border_radius=3)
        pygame.draw.rect(self.screen, BORDER, dr, 1, border_radius=3)
        self._txt(detail[:60], dr.x+5, dr.y+4,  self.f_small, GREEN)
        self._txt(detail[60:120], dr.x+5, dr.y+17, self.f_tiny, TEXT_DIM)

        entries = self.sim.rom.entries()
        addrs   = sorted(entries.keys())
        idx     = addrs.index(mpc) if mpc in addrs else 0
        start   = max(0, idx - 8)
        visible = addrs[start:start+20]

        y = ay + 66
        for addr in visible:
            instr   = entries[addr]
            is_cur  = addr == mpc
            row     = pygame.Rect(ax+6, y, aw-12, 19)
            if is_cur:
                pygame.draw.rect(self.screen, (20,50,0), row, border_radius=2)

            c_addr  = YELLOW   if is_cur else TEXT_MUT
            c_lbl   = GREEN    if is_cur else TEXT_DIM
            c_op    = PURPLE   if is_cur else (60,60,100)
            c_nxt   = YELLOW   if is_cur else TEXT_MUT

            self._txt(f"{addr:03X}", row.x+3,   row.y+2, self.f_small, c_addr)
            self._txt((instr.label or "—")[:10], row.x+42, row.y+2, self.f_small, c_lbl)
            self._txt(instr.alu_op.name[:9], row.x+130, row.y+2, self.f_tiny,  c_op)
            self._txt(f"→{instr.next_addr:03X}", row.x+220, row.y+2, self.f_tiny, c_nxt)
            y += 21

    def _draw_memory(self, ax, ay, aw, ah) -> None:
        last    = self.sim.last_state
        hl_addr = last.mem_address if last else None
        data    = self.sim.memory.snapshot()
        bpr     = 8
        base    = 0
        if hl_addr is not None:
            base = max(0, (hl_addr // (bpr*4)) * (bpr*4) - bpr*4*2)

        y    = ay + 32
        rows = (ah - 45) // 17

        for ri in range(rows):
            addr  = base + ri * bpr * 4
            if addr >= len(data): break
            chunk = data[addr:addr+bpr*4]
            hexs  = " ".join(f"{b:02X}" for b in chunk)
            hl    = hl_addr is not None and addr <= hl_addr < addr + bpr*4
            if hl:
                pygame.draw.rect(self.screen, (40,30,0),
                                 pygame.Rect(ax+6,y-2,aw-12,16), border_radius=2)
            self._txt(f"{addr:04X}", ax+8,    y, self.f_small, YELLOW if hl else TEXT_DIM)
            self._txt(hexs,          ax+52,   y, self.f_tiny,  CYAN if hl else TEXT_MUT)
            y += 17

    # ── Log ───────────────────────────────────────────────────────────────────

    def _draw_log(self) -> None:
        ax, ay = 8, HEIGHT-172
        aw, ah = WIDTH-16, 164
        pygame.draw.rect(self.screen, PANEL,  (ax,ay,aw,ah), border_radius=4)
        pygame.draw.rect(self.screen, BORDER, (ax,ay,aw,ah), 1, border_radius=4)
        self._txt("LOG DE EXECUÇÃO", ax+8, ay+5, self.f_label, TEXT_DIM)
        self._txt("E=Editor de Assembly IJVM", ax+aw-200, ay+5, self.f_small, TEXT_MUT)

        max_lines = (ah-28) // 15
        lines     = self.sim.cycle_log[-max_lines:]
        y         = ay + 24
        for line in lines:
            col = RED if "ERRO" in line else TEXT_DIM
            self._txt(line, ax+8, y, self.f_small, col)
            y += 15
        if not lines:
            self._txt("(nenhum ciclo executado — pressione ESPAÇO ou P)", ax+8, y, self.f_small, TEXT_MUT)

    # ── Editor ────────────────────────────────────────────────────────────────

    def _draw_editor(self) -> None:
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((0,0,0,185))
        self.screen.blit(ov, (0,0))

        m  = 60
        ar = pygame.Rect(m, m, WIDTH-m*2, HEIGHT-m*2)
        pygame.draw.rect(self.screen, PANEL,  ar, border_radius=6)
        pygame.draw.rect(self.screen, PURPLE, ar, 2, border_radius=6)

        self._txt("EDITOR DE ASSEMBLY IJVM", ar.x+12, ar.y+10, self.f_title, PURPLE)
        self._txt("Ctrl+Enter=Montar e Carregar   ESC=Fechar",
                  ar.right-360, ar.y+12, self.f_small, TEXT_DIM)

        tr = pygame.Rect(ar.x+10, ar.y+38, ar.width-20, ar.height-80)
        pygame.draw.rect(self.screen, BG,     tr, border_radius=3)
        pygame.draw.rect(self.screen, BORDER, tr, 1, border_radius=3)

        lines    = self.editor_text.split("\n")
        cur_line, cur_col = self._cursor_pos()
        lh       = 17
        max_vis  = (tr.height-10) // lh
        start_l  = max(0, cur_line - max_vis + 3)

        y = tr.y + 6
        for i, line in enumerate(lines[start_l:start_l+max_vis]):
            real_i = start_l + i
            # Número da linha
            self._txt(f"{real_i+1:3d}", tr.x+3, y, self.f_tiny, TEXT_MUT)
            # Colorização simples
            stripped = line.lstrip()
            if stripped.startswith("//"):
                col = TEXT_MUT
            elif stripped and stripped.split()[0].upper() in (
                "BIPUSH","ILOAD","ISTORE","IADD","ISUB","IAND","IOR",
                "DUP","POP","SWAP","GOTO","IFEQ","IFLT","HALT","NOP"
            ):
                col = PINK
            elif stripped.startswith("."):
                col = PURPLE
            else:
                col = TEXT
            self._txt(line, tr.x+36, y, self.f_mono, col)
            # Cursor
            if real_i == cur_line:
                cx = tr.x + 36 + self.f_mono.size(line[:cur_col])[0]
                pygame.draw.line(self.screen, CYAN, (cx, y), (cx, y+lh-2), 2)
            y += lh

        # Mensagem de status
        mc = HIT_COLOR if self.editor_msg_ok else RED
        self._txt(self.editor_msg or "Ctrl+Enter para montar",
                  ar.x+12, ar.bottom-32, self.f_small, mc)

    def _cursor_pos(self) -> tuple[int, int]:
        txt  = self.editor_text[:self.editor_cursor]
        line = txt.count("\n")
        col  = self.editor_cursor - (txt.rfind("\n") + 1)
        return line, col

    # ── Helper de texto ───────────────────────────────────────────────────────

    def _txt(self, text: str, x: int, y: int,
             fnt: pygame.font.Font, color: tuple) -> None:
        self.screen.blit(fnt.render(str(text), True, color), (x, y))


def main() -> int:
    App.get_source()
    app = App()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
