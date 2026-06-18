from dataclasses import dataclass


@dataclass
class CacheLine:
    valid: bool = False
    tag: int = 0
    data: int = 0


class DirectMappedCache:
    def __init__(self, size=16):
        self.size = size
        self.lines = [CacheLine() for _ in range(size)]

        self.hits = 0
        self.misses = 0
        self.last_access = ""
        self.last_result = ""

    def access(self, address, read_callback):
        index = address % self.size
        tag = address // self.size

        line = self.lines[index]

        if line.valid and line.tag == tag:
            self.hits += 1
            self.last_access = hex(address)
            self.last_result = "HIT"
            return line.data

        self.misses += 1

        value = read_callback(address)

        line.valid = True
        line.tag = tag
        line.data = value

        self.last_access = hex(address)
        self.last_result = "MISS"

        return value

    @property
    def hit_rate(self):
        total = self.hits + self.misses
        return 0 if total == 0 else (100 * self.hits / total)