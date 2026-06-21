from cpu.cpu import CPU, CPUState, CycleState
from memory.memory import Memory
from microcode.microinstruction import MicrocodeROM, MemOp
from cache.cache import Cache, CacheMapping, ReplacementPolicy


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

