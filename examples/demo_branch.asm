// Exemplo 4: Demonstracao de desvios (IFEQ, IFLT, GOTO)
.main
    BIPUSH -5
    IFLT negativo
    BIPUSH 0
    HALT

negativo:
    BIPUSH 1
    HALT
.end-main
