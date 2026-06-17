"""
MIC-1 Cache Simulation
========================
Implements configurable cache with:
- Direct mapped, Set-associative, Fully associative
- LRU, FIFO, Random replacement policies
- Hit/miss statistics with observer callbacks
"""

from __future__ import annotations
import logging
import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import OrderedDict
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

CacheObserver = Callable[["CacheEvent"], None]


class CacheMapping(Enum):
    DIRECT       = auto()
    SET_ASSOC    = auto()
    FULL_ASSOC   = auto()


class ReplacementPolicy(Enum):
    LRU    = auto()
    FIFO   = auto()
    RANDOM = auto()


@dataclass
class CacheEvent:
    """Event fired on every cache access."""
    address:    int
    is_hit:     bool
    set_index:  int
    way:        int           # which way was hit/replaced
    tag:        int
    evicted_tag: Optional[int] = None


@dataclass
class CacheLine:
    """A single cache line."""
    valid:  bool = False
    dirty:  bool = False
    tag:    int  = 0
    data:   List[int] = field(default_factory=list)  # word list
    access_count: int = 0
    insert_order: int = 0  # for FIFO


class CacheSet:
    """A set of cache lines (one set in a set-associative cache)."""

    def __init__(self, ways: int, block_size: int, policy: ReplacementPolicy) -> None:
        self._ways      = ways
        self._block_size = block_size
        self._policy    = policy
        self._lines     = [CacheLine(data=[0] * block_size) for _ in range(ways)]
        self._lru_order: List[int] = list(range(ways))  # LRU: head=LRU, tail=MRU
        self._insert_counter = 0

    def find(self, tag: int) -> Optional[int]:
        """Return way index if tag hits, else None."""
        for i, line in enumerate(self._lines):
            if line.valid and line.tag == tag:
                return i
        return None

    def get_replace_way(self) -> int:
        """Choose a way to replace based on policy."""
        # Prefer invalid lines first
        for i, line in enumerate(self._lines):
            if not line.valid:
                return i
        match self._policy:
            case ReplacementPolicy.LRU:
                return self._lru_order[0]
            case ReplacementPolicy.FIFO:
                oldest = min(self._lines, key=lambda l: l.insert_order)
                return self._lines.index(oldest)
            case ReplacementPolicy.RANDOM:
                return random.randrange(self._ways)

    def access(self, way: int) -> None:
        """Update LRU order on access."""
        if self._policy == ReplacementPolicy.LRU:
            self._lru_order.remove(way)
            self._lru_order.append(way)

    def insert(self, way: int, tag: int, data: List[int]) -> Optional[int]:
        """Insert a block into the given way, return evicted tag if any."""
        evicted = self._lines[way].tag if self._lines[way].valid else None
        self._lines[way].valid        = True
        self._lines[way].tag          = tag
        self._lines[way].data         = list(data)
        self._lines[way].insert_order = self._insert_counter
        self._insert_counter += 1
        self.access(way)
        return evicted

    def read(self, way: int, word_offset: int) -> int:
        return self._lines[way].data[word_offset]

    def write(self, way: int, word_offset: int, value: int) -> None:
        self._lines[way].data[word_offset] = value
        self._lines[way].dirty = True

    def invalidate(self, way: int) -> None:
        self._lines[way].valid = False

    @property
    def lines(self) -> List[CacheLine]:
        return self._lines


class Cache:
    """
    Configurable cache memory.
    
    Supports:
    - Direct mapped (ways=1)
    - Set associative (ways=2,4,8,16)
    - Fully associative (sets=1)
    
    Args:
        size_bytes:   Total cache size in bytes
        block_size:   Block/line size in words (4 bytes each)
        ways:         Number of ways (associativity)
        mapping:      Cache mapping type
        policy:       Replacement policy
        name:         Cache name for logging
    """

    def __init__(
        self,
        size_bytes: int           = 4096,
        block_size: int           = 4,
        ways: int                 = 1,
        mapping: CacheMapping     = CacheMapping.DIRECT,
        policy: ReplacementPolicy = ReplacementPolicy.LRU,
        name: str                 = "Cache",
    ) -> None:
        self._name       = name
        self._block_size = block_size  # in words
        self._ways       = ways
        self._mapping    = mapping
        self._policy     = policy

        total_words = size_bytes // 4
        total_blocks = total_words // block_size

        if mapping == CacheMapping.FULL_ASSOC:
            self._num_sets = 1
            self._ways     = total_blocks
        elif mapping == CacheMapping.DIRECT:
            self._num_sets = total_blocks
            self._ways     = 1
        else:
            self._num_sets = max(1, total_blocks // ways)
            self._ways     = ways

        self._sets = [
            CacheSet(self._ways, block_size, policy)
            for _ in range(self._num_sets)
        ]

        # Bit field sizes
        self._block_bits  = int(math.log2(block_size)) if block_size > 1 else 0
        self._set_bits    = int(math.log2(self._num_sets)) if self._num_sets > 1 else 0

        # Statistics
        self._hits         = 0
        self._misses       = 0
        self._total_access = 0

        self._observers: List[CacheObserver] = []
        logger.info(
            "%s: %d sets × %d ways × %d words/block, policy=%s",
            name, self._num_sets, self._ways, block_size, policy.name,
        )

    def access(self, address: int, write: bool = False, data: int = 0) -> Tuple[bool, int]:
        """
        Perform a cache access.
        
        Args:
            address:  Word address to access
            write:    True for write, False for read
            data:     Data to write (only for write accesses)
            
        Returns:
            (hit: bool, data: int)  — data is 0 on misses (caller fetches from mem)
        """
        self._total_access += 1
        tag, set_idx, word_offset = self._decode_address(address)

        cache_set = self._sets[set_idx]
        way = cache_set.find(tag)

        if way is not None:
            # HIT
            self._hits += 1
            cache_set.access(way)
            if write:
                cache_set.write(way, word_offset, data)
                result = data
            else:
                result = cache_set.read(way, word_offset)
            self._fire(CacheEvent(address, True, set_idx, way, tag))
            return True, result
        else:
            # MISS
            self._misses += 1
            replace_way = cache_set.get_replace_way()
            evicted_tag = cache_set.insert(
                replace_way, tag,
                [0] * self._block_size,  # caller fills from memory
            )
            if write:
                cache_set.write(replace_way, word_offset, data)
            self._fire(CacheEvent(address, False, set_idx, replace_way, tag, evicted_tag))
            return False, 0

    def _decode_address(self, address: int) -> Tuple[int, int, int]:
        """Decode word address into (tag, set_index, word_offset)."""
        word_offset = address & ((1 << self._block_bits) - 1)
        set_idx     = (address >> self._block_bits) & ((1 << self._set_bits) - 1)
        tag         = address >> (self._block_bits + self._set_bits)
        return tag, set_idx, word_offset

    def _fire(self, event: CacheEvent) -> None:
        for obs in self._observers:
            try:
                obs(event)
            except Exception as e:
                logger.error("Cache observer error: %s", e)

    def add_observer(self, obs: CacheObserver) -> None:
        self._observers.append(obs)

    def reset_stats(self) -> None:
        self._hits = self._misses = self._total_access = 0

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def total_access(self) -> int:
        return self._total_access

    @property
    def hit_rate(self) -> float:
        if self._total_access == 0:
            return 0.0
        return self._hits / self._total_access

    @property
    def miss_rate(self) -> float:
        return 1.0 - self.hit_rate

    @property
    def sets(self) -> List[CacheSet]:
        return self._sets

    @property
    def num_sets(self) -> int:
        return self._num_sets

    @property
    def num_ways(self) -> int:
        return self._ways

    @property
    def name(self) -> str:
        return self._name

    def get_stats_summary(self) -> str:
        return (
            f"{self._name}: "
            f"hits={self._hits} misses={self._misses} "
            f"total={self._total_access} "
            f"hit_rate={self.hit_rate:.1%}"
        )
