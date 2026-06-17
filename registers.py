# Registradores:
#    R0 (PC): Program Counter
#    R1 (AC): Accumulator
#    R2 (SP): Stack Pointer ou ponteiro de pilha
#    R3 (IR): Instruction Register
#    R4 (TIR): Temporary Instruction Register

#    R5: constante 0 (sempre 0)
#    R6: constante +1 (sempre +1)
#    R7: constante -1 (sempre 0xFFFF)
#    R8: AND_mask (máscara para AND, valor 0x0FF)
#    R9: SHIFT_mask (máscara para shift, valor 0x0FF)

#    R10 a R15: Registradores de propósito geral


class Registers:
    def __init__(self):
        self.registers = [0] * 16
        # registradores de 0 a 15

    def read (self, index):
        if 0 <= index <= 15:
            return self.registers[index]
        else:
            raise ValueError(f"Registrador inválido: {index}")
        
    def write (self, index, value):
        if 0 <= index <= 15:
            # garante que tem 16 bits
            self.registers[index] = value & 0xFFFF
        else:
            raise ValueError(f"Registrador inválido: {index}")

