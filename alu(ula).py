# ULA = ALU

class Alu:
    def __init__ (self):
        pass

    def operate (self, op, a, b):
        # garante que tem 16 bits
        a = a & 0xFFFF
        b = b & 0xFFFF

        # 0 = SOMA
        # 1 = AND 
        # 2 = NEGAÇÃO

        if op == 0:
            result = a + b
        elif op == 1:
            result = a & b
        elif op == 2:
            # bit a bit, garante que tem 16 bits
            # unário, ignora b
            result = (~ a) & 0xFFFF
        else:
            raise ValueError(f"Operação de ULA inválida: {op}")
        
        result = result & 0xFFFF

        # vale 1 se o bit 15 (sinal) for 1
        flag_negativo = 1 if (result & 0x8000) else 0

        # vale 1 se resultado é zero
        flag_zero = 1 if (result == 0) else 0

        return result, flag_negativo, flag_zero
    
# Passa resultado para o shifter


    # >>>>>> Teste da ALU
#if __name__ == "__main__":
#    alu = Alu()
#   
#    res, n, z = alu.operate(0,5,3)
#    print(f"5 + 3 = {res} (N={n}, Z={z})")  # Esperado: 8, N=0, Z=0
#    
#   res, n, z = alu.operate(1, 0x00FF, 0x0F0F)
#   print(f"0x00FF & 0x0F0F = {hex(res)} (N={n}, Z={z})")  # Esperado: 0x000F
#   
#   res, n, z = alu.operate(2, 0, 0)  # B é ignorado
#   print(f"~0 = {hex(res)} (N={n}, Z={z})")  # Esperado: 0xFFFF, N=1, Z=0
#   
#   res, n, z = alu.operate(2, 0xFFFF, 0)
#   print(f"~0xFFFF = {hex(res)} (N={n}, Z={z})")  # Esperado: 0x0000, N=0, Z=1