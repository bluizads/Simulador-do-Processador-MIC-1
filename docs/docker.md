# Executando com Docker

## Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop) instalado

---

## Linux

### 1. Instalar Docker
```bash
sudo apt install docker.io docker-compose-v2
sudo usermod -aG docker $USER
# Reinicie a sessão após isso
```

### 2. Executar
```bash
chmod +x run_docker.sh
./run_docker.sh
```

Ou manualmente:
```bash
xhost +local:docker
docker build -t mic1-simulator .
docker run --rm \
    -e DISPLAY=$DISPLAY \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -e SDL_AUDIODRIVER=dummy \
    mic1-simulator
```

### 3. Com Docker Compose
```bash
xhost +local:docker
docker compose up
```

---

## Windows

### Pré-requisito extra: VcXsrv (servidor X11)

O Pygame precisa de uma janela gráfica. No Windows, o Docker não tem
acesso ao display nativo, então usamos o **VcXsrv** como servidor X11.

#### Instalar o VcXsrv
1. Baixe em: https://vcxsrv.sourceforge.io/
2. Instale normalmente

#### Configurar o VcXsrv
Abra o **XLaunch** e configure:
- ✅ Multiple windows
- Display number: **0**
- ✅ Start no client
- ✅ **Disable access control** ← OBRIGATÓRIO
- Salve a configuração para próximas vezes

#### Executar o simulador
```bat
run_docker.bat
```

Ou manualmente no CMD:
```bat
docker build -t mic1-simulator .
docker run --rm -e DISPLAY=host.docker.internal:0.0 -e SDL_AUDIODRIVER=dummy mic1-simulator
```

---

## macOS

### Pré-requisito: XQuartz
```bash
brew install --cask xquartz
```

Abra o XQuartz, vá em **Preferências → Segurança** e marque:
- ✅ Permitir conexões de clientes de rede

Depois:
```bash
xhost +localhost
docker build -t mic1-simulator .
docker run --rm \
    -e DISPLAY=host.docker.internal:0 \
    -e SDL_AUDIODRIVER=dummy \
    mic1-simulator
```

---

## Verificar se funcionou

Ao executar, deve abrir a janela gráfica do simulador MIC-1.
Se aparecer erro de display, verifique:
1. O VcXsrv/XQuartz está rodando?
2. "Disable access control" está marcado?
3. O Docker Desktop está rodando?
