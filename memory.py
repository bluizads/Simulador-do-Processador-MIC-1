# Memória Principal
# 4.096 posições de 16 bits
class Memory:
    def __init__(self):
        self.mainMemory = [0] * 4096

    def read (self, address):
        if 0 <= address < len(self.mainMemory):
            return self.mainMemory[address]
        else:
            raise ValueError(f"Endereço inválido: {address}")

    def write(self, address, value):
        if 0 <= address < len(self.mainMemory):
            # garante que tem 16 bits
            self.mainMemory[address] = value & 0xFFFF
        else:
            raise ValueError(f"Endereço inválido: {address}")
