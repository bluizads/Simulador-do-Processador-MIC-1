"""
MIC-1 CPU Registers
====================
Implements all MIC-1 registers with observable state changes.
Based on Tanenbaum's MIC-1 specification.
"""

from __future__ import annotations
import logging
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Type alias for observer callbacks
Observer = Callable[[str, int, int], None]  # (register_name, old_value, new_value)


@dataclass
class Register:
    # A single MIC-1 register with observer pattern support.
    name: str
    width: int = 32
    value: int = 0
    description: str = ""
    _observers: List[Observer] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self._mask = (1 << self.width) - 1

    def read(self) -> int:
        """Read the current register value."""
        return self.value

    def write(self, new_value: int) -> None:
        """
        Write a new value to the register.
        Args:
            new_value: Value to write (masked to register width)
        """
        old_value = self.value
        self.value = new_value & self._mask
        if old_value != self.value:
            self._notify_observers(old_value, self.value)

    def reset(self) -> None:
        """Reset register to zero."""
        self.write(0)

    def add_observer(self, observer: Observer) -> None:
        """Register an observer callback."""
        self._observers.append(observer)

    def remove_observer(self, observer: Observer) -> None:
        """Remove an observer callback."""
        self._observers.remove(observer)

    def _notify_observers(self, old_value: int, new_value: int) -> None:
        for obs in self._observers:
            try:
                obs(self.name, old_value, new_value)
            except Exception as e:
                logger.error(f"Observer error for register {self.name}: {e}")

    def to_hex(self) -> str:
        """Return value as hexadecimal string."""
        digits = (self.width + 3) // 4
        return f"0x{self.value:0{digits}X}"

    def to_bin(self) -> str:
        """Return value as binary string."""
        return f"{self.value:0{self.width}b}"

    def to_dec(self) -> str:
        """Return value as signed decimal string."""
        if self.value >= (1 << (self.width - 1)):
            signed = self.value - (1 << self.width)
        else:
            signed = self.value
        return str(signed)


class RegisterFile:
    """
    Complete MIC-1 register file.
    Contains all registers defined in the MIC-1 microarchitecture:
    MAR, MDR, PC, MBR, SP, LV, CPP, TOS, OPC, H
    Also includes internal ALU registers: A, B (latches).
    """

    def __init__(self) -> None:
        self._registers: Dict[str, Register] = {}
        self._global_observers: List[Observer] = []
        self._init_registers()

    def _init_registers(self) -> None:
        """Initialize all MIC-1 registers."""
        specs = [
            ("MAR", 32, "Memory Address Register - holds address for memory access"),
            ("MDR", 32, "Memory Data Register - holds data read from / written to memory"),
            ("PC",  32, "Program Counter - holds address of next instruction"),
            ("MBR", 8,  "Memory Buffer Register - 8-bit buffer for instruction fetch"),
            ("SP",  32, "Stack Pointer - points to top of stack"),
            ("LV",  32, "Local Variable pointer - base of local variable frame"),
            ("CPP", 32, "Constant Pool Pointer - pointer to constant pool"),
            ("TOS", 32, "Top Of Stack - cached top-of-stack value"),
            ("OPC", 32, "OPCode register - holds current opcode"),
            ("H",   32, "H register - left input latch to ALU"),
            # Internal latches
            ("A_LATCH", 32, "A Bus latch - ALU left input"),
            ("B_LATCH", 32, "B Bus latch - ALU right input"),
            ("C_LATCH", 32, "C Bus latch - ALU output"),
        ]
        for name, width, desc in specs:
            reg = Register(name=name, width=width, description=desc)
            reg.add_observer(self._on_register_change)
            self._registers[name] = reg
        logger.debug("RegisterFile initialized with %d registers", len(self._registers))

    def _on_register_change(self, name: str, old: int, new: int) -> None:
        for obs in self._global_observers:
            obs(name, old, new)

    def add_global_observer(self, observer: Observer) -> None:
        """Add observer that fires on ANY register change."""
        self._global_observers.append(observer)

    def __getitem__(self, name: str) -> Register:
        """Access register by name."""
        if name not in self._registers:
            raise KeyError(f"Unknown register: {name}")
        return self._registers[name]

    def read(self, name: str) -> int:
        """Read value of named register."""
        return self._registers[name].read()

    def write(self, name: str, value: int) -> None:
        """Write value to named register."""
        self._registers[name].write(value)

    def reset_all(self) -> None:
        """Reset all registers to zero."""
        for reg in self._registers.values():
            reg.reset()

    def snapshot(self) -> Dict[str, int]:
        """Return a dictionary snapshot of all register values."""
        return {name: reg.read() for name, reg in self._registers.items()}

    def restore(self, snapshot: Dict[str, int]) -> None:
        """Restore register values from a snapshot."""
        for name, value in snapshot.items():
            if name in self._registers:
                self._registers[name].write(value)

    @property
    def names(self) -> List[str]:
        """Return list of all register names."""
        return list(self._registers.keys())

    def get_all(self) -> Dict[str, Register]:
        """Return dictionary of all registers."""
        return dict(self._registers)
