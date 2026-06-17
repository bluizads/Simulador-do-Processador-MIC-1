"""
MIC-1 CPU Execution Engine
============================
Core simulation engine executing the MIC-1 data path cycle:
  1. Decode microinstruction
  2. Drive A-bus and B-bus
  3. ALU compute
  4. Shifter
  5. Drive C-bus (write back)
  6. Memory operations
  7. Determine next microinstruction address
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional

from cpu.registers import RegisterFile
from cpu.alu import ALU, ALUOperation, ShifterOperation
from memory.memory import Memory
from microcode.microinstruction import (
    Microinstruction, MicrocodeROM, BBusSource, CBusDest, MemOp
)

logger = logging.getLogger(__name__)

# Observer callbacks
CycleObserver = Callable[["CycleState"], None]


class CPUState(Enum):
    """CPU execution state machine."""
    RESET   = auto()
    RUNNING = auto()
    PAUSED  = auto()
    HALTED  = auto()
    ERROR   = auto()


@dataclass
class CycleState:
    """
    Complete state snapshot of one MIC-1 clock cycle.
    Used for animation, logging, and undo/redo.
    """
    cycle_number:    int
    mic_pc:          int                      # Current microinstruction address
    microinstruction: Microinstruction
    register_snapshot: Dict[str, int]         # All register values before
    alu_a:           int = 0
    alu_b:           int = 0
    alu_result:      int = 0
    n_flag:          bool = False
    z_flag:          bool = False
    next_mic_pc:     int = 0
    active_c_bus:    int = 0                  # CBusDest bitmask
    mem_address:     Optional[int] = None
    mem_data:        Optional[int] = None
    mem_is_write:    bool = False
    changed_registers: List[str] = field(default_factory=list)
    description:     str = ""


class CPU:
    """
    MIC-1 Central Processing Unit.
    
    Implements the complete MIC-1 data path:
    - Register file (MAR, MDR, PC, MBR, SP, LV, CPP, TOS, OPC, H)
    - ALU with shifter
    - Microcode ROM (512 × 36-bit)
    - Main memory interface
    - Cycle-by-cycle execution with observer notifications
    
    Supports:
    - Single-step execution
    - Continuous run with configurable clock speed
    - Snapshot/restore for rewind
    """

    MBR_SIGN_BIT = 0x80

    # Endereço inicial da pilha (SP/LV). Na MIC-1 real este valor é
    # carregado pelo bootstrap; aqui usamos um endereço fixo de forma
    # que a área de programa (a partir de 0x0000) e a área de pilha
    # não se sobreponham para programas pequenos.
    STACK_BASE = 0x1000

    def __init__(
        self,
        memory: Memory,
        rom: Optional[MicrocodeROM] = None,
    ) -> None:
        self._memory = memory
        self._rom    = rom or MicrocodeROM()
        self._regs   = RegisterFile()
        self._alu    = ALU()
        
        self._state          = CPUState.RESET
        self._mic_pc: int    = 0      # Micro Program Counter
        self._cycle_count: int = 0
        self._instr_count: int = 0
        
        self._cycle_observers: List[CycleObserver] = []
        self._state_observers: List[Callable[[CPUState, CPUState], None]] = []
        self._history: List[CycleState] = []   # for rewind
        self._max_history = 500

        # Inicializa SP e LV apontando para a base da pilha
        self._regs.write("SP", self.STACK_BASE)
        self._regs.write("LV", self.STACK_BASE)

        logger.info("CPU initialized")

    # ------------------------------------------------------------------ #
    # Public control API                                                   #
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        """Reset CPU to initial state."""
        self._regs.reset_all()
        self._regs.write("SP", self.STACK_BASE)
        self._regs.write("LV", self.STACK_BASE)
        self._mic_pc      = 0
        self._cycle_count = 0
        self._instr_count = 0
        self._history.clear()
        self._set_state(CPUState.RESET)
        logger.info("CPU reset")

    def step(self) -> CycleState:
        """
        Execute exactly one MIC-1 clock cycle.
        
        Returns:
            CycleState describing what happened this cycle
        """
        if self._state == CPUState.HALTED:
            raise RuntimeError("CPU is halted; reset to continue")
        if self._state == CPUState.ERROR:
            raise RuntimeError("CPU in ERROR state; reset to continue")

        self._set_state(CPUState.RUNNING)

        try:
            state = self._execute_cycle()
        except Exception as e:
            logger.error("CPU cycle error: %s", e)
            self._set_state(CPUState.ERROR)
            raise

        self._history.append(state)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        for obs in self._cycle_observers:
            try:
                obs(state)
            except Exception as e:
                logger.error("Cycle observer error: %s", e)

        # Check for HALT (microinstruction loops to itself at address 0xFF)
        if self._mic_pc == 0xFF and state.mic_pc == 0xFF:
            self._set_state(CPUState.HALTED)
            logger.info("CPU halted at cycle %d", self._cycle_count)
        
        return state

    def run(self, max_cycles: int = 100_000) -> int:
        """
        Run CPU continuously until HALT or max_cycles reached.
        
        Returns:
            Number of cycles executed
        """
        executed = 0
        while self._state not in (CPUState.HALTED, CPUState.ERROR):
            self.step()
            executed += 1
            if executed >= max_cycles:
                logger.warning("Max cycles (%d) reached", max_cycles)
                break
        return executed

    def pause(self) -> None:
        """Pause continuous execution."""
        if self._state == CPUState.RUNNING:
            self._set_state(CPUState.PAUSED)

    def rewind(self) -> Optional[CycleState]:
        """Rewind one cycle (undo)."""
        if not self._history:
            return None
        state = self._history.pop()
        self._regs.restore(state.register_snapshot)
        self._mic_pc = state.mic_pc
        self._cycle_count -= 1
        return state

    # ------------------------------------------------------------------ #
    # Observer management                                                  #
    # ------------------------------------------------------------------ #

    def add_cycle_observer(self, obs: CycleObserver) -> None:
        self._cycle_observers.append(obs)

    def add_state_observer(
        self, obs: Callable[[CPUState, CPUState], None]
    ) -> None:
        self._state_observers.append(obs)

    # ------------------------------------------------------------------ #
    # Internal execution                                                   #
    # ------------------------------------------------------------------ #

    def _execute_cycle(self) -> CycleState:
        """Execute one full MIC-1 datapath cycle."""
        self._cycle_count += 1
        snap_before = self._regs.snapshot()

        # 1. Fetch microinstruction
        instr = self._rom.read(self._mic_pc)
        current_mic_pc = self._mic_pc

        # 2. Drive B-bus
        b_val = self._read_b_bus(instr.b_bus)

        # 3. Drive A-bus (H register)
        a_val = self._regs.read("H")

        # 4. ALU compute
        alu_result = self._alu.compute(a_val, b_val, instr.alu_op, instr.shift)
        out = alu_result.output
        n   = alu_result.n_flag
        z   = alu_result.z_flag

        # 5. Drive C-bus (write to destination registers)
        changed = self._write_c_bus(instr.c_bus, out)

        # 6. Memory operations
        mem_addr, mem_data = self._do_memory(instr.mem_op)

        # 7. Determine next microinstruction address
        next_addr = self._compute_next_addr(instr, n, z)
        self._mic_pc = next_addr

        state = CycleState(
            cycle_number       = self._cycle_count,
            mic_pc             = current_mic_pc,
            microinstruction   = instr,
            register_snapshot  = snap_before,
            alu_a              = a_val,
            alu_b              = b_val,
            alu_result         = out,
            n_flag             = n,
            z_flag             = z,
            next_mic_pc        = next_addr,
            active_c_bus       = instr.c_bus,
            mem_address        = mem_addr,
            mem_data           = mem_data,
            mem_is_write       = bool(instr.mem_op & MemOp.WRITE),
            changed_registers  = changed,
            description        = instr.disassemble(),
        )

        logger.debug(
            "Cycle %d: MPC=%03X next=%03X ALU=%08X N=%s Z=%s",
            self._cycle_count, current_mic_pc, next_addr, out, n, z,
        )
        return state

    def _read_b_bus(self, b_bus: int) -> int:
        """Read value from B-bus source register."""
        mapping = {
            BBusSource.MDR:  lambda: self._regs.read("MDR"),
            BBusSource.PC:   lambda: self._regs.read("PC"),
            BBusSource.MBR:  lambda: self._mbr_signed(),
            BBusSource.MBRU: lambda: self._regs.read("MBR"),  # unsigned
            BBusSource.SP:   lambda: self._regs.read("SP"),
            BBusSource.LV:   lambda: self._regs.read("LV"),
            BBusSource.CPP:  lambda: self._regs.read("CPP"),
            BBusSource.TOS:  lambda: self._regs.read("TOS"),
            BBusSource.OPC:  lambda: self._regs.read("OPC"),
        }
        return mapping.get(b_bus, lambda: 0)()

    def _mbr_signed(self) -> int:
        """Return MBR as sign-extended 32-bit value."""
        mbr = self._regs.read("MBR")
        if mbr & self.MBR_SIGN_BIT:
            return mbr | 0xFFFF_FF00
        return mbr

    def _write_c_bus(self, c_bus: int, value: int) -> List[str]:
        """Write ALU output to all selected C-bus destinations."""
        changed = []
        c_map = [
            (CBusDest.MAR, "MAR"), (CBusDest.MDR, "MDR"), (CBusDest.PC, "PC"),
            (CBusDest.SP, "SP"),   (CBusDest.LV, "LV"),   (CBusDest.CPP, "CPP"),
            (CBusDest.TOS, "TOS"), (CBusDest.OPC, "OPC"), (CBusDest.H, "H"),
        ]
        for mask, name in c_map:
            if c_bus & mask:
                self._regs.write(name, value)
                changed.append(name)
        return changed

    def _do_memory(self, mem_op: int) -> tuple[Optional[int], Optional[int]]:
        """Perform memory read/write/fetch operations."""
        if mem_op == MemOp.NONE:
            return None, None

        if mem_op & MemOp.READ:
            addr = self._regs.read("MAR")
            data = self._memory.read_word(addr)
            self._regs.write("MDR", data)
            logger.debug("MEM READ addr=0x%08X data=0x%08X", addr, data)
            return addr, data

        if mem_op & MemOp.WRITE:
            addr = self._regs.read("MAR")
            data = self._regs.read("MDR")
            self._memory.write_word(addr, data)
            logger.debug("MEM WRITE addr=0x%08X data=0x%08X", addr, data)
            return addr, data

        if mem_op & MemOp.FETCH:
            addr = self._regs.read("PC")
            byte = self._memory.read_byte(addr)
            self._regs.write("MBR", byte)
            logger.debug("MEM FETCH addr=0x%08X MBR=0x%02X", addr, byte)
            return addr, byte

        return None, None

    def _compute_next_addr(
        self, instr: Microinstruction, n: bool, z: bool
    ) -> int:
        """Compute next micro-PC from JAM bits and flags."""
        addr = instr.next_addr

        if instr.jmpc:
            mbr = self._regs.read("MBR")
            addr = addr | mbr

        if instr.jamn and n:
            addr = addr | 0x100   # set bit 8

        if instr.jamz and z:
            addr = addr | 0x100

        return addr & 0x1FF

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def state(self) -> CPUState:
        return self._state

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def mic_pc(self) -> int:
        return self._mic_pc

    @property
    def registers(self) -> RegisterFile:
        return self._regs

    @property
    def alu(self) -> ALU:
        return self._alu

    def _set_state(self, new_state: CPUState) -> None:
        old = self._state
        self._state = new_state
        if old != new_state:
            for obs in self._state_observers:
                obs(old, new_state)
