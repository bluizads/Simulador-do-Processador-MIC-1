// Exemplo 2: Fibonacci(7) = 13
// Usa 4 variaveis locais: a(0), b(1), contador(2), temp(3)
// Contador = n-1 iteracoes para fib(n)
.main
    BIPUSH 0
    ISTORE 0
    BIPUSH 1
    ISTORE 1
    BIPUSH 6
    ISTORE 2

loop:
    ILOAD 2
    IFEQ done

    ILOAD 0
    ILOAD 1
    IADD
    ISTORE 3

    ILOAD 1
    ISTORE 0

    ILOAD 3
    ISTORE 1

    ILOAD 2
    BIPUSH 1
    ISUB
    ISTORE 2

    GOTO loop

done:
    ILOAD 1
    HALT
.end-main
