// Exemplo 3: 5 * 3 = 15 (via somas repetidas)
// local 0 = acumulador, local 1 = contador
.main
    BIPUSH 0
    ISTORE 0
    BIPUSH 3
    ISTORE 1

loop:
    ILOAD 1
    IFEQ done

    ILOAD 0
    BIPUSH 5
    IADD
    ISTORE 0

    ILOAD 1
    BIPUSH 1
    ISUB
    ISTORE 1

    GOTO loop

done:
    ILOAD 0
    HALT
.end-main
