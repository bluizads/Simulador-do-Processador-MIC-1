"""
MIC-1 ALU (Unidade Lógica e Aritmética)
=========================================
Implementa a ALU de 32 bits do MIC-1 conforme Tanenbaum Cap. 3-4.

A ALU recebe dois operandos (A=barramento A / H, B=barramento B) e
produz um resultado de 32 bits com os flags N (negativo) e Z (zero).
O Shifter pós-ALU aplica SLL8 ou SRA1 ao resultado.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from enum import IntEnum

logger = logging.getLogger(__name__)


class ALUOperation(IntEnum):
    """
    Operações da ALU do MIC-1.
    Codificação baseada nos bits F0,F1,ENA,ENB,INVA,INC do hardware.
    """
    # Passagem
    PASS_A   = 0x18   # saída = A
    PASS_B   = 0x14   # saída = B
    # Aritméticas
    ADD      = 0x1C   # saída = A + B
    SUB      = 0x1F   # saída = A - B  (complemento de dois: A + NOT(B) + 1)
    INC_A    = 0x19   # saída = A + 1
    INC_B    = 0x15   # saída = B + 1
    DEC_A    = 0x18   # saída = A - 1  (A + NOT(0) = A + 0xFF...FF)
    DEC_B    = 0x10   # saída = B - 1
    NEG_B    = 0x16   # saída = -B
    # Aritmética de pilha (passo de palavra = 4 bytes)
    # Simplificação didática: a memória do MIC-1 é byte-addressable,
    # mas cada valor da pilha ocupa uma palavra de 32 bits (4 bytes).
    # Estas operações avançam/recuam o ponteiro de pilha em 4 bytes
    # para manter os endereços de SP/LV/MAR alinhados a palavras.
    INC4_B   = 0x25   # saída = B + 4
    DEC4_B   = 0x26   # saída = B - 4
    # Lógicas
    AND      = 0x00   # saída = A AND B
    OR       = 0x1E   # saída = A OR  B
    NOT_A    = 0x1A   # saída = NOT A
    XOR      = 0x06   # saída = A XOR B  (não original MIC-1, adicionado)
    # Constantes
    ZERO     = 0x08   # saída = 0
    ONE      = 0x09   # saída = 1  (B=0 + INC)
    NEG_ONE  = 0x0A   # saída = -1


class ShifterOperation(IntEnum):
    """Operações do Shifter pós-ALU."""
    NONE = 0   # sem deslocamento
    SLL8 = 1   # deslocamento lógico à esquerda 8 bits
    SRA1 = 2   # deslocamento aritmético à direita 1 bit (preserva sinal)


@dataclass
class ALUResult:
    """Resultado de uma operação da ALU."""
    output:   int    # resultado de 32 bits (já mascarado)
    n_flag:   bool   # 1 se bit 31 do resultado = 1 (negativo)
    z_flag:   bool   # 1 se resultado == 0


class ALU:
    """
    ALU do MIC-1. (também inclui o shifter)
    
    Entradas: A (registrador H) e B (barramento B)
    Saída: resultado de 32 bits + flags N e Z
    """

    MASK = 0xFFFF_FFFF
    SIGN = 0x8000_0000


    def __init__(self) -> None:
        self._last = ALUResult(0, False, True)

    def compute(self, a: int, b: int, operation: ALUOperation, shift: ShifterOperation = ShifterOperation.NONE) -> ALUResult:
        """
        Executa a operação da ALU seguida do Shifter.

        Args:
            a: operando esquerdo (registrador H), 32 bits
            b: operando direito (barramento B), 32 bits
            operation: operação a executar
            shift: deslocamento a aplicar no resultado

        Returns:
            ALUResult com output e flags N, Z
        """
        a &= self.MASK
        b &= self.MASK

        raw = self._exec(a, b, operation) & self.MASK
        out = self._shift(raw, shift)

        result = ALUResult(
            output = out,
            n_flag = bool(out & self.SIGN),
            z_flag = (out == 0),
        )
        self._last = result

        logger.debug(
            "ALU %s(0x%08X, 0x%08X) = 0x%08X  N=%d Z=%d",
            operation.name, a, b, out, result.n_flag, result.z_flag,
        )
        return result

    def _exec(self, a: int, b: int, op: ALUOperation) -> int:
        match op:
            case ALUOperation.PASS_A:  return a
            case ALUOperation.PASS_B:  return b
            case ALUOperation.ADD:     return a + b
            case ALUOperation.SUB:     return a + ((~b + 1) & self.MASK)
            case ALUOperation.INC_A:   return a + 1
            case ALUOperation.INC_B:   return b + 1
            case ALUOperation.DEC_A:   return a + self.MASK      # a - 1
            case ALUOperation.DEC_B:   return b + self.MASK      # b - 1
            case ALUOperation.NEG_B:   return (~b + 1)
            case ALUOperation.INC4_B:  return b + 4
            case ALUOperation.DEC4_B:  return b + (self.MASK - 3)   # b - 4
            case ALUOperation.AND:     return a & b
            case ALUOperation.OR:      return a | b
            case ALUOperation.NOT_A:   return ~a
            case ALUOperation.XOR:     return a ^ b
            case ALUOperation.ZERO:    return 0
            case ALUOperation.ONE:     return 1
            case ALUOperation.NEG_ONE: return self.MASK
            case _:
                logger.warning("Operação ALU desconhecida: %s, usando PASS_B", op)
                return b

    def _shift(self, value: int, shift: ShifterOperation) -> int:
        match shift:
            case ShifterOperation.NONE: return value & self.MASK
            case ShifterOperation.SLL8: return (value << 8) & self.MASK
            case ShifterOperation.SRA1:
                if value & self.SIGN:
                    return ((value >> 1) | self.SIGN) & self.MASK
                return (value >> 1) & self.MASK
            case _: return value & self.MASK

    @property
    def n_flag(self) -> bool:
        return self._last.n_flag

    @property
    def z_flag(self) -> bool:
        return self._last.z_flag

    @property
    def last_result(self) -> ALUResult:
        return self._last
