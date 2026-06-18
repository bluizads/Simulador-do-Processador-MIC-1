@echo off
echo.
echo  MIC-1 Simulator (Pygame) v2.0
echo  ================================
echo.

python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERRO] Python nao encontrado no PATH.
    echo Instale em: https://www.python.org/downloads/
    echo Marque "Add Python to PATH" durante a instalacao.
    pause
    exit /b 1
)

FOR /f "tokens=*" %%V IN ('python --version 2^>^&1') DO echo [OK] %%V encontrado.

echo [*] Instalando pygame (caso necessario)...
pip install --quiet pygame

echo.
echo [*] Iniciando simulador...
echo     Controles: ESPACO=Passo  P=Play  R=Reset  E=Editor  ESC=Sair
echo.
python main.py

echo.
echo [*] Simulador encerrado.
pause
