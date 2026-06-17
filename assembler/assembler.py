"""
MIC-1 / IJVM Assembler
========================
Complete two-pass assembler for IJVM assembly language.
Generates binary, hex, and memory dump output.

Supported instructions:
  BIPUSH n       - push signed byte constant
  IADD           - integer add (top two stack values)
  ISUB           - integer subtract
  IAND           - integer AND
  IOR            - integer OR
  DUP            - duplicate top of stack
  POP            - discard top of stack
  SWAP           - swap top two stack values
  ILOAD  index   - push local variable
  ISTORE index   - pop to local variable
  GOTO   label   - unconditional jump
  IFEQ   label   - branch if top == 0
  IFLT   label   - branch if top < 0
  IF_ICMPEQ label- branch if top two equal
  INVOKEVIRTUAL  - invoke method
  IRETURN        - return integer
  HALT           - halt
"""

from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────── #
# Token types                                                                 #
# ────────────────────────────────────────────────────────────────────────────#

class TokenType(IntEnum):
    IDENTIFIER = auto()
    NUMBER     = auto()
    LABEL_DEF  = auto()    # "identifier:"
    DIRECTIVE  = auto()    # ".word", ".main"
    NEWLINE    = auto()
    EOF        = auto()
    COMMENT    = auto()


@dataclass
class Token:
    type:   TokenType
    value:  str
    line:   int
    column: int


# ────────────────────────────────────────────────────────────────────────── #
# IJVM opcodes                                                                #
# ────────────────────────────────────────────────────────────────────────────#

OPCODES: Dict[str, int] = {
    "BIPUSH":        0x10,
    "LDC_W":         0x13,
    "ILOAD":         0x15,
    "ISTORE":        0x36,
    "IADD":          0x60,
    "ISUB":          0x64,
    "IAND":          0x7E,
    "IOR":           0x80,
    "DUP":           0x59,
    "POP":           0x57,
    "SWAP":          0x5F,
    "GOTO":          0xA7,
    "IFEQ":          0x99,
    "IFLT":          0x9B,
    "IF_ICMPEQ":     0x9F,
    "INVOKEVIRTUAL": 0xB6,
    "IRETURN":       0xAC,
    "HALT":          0xFF,
    "NOP":           0x00,
    "ERR":           0xFE,
    "OUT":           0xFD,
    "IN":            0xFC,
}

# Instructions that take operands and their sizes in bytes
OPERAND_SIZES: Dict[str, int] = {
    "BIPUSH":        1,   # 1 byte signed
    "LDC_W":         2,   # 2 byte index
    "ILOAD":         1,   # 1 byte index
    "ISTORE":        1,   # 1 byte index
    "GOTO":          2,   # 2 byte offset
    "IFEQ":          2,
    "IFLT":          2,
    "IF_ICMPEQ":     2,
    "INVOKEVIRTUAL": 2,
}


# ────────────────────────────────────────────────────────────────────────── #
# Assembler errors                                                            #
# ────────────────────────────────────────────────────────────────────────────#

@dataclass
class AssemblerError:
    message: str
    line:    int
    column:  int = 0

    def __str__(self) -> str:
        return f"Line {self.line}, col {self.column}: {self.message}"


@dataclass
class AssemblyResult:
    """Result of assembling a source file."""
    success:    bool
    binary:     bytes                   = b""
    errors:     List[AssemblerError]    = field(default_factory=list)
    warnings:   List[AssemblerError]    = field(default_factory=list)
    symbol_table: Dict[str, int]        = field(default_factory=dict)
    source_map:   Dict[int, int]        = field(default_factory=dict)  # addr -> line

    def hex_dump(self) -> str:
        lines = []
        for i in range(0, len(self.binary), 16):
            chunk = self.binary[i:i + 16]
            hex_part   = " ".join(f"{b:02X}" for b in chunk)
            ascii_part = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in chunk)
            lines.append(f"{i:08X}  {hex_part:<47}  |{ascii_part}|")
        return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────────── #
# Tokenizer                                                                   #
# ────────────────────────────────────────────────────────────────────────────#

class Tokenizer:
    """Converts IJVM assembly source text into a token stream."""

    TOKEN_PATTERNS = [
        (TokenType.COMMENT,   r'//.*'),
        (TokenType.LABEL_DEF, r'[A-Za-z_][A-Za-z0-9_]*:'),
        (TokenType.DIRECTIVE, r'\.[A-Za-z_][A-Za-z0-9_\-]*'),
        (TokenType.NUMBER,    r'-?0x[0-9A-Fa-f]+|-?\d+'),
        (TokenType.IDENTIFIER, r'[A-Za-z_][A-Za-z0-9_]*'),
        (TokenType.NEWLINE,   r'\n'),
    ]

    def __init__(self) -> None:
        parts = []
        for ttype, pattern in self.TOKEN_PATTERNS:
            parts.append(f"(?P<T{ttype.value}>{pattern})")
        self._regex = re.compile("|".join(parts))

    def tokenize(self, source: str) -> List[Token]:
        tokens: List[Token] = []
        line = 1
        line_start = 0

        for match in self._regex.finditer(source):
            col = match.start() - line_start + 1
            value = match.group()

            # Identify token type by group name
            for ttype, _ in self.TOKEN_PATTERNS:
                group_name = f"T{ttype.value}"
                if match.group(group_name) is not None:
                    if ttype == TokenType.NEWLINE:
                        tokens.append(Token(TokenType.NEWLINE, "\n", line, col))
                        line += 1
                        line_start = match.end()
                    elif ttype != TokenType.COMMENT:
                        tokens.append(Token(ttype, value, line, col))
                    break

        tokens.append(Token(TokenType.EOF, "", line, 0))
        return tokens


# ────────────────────────────────────────────────────────────────────────── #
# Assembler                                                                   #
# ────────────────────────────────────────────────────────────────────────────#

class Assembler:
    """
    Two-pass IJVM Assembler.
    
    Pass 1: collect labels and calculate addresses
    Pass 2: emit binary code with resolved labels
    """

    DEFAULT_ORIGIN = 0x0000

    def __init__(self) -> None:
        self._tokenizer = Tokenizer()

    def assemble_file(self, path: str) -> AssemblyResult:
        """Assemble an .asm file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()
        except OSError as e:
            return AssemblyResult(
                success=False,
                errors=[AssemblerError(str(e), 0)],
            )
        return self.assemble(source)

    def assemble(self, source: str) -> AssemblyResult:
        """
        Assemble IJVM source code.
        
        Args:
            source: Assembly source code string
            
        Returns:
            AssemblyResult with binary output and diagnostics
        """
        errors: List[AssemblerError] = []
        warnings: List[AssemblerError] = []

        # Tokenize
        tokens = self._tokenizer.tokenize(source)

        # Pass 1: collect symbols
        symbols: Dict[str, int] = {}
        pc = self.DEFAULT_ORIGIN
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok.type == TokenType.LABEL_DEF:
                name = tok.value.rstrip(":")
                if name in symbols:
                    errors.append(AssemblerError(
                        f"Duplicate label: '{name}'", tok.line, tok.column
                    ))
                else:
                    symbols[name] = pc
                i += 1
            elif tok.type == TokenType.IDENTIFIER:
                mnem = tok.value.upper()
                if mnem in OPCODES:
                    pc += 1  # opcode byte
                    if mnem in OPERAND_SIZES:
                        pc += OPERAND_SIZES[mnem]
                i += 1
            elif tok.type in (TokenType.NEWLINE, TokenType.EOF, TokenType.NUMBER):
                i += 1
            elif tok.type == TokenType.DIRECTIVE:
                i = self._handle_directive_pass1(tokens, i, symbols, errors)
            else:
                i += 1

        if errors:
            return AssemblyResult(False, errors=errors, warnings=warnings,
                                  symbol_table=symbols)

        # Pass 2: emit code
        binary: List[int] = []
        source_map: Dict[int, int] = {}
        i = 0
        pc = self.DEFAULT_ORIGIN

        while i < len(tokens):
            tok = tokens[i]

            if tok.type == TokenType.LABEL_DEF:
                i += 1
                continue

            if tok.type == TokenType.DIRECTIVE:
                # Diretivas como .main, .end-main etc. são ignoradas no pass2
                i += 1
                continue

            if tok.type == TokenType.IDENTIFIER:
                mnem = tok.value.upper()
                if mnem not in OPCODES:
                    errors.append(AssemblerError(
                        f"Unknown mnemonic: '{tok.value}'", tok.line, tok.column
                    ))
                    i += 1
                    continue

                source_map[pc] = tok.line
                binary.append(OPCODES[mnem])
                pc += 1

                if mnem in OPERAND_SIZES:
                    op_size = OPERAND_SIZES[mnem]
                    i += 1
                    # Skip newlines
                    while i < len(tokens) and tokens[i].type == TokenType.NEWLINE:
                        i += 1
                    if i >= len(tokens) or tokens[i].type == TokenType.EOF:
                        errors.append(AssemblerError(
                            f"Missing operand for {mnem}", tok.line, tok.column
                        ))
                        continue

                    operand_tok = tokens[i]
                    operand = self._resolve_operand(
                        operand_tok, mnem, pc, symbols, errors
                    )

                    if op_size == 1:
                        binary.append(operand & 0xFF)
                        pc += 1
                    else:
                        binary.append((operand >> 8) & 0xFF)
                        binary.append(operand & 0xFF)
                        pc += 2

            i += 1

        if errors:
            return AssemblyResult(False, errors=errors, warnings=warnings,
                                  symbol_table=symbols)

        return AssemblyResult(
            success=True,
            binary=bytes(binary),
            errors=errors,
            warnings=warnings,
            symbol_table=symbols,
            source_map=source_map,
        )

    def _resolve_operand(
        self,
        tok: Token,
        mnem: str,
        pc: int,
        symbols: Dict[str, int],
        errors: List[AssemblerError],
    ) -> int:
        """Resolve a numeric or label operand."""
        if tok.type == TokenType.NUMBER:
            value = self._parse_int(tok.value)
            # ILOAD/ISTORE: o índice de variável é multiplicado por 4
            # (tamanho da palavra) para gerar o offset em bytes a partir
            # de LV, mantendo o endereçamento alinhado a palavras no
            # microcódigo (ver microcode/microinstruction.py).
            if mnem in ("ILOAD", "ISTORE"):
                value *= 4
                if value > 0xFF:
                    errors.append(AssemblerError(
                        f"Índice de variável muito grande para {mnem} "
                        f"(máx. 63): {value // 4}", tok.line, tok.column
                    ))
            return value
        elif tok.type == TokenType.IDENTIFIER:
            name = tok.value
            if name not in symbols:
                errors.append(AssemblerError(
                    f"Undefined label: '{name}'", tok.line, tok.column
                ))
                return 0
            target = symbols[name]
            # Branch instructions use relative offsets
            if mnem in ("GOTO", "IFEQ", "IFLT", "IF_ICMPEQ"):
                return (target - pc + 1) & 0xFFFF
            return target
        else:
            errors.append(AssemblerError(
                f"Expected operand, got '{tok.value}'", tok.line, tok.column
            ))
            return 0

    def _handle_directive_pass1(
        self,
        tokens: List[Token],
        i: int,
        symbols: Dict[str, int],
        errors: List[AssemblerError],
    ) -> int:
        """Process assembler directives in pass 1."""
        tok = tokens[i]
        directive = tok.value.upper()
        if directive == ".MAIN":
            symbols["__main__"] = 0
        # .constant and .var sections are parsed but simplified here
        return i + 1

    @staticmethod
    def _parse_int(s: str) -> int:
        """Parse integer literal (decimal or hex)."""
        try:
            if s.startswith("0x") or s.startswith("0X"):
                return int(s, 16)
            return int(s, 10)
        except ValueError:
            return 0
