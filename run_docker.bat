@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM run_docker.bat — Executa o MIC-1 Simulator via Docker (Windows)
REM Requer: Docker Desktop + VcXsrv (X11 server para Windows)
REM ─────────────────────────────────────────────────────────────────────────────

echo.
echo  MIC-1 Simulator ^— Docker (Windows)
echo  =====================================
echo.

docker --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERRO] Docker nao encontrado.
    echo Instale Docker Desktop: https://www.docker.com/products/docker-desktop
    pause & exit /b 1
)
echo [OK] Docker encontrado.

echo.
echo [AVISO] Certifique-se de que o VcXsrv esta rodando com:
echo   - Multiple windows
echo   - Display number: 0
echo   - "Disable access control" MARCADO
echo.
echo Baixe o VcXsrv em: https://vcxsrv.sourceforge.io/
echo.
pause

echo [*] Build da imagem...
docker build -t mic1-simulator . --quiet

echo [*] Iniciando simulador...
docker run --rm ^
    -e DISPLAY=host.docker.internal:0.0 ^
    -e SDL_AUDIODRIVER=dummy ^
    --name mic1-sim ^
    mic1-simulator

echo.
echo [*] Simulador encerrado.
pause
