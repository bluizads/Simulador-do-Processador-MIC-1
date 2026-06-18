"""
MIC-1 Microinstrução & ROM de Microcódigo
============================================
Microinstrução de 36 bits conforme Tanenbaum, Cap 4.

Layout dos campos:
  [35:27] NEXT_ADDR  9 bits  - endereço da próxima microinstrução
  [26]    JMPC       1 bit   - OR MBR no próximo endereço
  [25]    JAMN       1 bit   - OR bit8 se N=1
  [24]    JAMZ       1 bit   - OR bit8 se Z=1
  [23:18] ALU        6 bits  - operação da ALU
  [17:16] SH         2 bits  - shifter (00=nenhum, 01=SLL8, 10=SRA1)
  [15:7]  C          9 bits  - destinos do barramento C (bitmask)
  [6:3]   B          4 bits  - fonte do barramento B
  [2]     MEM_RD     1 bit   - leitura de memória (MAR -> MDR)
  [1]     MEM_WR     1 bit   - escrita de memória (MDR -> mem[MAR])
  [0]     FETCH      1 bit   - busca de instrução (mem[PC] -> MBR)

NOTA SOBRE ENDEREÇAMENTO DA PILHA
-----------------------------------
A memória do MIC-1 é byte-addressable. Cada valor da pilha (TOS, variáveis
locais, etc.) ocupa uma palavra de 32 bits = 4 bytes. Para manter o modelo
simples e didático, SP e LV avançam/recuam em passos de 4 bytes usando as
operações ALUOperation.INC4_B / DEC4_B. SP sempre aponta para o endereço
do elemento atual do topo da pilha (TOS).
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Dict
from cpu.alu import ALUOperation, ShifterOperation

logger = logging.getLogger(__name__)


class BBusSource:
    """Fonte do Barramento B (4 bits)."""
    MDR  = 0
    PC   = 1
    MBR  = 2    # com extensão de sinal
    MBRU = 3    # sem sinal
    SP   = 4
    LV   = 5
    CPP  = 6
    TOS  = 7
    OPC  = 8
    NONE = 15


class CBusDest:
    """Destinos do Barramento C (bitmask de 9 bits)."""
    MAR = 0x001
    MDR = 0x002
    PC  = 0x004
    SP  = 0x008
    LV  = 0x010
    CPP = 0x020
    TOS = 0x040
    OPC = 0x080
    H   = 0x100


class MemOp:
    """Sinais de controle de memória."""
    NONE  = 0
    READ  = 1   # MDR <- mem[MAR]
    WRITE = 2   # mem[MAR] <- MDR
    FETCH = 4   # MBR <- mem[PC]


@dataclass
class Microinstruction:
    """Uma microinstrução MIC-1 de 36 bits."""
    next_addr: int              = 0
    jamn:      bool             = False
    jamz:      bool             = False
    jmpc:      bool             = False
    alu_op:    ALUOperation     = ALUOperation.PASS_B
    shift:     ShifterOperation = ShifterOperation.NONE
    c_bus:     int              = 0
    b_bus:     int              = BBusSource.NONE
    mem_op:    int              = MemOp.NONE
    label:     str              = ""

    def encode(self) -> int:
        w  = (self.next_addr & 0x1FF) << 27
        w |= (int(self.jmpc) << 26)
        w |= (int(self.jamn) << 25)
        w |= (int(self.jamz) << 24)
        w |= ((int(self.alu_op)  & 0x3F) << 18)
        w |= ((int(self.shift)   & 0x03) << 16)
        w |= ((self.c_bus  & 0x1FF) << 7)
        w |= ((self.b_bus  & 0x0F) << 3)
        w |= (self.mem_op & 0x07)
        return w

    @classmethod
    def decode(cls, word: int, label: str = "") -> "Microinstruction":
        try:
            alu = ALUOperation((word >> 18) & 0x3F)
        except ValueError:
            alu = ALUOperation.PASS_B
        try:
            sh = ShifterOperation((word >> 16) & 0x03)
        except ValueError:
            sh = ShifterOperation.NONE
        return cls(
            next_addr = (word >> 27) & 0x1FF,
            jmpc      = bool((word >> 26) & 1),
            jamn      = bool((word >> 25) & 1),
            jamz      = bool((word >> 24) & 1),
            alu_op    = alu,
            shift     = sh,
            c_bus     = (word >> 7) & 0x1FF,
            b_bus     = (word >> 3) & 0x0F,
            mem_op    = word & 0x07,
            label     = label,
        )

    def disassemble(self) -> str:
        B_NAMES = {
            BBusSource.MDR:"MDR", BBusSource.PC:"PC",
            BBusSource.MBR:"MBR", BBusSource.MBRU:"MBRU",
            BBusSource.SP:"SP",   BBusSource.LV:"LV",
            BBusSource.CPP:"CPP", BBusSource.TOS:"TOS",
            BBusSource.OPC:"OPC", BBusSource.NONE:"-",
        }
        C_MAP = [
            (CBusDest.MAR,"MAR"), (CBusDest.MDR,"MDR"), (CBusDest.PC,"PC"),
            (CBusDest.SP,"SP"),   (CBusDest.LV,"LV"),   (CBusDest.CPP,"CPP"),
            (CBusDest.TOS,"TOS"), (CBusDest.OPC,"OPC"), (CBusDest.H,"H"),
        ]
        b = B_NAMES.get(self.b_bus, "?")
        c_dests = [n for m, n in C_MAP if self.c_bus & m]
        parts = []
        if self.label:
            parts.append(f"{self.label}:")
        if c_dests:
            dst = ",".join(c_dests)
            parts.append(f"{dst} <- {self.alu_op.name}(H,{b})")
        else:
            parts.append(f"{self.alu_op.name}(H,{b})")
        if self.shift != ShifterOperation.NONE:
            parts.append(f"SH={self.shift.name}")
        if self.mem_op & MemOp.READ:   parts.append("RD")
        if self.mem_op & MemOp.WRITE:  parts.append("WR")
        if self.mem_op & MemOp.FETCH:  parts.append("FETCH")
        if self.jmpc:  parts.append("JMPC")
        if self.jamn:  parts.append("JAMN")
        if self.jamz:  parts.append("JAMZ")
        parts.append(f"-> {self.next_addr:03X}")
        return "  ".join(parts)


class MicrocodeROM:
    """
    ROM de Microcódigo MIC-1 (512 x 36 bits).

    Implementa o ciclo principal (fetch/decode/dispatch) e as seguintes
    instruções IJVM: NOP, BIPUSH, ILOAD, ISTORE, IADD, ISUB, IAND, IOR,
    DUP, POP, SWAP, GOTO, IFEQ, IFLT, HALT.
    """
    CAPACITY = 512

    def __init__(self) -> None:
        self._rom: Dict[int, Microinstruction] = {}
        self._load_ijvm_microprogram()
        logger.info("MicrocodeROM: %d microinstrucoes carregadas", len(self._rom))

    def _mi(self, label, next_addr, alu_op=ALUOperation.PASS_B,
            b_bus=BBusSource.NONE, c_bus=0, mem_op=MemOp.NONE,
            shift=ShifterOperation.NONE, jamn=False, jamz=False, jmpc=False):
        return Microinstruction(
            label=label, next_addr=next_addr, alu_op=alu_op,
            b_bus=b_bus, c_bus=c_bus, mem_op=mem_op,
            shift=shift, jamn=jamn, jamz=jamz, jmpc=jmpc,
        )

    def _load_ijvm_microprogram(self) -> None:
        mi = self._mi

        # ════════════════════════════════════════════════════════════════
        # CICLO PRINCIPAL — busca, decodifica e despacha
        # ════════════════════════════════════════════════════════════════

        # Main1: MAR = PC; fetch (MBR <- mem[PC])
        self._rom[0x00] = mi("Main1", 0x01,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.MAR, mem_op=MemOp.FETCH)

        # Main2: PC = PC + 1
        self._rom[0x01] = mi("Main2", 0x02,
            alu_op=ALUOperation.INC_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.PC)

        # Main3: despacho — next_addr = 0x000 | MBR (via JMPC)
        self._rom[0x02] = mi("Main3", 0x00,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.MBR,
            jmpc=True)

        # ════════════════════════════════════════════════════════════════
        # BIPUSH byte  (opcode 0x10)
        # Empilha um byte com extensão de sinal.
        # SP avança 4 bytes (palavra). Após escrever, SP aponta para o
        # novo elemento do topo.
        # ════════════════════════════════════════════════════════════════
        self._rom[0x10] = mi("bipush1", 0x11,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.MAR, mem_op=MemOp.FETCH)     # busca operando
        self._rom[0x11] = mi("bipush2", 0x12,
            alu_op=ALUOperation.INC_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.PC)                          # PC++
        self._rom[0x12] = mi("bipush3", 0x13,
            alu_op=ALUOperation.DEC4_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.MAR | CBusDest.SP)           # SP -= 4; MAR = novo SP
        self._rom[0x13] = mi("bipush4", 0x00,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.MBR,
            c_bus=CBusDest.MDR | CBusDest.TOS, mem_op=MemOp.WRITE)  # mem[SP]=MBR; TOS=MBR

        # ════════════════════════════════════════════════════════════════
        # ILOAD varnum  (opcode 0x15)
        # Empilha LV[varnum] (variável local na posição LV + 4*varnum).
        # ════════════════════════════════════════════════════════════════
        self._rom[0x15] = mi("iload1", 0x16,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.MAR, mem_op=MemOp.FETCH)     # busca varnum
        self._rom[0x16] = mi("iload2", 0x17,
            alu_op=ALUOperation.INC_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.PC)                          # PC++
        self._rom[0x17] = mi("iload3", 0x18,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.LV,
            c_bus=CBusDest.H)                           # H = LV
        # endereco = LV + 4*varnum  ->  aproveita SLL8? Não: varnum cabe em 1 byte,
        # multiplicar por 4 = somar varnum quatro vezes seria custoso; para
        # simplicidade didática tratamos varnum já como offset em palavras
        # somando-o ADD com deslocamento aplicado externamente. Aqui somamos
        # MBRU diretamente (offset em "slots"): endereco = LV + varnum*1
        # (cada slot = 1 palavra = 4 bytes, mas para simplificar o offset
        # é tratado como múltiplo de 4 já correto se varnum representar
        # o índice do slot multiplicado por 4 no momento da montagem).
        self._rom[0x18] = mi("iload4", 0x19,
            alu_op=ALUOperation.ADD, b_bus=BBusSource.MBRU,
            c_bus=CBusDest.MAR, mem_op=MemOp.READ)      # MAR = LV + varnum*4; rd
        self._rom[0x19] = mi("iload5", 0x1A,
            alu_op=ALUOperation.DEC4_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.MAR | CBusDest.SP)           # SP -= 4; MAR = novo SP
        self._rom[0x1A] = mi("iload6", 0x00,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.MDR,
            c_bus=CBusDest.MDR | CBusDest.TOS, mem_op=MemOp.WRITE)  # mem[SP]=valor; TOS=valor

        # ════════════════════════════════════════════════════════════════
        # ISTORE varnum  (opcode 0x36)
        # Desempilha para LV[varnum].
        # ════════════════════════════════════════════════════════════════
        self._rom[0x36] = mi("istore1", 0x37,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.MAR, mem_op=MemOp.FETCH)     # busca varnum
        self._rom[0x37] = mi("istore2", 0x38,
            alu_op=ALUOperation.INC_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.PC)                          # PC++
        self._rom[0x38] = mi("istore3", 0x39,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.LV,
            c_bus=CBusDest.H)                           # H = LV
        self._rom[0x39] = mi("istore4", 0x3A,
            alu_op=ALUOperation.ADD, b_bus=BBusSource.MBRU,
            c_bus=CBusDest.H)                           # H = LV + varnum*4 (endereço destino)
        self._rom[0x3A] = mi("istore5", 0x3B,
            alu_op=ALUOperation.PASS_A, b_bus=BBusSource.NONE,
            c_bus=CBusDest.MAR)                         # MAR = H (endereço destino)
        self._rom[0x3B] = mi("istore6", 0x3C,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.TOS,
            c_bus=CBusDest.MDR, mem_op=MemOp.WRITE)     # mem[destino] = TOS
        self._rom[0x3C] = mi("istore7", 0x3D,
            alu_op=ALUOperation.INC4_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.MAR | CBusDest.SP, mem_op=MemOp.READ)  # SP+=4; MAR=novo SP; rd (novo TOS)
        self._rom[0x3D] = mi("istore8", 0x00,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.MDR,
            c_bus=CBusDest.TOS)                         # TOS = novo valor do topo

        # ════════════════════════════════════════════════════════════════
        # IADD (opcode 0x60):  TOS = pop() + pop()
        # SP aponta para o TOS atual. O 2º operando está em SP+4 (palavra
        # abaixo na pilha, em endereço mais alto). Avançamos SP em 4 e
        # lemos esse valor no mesmo ciclo.
        # ════════════════════════════════════════════════════════════════
        self._rom[0x60] = mi("iadd1", 0x61,
            alu_op=ALUOperation.INC4_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.MAR | CBusDest.SP, mem_op=MemOp.READ)  # SP+=4; MAR=novoSP; rd
        self._rom[0x61] = mi("iadd2", 0x62,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.MDR,
            c_bus=CBusDest.H)                           # H = 2º operando
        self._rom[0x62] = mi("iadd3", 0x63,
            alu_op=ALUOperation.ADD, b_bus=BBusSource.TOS,
            c_bus=CBusDest.TOS | CBusDest.MDR)          # TOS = H + TOS (resultado)
        self._rom[0x63] = mi("iadd4", 0x00,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.MAR, mem_op=MemOp.WRITE)     # mem[SP] = resultado

        # ════════════════════════════════════════════════════════════════
        # ISUB (opcode 0x64):  TOS = pop() - pop()
        # resultado = (2º operando) - (TOS atual) = H - TOS
        # ════════════════════════════════════════════════════════════════
        self._rom[0x64] = mi("isub1", 0x65,
            alu_op=ALUOperation.INC4_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.MAR | CBusDest.SP, mem_op=MemOp.READ)
        self._rom[0x65] = mi("isub2", 0x66,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.MDR,
            c_bus=CBusDest.H)
        self._rom[0x66] = mi("isub3", 0x67,
            alu_op=ALUOperation.SUB, b_bus=BBusSource.TOS,
            c_bus=CBusDest.TOS | CBusDest.MDR)          # TOS = H - TOS
        self._rom[0x67] = mi("isub4", 0x00,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.MAR, mem_op=MemOp.WRITE)

        # ════════════════════════════════════════════════════════════════
        # IAND (opcode 0x7E):  TOS = pop() & pop()
        # O bloco padrão de 4 slots (0x7E-0x81) colidiria com IOR (0x80).
        # Usamos apenas 0x7E-0x7F como "decodificação" e desviamos (via
        # next_addr fixo, sem JMPC) para a zona alta 0x17E onde o resto
        # da operação é executado sem risco de colisão.
        # ════════════════════════════════════════════════════════════════
        self._rom[0x7E] = mi("iand1", 0x7F,
            alu_op=ALUOperation.INC4_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.MAR | CBusDest.SP, mem_op=MemOp.READ)
        self._rom[0x7F] = mi("iand2", 0x17E,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.MDR,
            c_bus=CBusDest.H)                            # -> salta para zona alta
        self._rom[0x17E] = mi("iand3", 0x17F,
            alu_op=ALUOperation.AND, b_bus=BBusSource.TOS,
            c_bus=CBusDest.TOS | CBusDest.MDR)
        self._rom[0x17F] = mi("iand4", 0x00,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.MAR, mem_op=MemOp.WRITE)

        # ════════════════════════════════════════════════════════════════
        # IOR (opcode 0x80):  TOS = pop() | pop()
        # ════════════════════════════════════════════════════════════════
        self._rom[0x80] = mi("ior1", 0x81,
            alu_op=ALUOperation.INC4_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.MAR | CBusDest.SP, mem_op=MemOp.READ)
        self._rom[0x81] = mi("ior2", 0x82,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.MDR,
            c_bus=CBusDest.H)
        self._rom[0x82] = mi("ior3", 0x83,
            alu_op=ALUOperation.OR, b_bus=BBusSource.TOS,
            c_bus=CBusDest.TOS | CBusDest.MDR)
        self._rom[0x83] = mi("ior4", 0x00,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.MAR, mem_op=MemOp.WRITE)

        # ════════════════════════════════════════════════════════════════
        # DUP (opcode 0x59):  duplica o topo da pilha
        # ════════════════════════════════════════════════════════════════
        self._rom[0x59] = mi("dup1", 0x5A,
            alu_op=ALUOperation.DEC4_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.MAR | CBusDest.SP)           # SP -= 4; MAR = novo SP
        self._rom[0x5A] = mi("dup2", 0x00,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.TOS,
            c_bus=CBusDest.MDR, mem_op=MemOp.WRITE)     # mem[SP] = TOS (cópia)

        # ════════════════════════════════════════════════════════════════
        # POP (opcode 0x57):  descarta o topo, restaura o anterior
        # ════════════════════════════════════════════════════════════════
        self._rom[0x57] = mi("pop1", 0x58,
            alu_op=ALUOperation.INC4_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.SP | CBusDest.MAR, mem_op=MemOp.READ)  # SP+=4; rd novo topo
        self._rom[0x58] = mi("pop2", 0x00,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.MDR,
            c_bus=CBusDest.TOS)                          # TOS = novo topo

        # ════════════════════════════════════════════════════════════════
        # SWAP (opcode 0x5F):  troca os dois elementos do topo
        # ════════════════════════════════════════════════════════════════
        self._rom[0x5F] = mi("swap1", 0xC0,
            alu_op=ALUOperation.INC4_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.MAR, mem_op=MemOp.READ)       # lê o 2º elemento (SP+4), sem mover SP
        self._rom[0xC0] = mi("swap2", 0xC1,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.MDR,
            c_bus=CBusDest.OPC)                          # OPC = 2º elemento
        self._rom[0xC1] = mi("swap3", 0xC2,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.TOS,
            c_bus=CBusDest.MDR, mem_op=MemOp.WRITE)      # mem[SP+4] = TOS (MAR já é SP+4)
        self._rom[0xC2] = mi("swap4", 0xC3,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.MAR)                          # MAR = SP (1º elemento)
        self._rom[0xC3] = mi("swap5", 0x00,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.OPC,
            c_bus=CBusDest.MDR | CBusDest.TOS, mem_op=MemOp.WRITE)  # mem[SP]=OPC; TOS=OPC

        # ════════════════════════════════════════════════════════════════
        # GOTO offset  (opcode 0xA7):  salto incondicional (offset 16-bit
        # com sinal, big-endian, relativo ao endereço do opcode)
        # ════════════════════════════════════════════════════════════════
        self._rom[0xA7] = mi("goto1", 0xA8,
            alu_op=ALUOperation.DEC_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.OPC)                          # OPC = PC-1 = endereço do opcode
        self._rom[0xA8] = mi("goto2", 0xA9,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.MAR, mem_op=MemOp.FETCH)      # busca byte alto do offset
        self._rom[0xA9] = mi("goto3", 0xAA,
            alu_op=ALUOperation.INC_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.PC)                           # PC++
        self._rom[0xAA] = mi("goto4", 0xAB,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.MBR,
            c_bus=CBusDest.H, shift=ShifterOperation.SLL8)  # H = byte_alto << 8
        self._rom[0xAB] = mi("goto5", 0xAC,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.MAR, mem_op=MemOp.FETCH)      # busca byte baixo do offset
        self._rom[0xAC] = mi("goto6", 0xAD,
            alu_op=ALUOperation.INC_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.PC)                           # PC++
        self._rom[0xAD] = mi("goto7", 0xAE,
            alu_op=ALUOperation.OR, b_bus=BBusSource.MBRU,
            c_bus=CBusDest.H)                            # H = offset completo (16 bits)
        self._rom[0xAE] = mi("goto8", 0x00,
            alu_op=ALUOperation.ADD, b_bus=BBusSource.OPC,
            c_bus=CBusDest.PC)                           # PC = endereço_opcode + offset

        # ════════════════════════════════════════════════════════════════
        # IFEQ offset  (opcode 0x99):  salta se pop() == 0
        # Bloco de dispatch 0x99-0x9C (4 slots); IFLT=0x9B exige que
        # 0x9B fique livre, então IFEQ usa apenas 0x99-0x9A e desvia
        # (next_addr fixo) para a zona alta 0x199 a partir do 3º passo.
        # ════════════════════════════════════════════════════════════════
        self._rom[0x99] = mi("ifeq1", 0x9A,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.TOS,
            c_bus=CBusDest.H)                            # H = valor a testar
        self._rom[0x9A] = mi("ifeq2", 0x199,
            alu_op=ALUOperation.INC4_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.SP | CBusDest.MAR, mem_op=MemOp.READ)  # SP+=4; rd novo topo; -> zona alta
        self._rom[0x199] = mi("ifeq3", 0x09A,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.MDR,
            c_bus=CBusDest.TOS)                          # TOS = novo topo; -> 0x09A (sem bit 0x100)
        # Testa H: PASS_A(H) -> Z=1 se H==0. JAMZ desvia para +0x100 se Z.
        self._rom[0x09A] = mi("ifeq4", 0x09B,
            alu_op=ALUOperation.PASS_A,
            jamz=True)                                   # se Z: -> 0x19B ; senão -> 0x09B
        # CASO NÃO SALTA (Z=0): consome o offset de 2 bytes e volta ao main
        self._rom[0x09B] = mi("ifeq_no1", 0x09C,
            alu_op=ALUOperation.INC_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.PC)                           # PC++ (pula byte alto do offset)
        self._rom[0x09C] = mi("ifeq_no2", 0x00,
            alu_op=ALUOperation.INC_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.PC)                           # PC++ (pula byte baixo do offset)
        # CASO SALTA (Z=1, endereco = 0x09B | 0x100 = 0x19B): executa GOTO
        self._rom[0x19B] = mi("ifeq_yes", 0xA8,
            alu_op=ALUOperation.DEC_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.OPC)                          # OPC = PC-1 = endereço do opcode (reusa GOTO a partir de goto2)

        # ════════════════════════════════════════════════════════════════
        # IFLT offset  (opcode 0x9B):  salta se pop() < 0
        # Usa apenas 0x9B-0x9C como dispatch e desvia para zona alta 0x1B0.
        # ════════════════════════════════════════════════════════════════
        self._rom[0x9B] = mi("iflt1", 0x9C,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.TOS,
            c_bus=CBusDest.H)                            # H = valor a testar
        self._rom[0x9C] = mi("iflt2", 0x1B0,
            alu_op=ALUOperation.INC4_B, b_bus=BBusSource.SP,
            c_bus=CBusDest.SP | CBusDest.MAR, mem_op=MemOp.READ)  # -> zona alta
        self._rom[0x1B0] = mi("iflt3", 0x0B1,
            alu_op=ALUOperation.PASS_B, b_bus=BBusSource.MDR,
            c_bus=CBusDest.TOS)                          # -> 0x0B1 (sem bit 0x100)
        # Testa H: PASS_A(H) -> N=1 se H<0. JAMN desvia para +0x100 se N.
        self._rom[0x0B1] = mi("iflt4", 0x0B2,
            alu_op=ALUOperation.PASS_A,
            jamn=True)                                   # se N: -> 0x1B2 ; senão -> 0x0B2
        self._rom[0x0B2] = mi("iflt_no1", 0x0B3,
            alu_op=ALUOperation.INC_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.PC)
        self._rom[0x0B3] = mi("iflt_no2", 0x00,
            alu_op=ALUOperation.INC_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.PC)
        self._rom[0x1B2] = mi("iflt_yes", 0xA8,
            alu_op=ALUOperation.DEC_B, b_bus=BBusSource.PC,
            c_bus=CBusDest.OPC)

        # ════════════════════════════════════════════════════════════════
        # HALT (opcode 0xFF):  laço infinito detectado pelo controlador
        # ════════════════════════════════════════════════════════════════
        self._rom[0xFF] = mi("HALT", 0xFF,
            alu_op=ALUOperation.ZERO)

    # ── API pública ───────────────────────────────────────────────────────

    def read(self, address: int) -> Microinstruction:
        return self._rom.get(
            address,
            Microinstruction(next_addr=0x00, label=f"NOP@{address:03X}")
        )

    def write(self, address: int, instr: Microinstruction) -> None:
        if not 0 <= address < self.CAPACITY:
            raise ValueError(f"Endereco ROM invalido: {address}")
        self._rom[address] = instr

    def load_program(self, program: Dict[int, Microinstruction]) -> None:
        for addr, instr in program.items():
            self.write(addr, instr)

    def dump(self) -> str:
        lines = ["=== MIC-1 Microcode ROM ==="]
        for addr in sorted(self._rom.keys()):
            lines.append(f"  [{addr:03X}] {self._rom[addr].disassemble()}")
        return "\n".join(lines)

    def entries(self) -> Dict[int, Microinstruction]:
        return dict(self._rom)

    @property
    def loaded_count(self) -> int:
        return len(self._rom)
