# Recebe resultado da ULA e desloca 1 bit para:
#   esquerda (op = 1)
#   direita (op = 2)
#   não desloca (op = 3)

class Shifter:
    def __init__(self):
        pass

    def shift (self, op, value):
        # garante que tem 16 bits
        value = value & 0xFFFF

        if op == 0:
            # sem deslocamento
            result = value
        elif op == 1:
            # desloca pra esquerda
            result = (value << 1) & 0xFFFF
        elif op == 2:
            # desloca pra direita
            result = (value >> 1) & 0xFFFF
        else:
            raise ValueError(f"Operação de Shifter inválida: {op}")
        
        return (result & 0xFFFF)


# >>>> Teste do shifter
if __name__ == "__main__":
    sh = Shifter()
    
    res = sh.shift(0, 0x00FF)
    print(f"Sem shift (0x00FF) = {hex(res)}")  # Esperado: 0xff
 
    res = sh.shift(1, 0x00FF)
    print(f"Shift Left (0x00FF) = {hex(res)}")  # Esperado: 0x1fe
   
    res = sh.shift(2, 0x00FF)
    print(f"Shift Right (0x00FF) = {hex(res)}")  # Esperado: 0x7f
    
    res = sh.shift(1, 0xFFFF)
    print(f"Shift Left (0xFFFF) = {hex(res)}")  # Esperado: 0xfffe (cortou o carry)