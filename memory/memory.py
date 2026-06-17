"""
MIC-1 Main Memory
==================
Byte-addressable main memory with read/write access and observer pattern.
Supports configurable size and access width.
"""

from __future__ import annotations
import logging
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

MemoryObserver = Callable[[int, int, int, bool], None]  # (address, old, new, is_write)


class Memory:
    """
    MIC-1 Main Memory.
    Byte-addressable memory with configurable size.
    Supports 8-bit, 16-bit and 32-bit access.
    Attributes:
        size: Memory size in bytes
    """

    DEFAULT_SIZE = 64 * 1024  # 64 KB

    def __init__(self, size: int = DEFAULT_SIZE) -> None:
        """
        Initialize memory.
        Args:
            size: Memory size in bytes (default 64 KB)
        """
        if size <= 0:
            raise ValueError(f"Memory size must be positive, got {size}")
        self._size = size
        self._data = bytearray(size)
        self._observers: List[MemoryObserver] = []
        self._access_count = 0
        self._read_count  = 0
        self._write_count = 0
        logger.info("Memory initialized: %d bytes (%.1f KB)", size, size / 1024)

    # ------------------------------------------------------------------ #
    # Public read/write API                                                #
    # ------------------------------------------------------------------ #

    def read_byte(self, address: int) -> int:
        """Read a single byte from memory."""
        self._validate_address(address, 1)
        value = self._data[address]
        self._read_count += 1
        self._access_count += 1
        return value

    def write_byte(self, address: int, value: int) -> None:
        """Write a single byte to memory."""
        self._validate_address(address, 1)
        old = self._data[address]
        self._data[address] = value & 0xFF
        self._write_count += 1
        self._access_count += 1
        self._notify(address, old, self._data[address], True)

    def read_word(self, address: int) -> int:
        """Read a 32-bit word (big-endian) from memory."""
        self._validate_address(address, 4)
        b = self._data[address:address + 4]
        return (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]

    def write_word(self, address: int, value: int) -> None:
        """Write a 32-bit word (big-endian) to memory."""
        self._validate_address(address, 4)
        old = self.read_word(address)
        v = value & 0xFFFF_FFFF
        self._data[address]     = (v >> 24) & 0xFF
        self._data[address + 1] = (v >> 16) & 0xFF
        self._data[address + 2] = (v >>  8) & 0xFF
        self._data[address + 3] =  v        & 0xFF
        self._write_count += 1
        self._access_count += 1
        self._notify(address, old, v, True)

    def read_halfword(self, address: int) -> int:
        """Read a 16-bit half-word (big-endian) from memory."""
        self._validate_address(address, 2)
        return (self._data[address] << 8) | self._data[address + 1]

    def load_program(self, data: bytes, base_address: int = 0) -> None:
        """
        Load program bytes into memory at base_address.
        
        Args:
            data: Program bytes to load
            base_address: Starting address (default 0)
        """
        end = base_address + len(data)
        if end > self._size:
            raise MemoryError(
                f"Program ({len(data)} bytes) exceeds memory at address {base_address}"
            )
        self._data[base_address:end] = data
        logger.info("Loaded %d bytes at address 0x%04X", len(data), base_address)

    def dump(self, start: int = 0, length: int = 256) -> str:
        """
        Generate a hex dump of memory.
        
        Args:
            start: Start address
            length: Number of bytes to dump
            
        Returns:
            Formatted hex dump string
        """
        lines = []
        for offset in range(0, length, 16):
            addr = start + offset
            if addr >= self._size:
                break
            chunk = self._data[addr:addr + 16]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            ascii_part = "".join(
                chr(b) if 0x20 <= b < 0x7F else "." for b in chunk
            )
            lines.append(f"{addr:08X}  {hex_part:<47}  |{ascii_part}|")
        return "\n".join(lines)

    def reset(self) -> None:
        """Clear all memory to zero."""
        self._data = bytearray(self._size)
        self._access_count = 0
        self._read_count   = 0
        self._write_count  = 0
        logger.info("Memory reset to zero")

    def snapshot(self) -> bytes:
        """Return a copy of the current memory state."""
        return bytes(self._data)

    def restore(self, snapshot: bytes) -> None:
        """Restore memory from a snapshot."""
        if len(snapshot) != self._size:
            raise ValueError("Snapshot size mismatch")
        self._data[:] = snapshot

    # ------------------------------------------------------------------ #
    # Observer support                                                     #
    # ------------------------------------------------------------------ #

    def add_observer(self, observer: MemoryObserver) -> None:
        """Add a memory access observer."""
        self._observers.append(observer)

    def _notify(self, addr: int, old: int, new: int, is_write: bool) -> None:
        for obs in self._observers:
            try:
                obs(addr, old, new, is_write)
            except Exception as e:
                logger.error("Memory observer error: %s", e)

    # ------------------------------------------------------------------ #
    # Properties & helpers                                                 #
    # ------------------------------------------------------------------ #

    @property
    def size(self) -> int:
        return self._size

    @property
    def access_count(self) -> int:
        return self._access_count

    @property
    def read_count(self) -> int:
        return self._read_count

    @property
    def write_count(self) -> int:
        return self._write_count

    def _validate_address(self, address: int, width: int) -> None:
        if address < 0 or address + width > self._size:
            raise MemoryError(
                f"Memory access out of bounds: address=0x{address:08X} "
                f"width={width} size=0x{self._size:08X}"
            )

    def __len__(self) -> int:
        return self._size

    def __getitem__(self, address: int) -> int:
        return self.read_byte(address)

    def __setitem__(self, address: int, value: int) -> None:
        self.write_byte(address, value)
