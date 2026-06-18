# MIC-1 Microarchitecture Simulator

Simulador didático da microarquitetura **MIC-1** (Tanenbaum, Cap. 4)
implementado em Python com interface gráfica Pygame.

## Componentes implementados

| Componente | Status |
|------------|--------|
| Montador IJVM (assembler) | Completo |
| Registradores (PC, MAR, MDR, MBR, SP, LV, CPP, TOS, OPC, H) | Visíveis |
| Barramentos A, B e C | Animados no diagrama |
| ALU + Shifter | Com flags N e Z |
| Memória Principal | Hex dump em tempo real |
| ROM de Microcódigo (512 × 36 bits) | Visível com destaque |
| Cache de Instruções (I-Cache) | Hit/miss em tempo real |
| Cache de Dados (D-Cache) | Hit/miss em tempo real |
| Encapsulamento Docker | Dockerfile + Compose |
| Encapsulamento VirtualBox | Documentado |

---

## Execução Rápida

### Windows (CMD)
```
run.bat
```

### Linux / macOS
```bash
chmod +x run.sh && ./run.sh
```

### Docker (Linux)
```bash
xhost +local:docker
./run_docker.sh
```

### Docker (Windows) — requer VcXsrv
```
run_docker.bat
```

---

## Controles

| Tecla | Ação |
|-------|------|
| `ESPAÇO` | Executar um ciclo (step) |
| `P` | Play / Pause (execução contínua) |
| `R` | Reset |
| `↑` / `↓` | Aumentar / diminuir velocidade |
| `E` | Abrir editor de Assembly IJVM |
| `Ctrl+Enter` | (no editor) Montar e carregar programa |
| `TAB` | Alternar painel direito: Microcódigo ↔ Memória |
| `ESC` | Sair |

---

## Layout da Interface

```
┌─────────────────────────────────────────────────────────────────────┐
│  MIC-1  CPU: RESET  Ciclo: 0  MPC: 000  Vel: 4Hz                   │
├──────────────┬──────────────┬───────────┬──────────────────────────┤
│  DATAPATH    │ REGISTRADORES│   CACHE   │  MICROCÓDIGO / MEMÓRIA   │
│              │              │           │                          │
│ Registradores│ PC  0x000000 │ I-Cache   │  [000] Main1 FETCH →001  │
│ Bus A (red)  │ MAR 0x000000 │ ████   66%│  [001] Main2 INC_B →002  │
│ Bus B (green)│ MDR 0x000000 │ Hits:  12 │  [002] Main3 JMPC →000   │
│ Bus C (blue) │ MBR 0x00     │ Miss:   6 │  ...                     │
│ ALU+Shifter  │ SP  0x001000 │           │                          │
│ Memória      │ ...          │ D-Cache   │                          │
│              │              │ ██     33%│                          │
│              │              │ Hits:   2 │                          │
│              │              │ Miss:   4 │                          │
├──────────────┴──────────────┴───────────┴──────────────────────────┤
│  LOG DE EXECUÇÃO                                                   │
│  #   1  MPC=000  Main1: MAR <- PASS_B(H,PC)  FETCH  -> 001         │
│  #   2  MPC=001  Main2: PC <- INC_B(H,PC)  -> 002                  │
└────────────────────────────────────────────────────────────────────┘
```

---

## Instruções IJVM Suportadas

| Instrução | Opcode | Descrição |
|-----------|--------|-----------|
| `BIPUSH n` | 0x10 | Empilha byte com sinal (-128 a 127) |
| `ILOAD i` | 0x15 | Empilha variável local i |
| `ISTORE i` | 0x36 | Desempilha para variável local i |
| `IADD` | 0x60 | Soma dos dois topos |
| `ISUB` | 0x64 | Subtração (2º − 1º) |
| `IAND` | 0x7E | AND lógico |
| `IOR` | 0x80 | OR lógico |
| `DUP` | 0x59 | Duplica topo |
| `POP` | 0x57 | Descarta topo |
| `SWAP` | 0x5F | Troca dois topos |
| `GOTO label` | 0xA7 | Salto incondicional |
| `IFEQ label` | 0x99 | Salta se TOS == 0 |
| `IFLT label` | 0x9B | Salta se TOS < 0 |
| `HALT` | 0xFF | Para execução |
| `NOP` | 0x00 | Sem operação |

---

## Exemplos incluídos

| Arquivo | Descrição | Resultado |
|---------|-----------|-----------|
| `examples/soma.asm` | 10 + 20 | TOS = 30 |
| `examples/fibonacci.asm` | Fibonacci(7) | TOS = 13 |
| `examples/multiplicacao.asm` | 5 × 3 | TOS = 15 |
| `examples/demo_branch.asm` | Desvio condicional | TOS = 1 |

---

## Docker

Ver: [docs/docker.md](docs/docker.md)

## VirtualBox

Ver: [docs/virtualbox.md](docs/virtualbox.md)

---

## Referência

Andrew S. Tanenbaum — *Organização Estruturada de Computadores*, 5ª Ed., Cap. 4
