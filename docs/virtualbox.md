# Executando com VirtualBox

## Visão Geral

O VirtualBox cria uma máquina virtual Ubuntu onde o simulador roda
nativamente, sem precisar de X11 forwarding.

---

## 1. Baixar e Instalar o VirtualBox

https://www.virtualbox.org/wiki/Downloads

Escolha a versão para seu sistema (Windows/macOS/Linux).

---

## 2. Baixar a ISO do Ubuntu

https://ubuntu.com/download/desktop

Recomendado: **Ubuntu 24.04 LTS Desktop** (~5 GB)

---

## 3. Criar a Máquina Virtual

No VirtualBox, clique em **Novo** e configure:

| Campo | Valor recomendado |
|-------|-------------------|
| Nome | MIC1-Simulator |
| Tipo | Linux |
| Versão | Ubuntu (64-bit) |
| RAM | 4096 MB (mínimo 2048) |
| Disco | 20 GB (dinâmico) |

### Configurações adicionais (antes de ligar)
- **Display → Vídeo:** 128 MB VRAM, habilitar aceleração 2D
- **Sistema → Processador:** 2 CPUs

---

## 4. Instalar o Ubuntu

1. Ligue a VM e selecione a ISO do Ubuntu
2. Instale normalmente (instalação mínima é suficiente)
3. Crie um usuário (ex: `aluno`)

---

## 5. Instalar o Guest Additions (melhora a experiência)

Dentro da VM Ubuntu, abra o terminal:
```bash
sudo apt update
sudo apt install -y build-essential dkms linux-headers-$(uname -r)
```

No menu do VirtualBox: **Dispositivos → Inserir imagem do Guest Additions**

```bash
sudo /media/$USER/VBox_GAs_*/VBoxLinuxAdditions.run
sudo reboot
```

---

## 6. Instalar as Dependências

Dentro da VM Ubuntu:
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git

# Dependências do Pygame
sudo apt install -y \
    libsdl2-2.0-0 libsdl2-image-2.0-0 \
    libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0 \
    fonts-dejavu-core
```

---

## 7. Copiar o Projeto para a VM

### Opção A — Pasta Compartilhada (recomendado)

1. No VirtualBox (VM desligada): **Configurações → Pastas Compartilhadas**
2. Adicione a pasta onde está o `mic1_pygame` no seu computador
3. Marque **Montar automaticamente** e **Acesso permanente**
4. Na VM:
```bash
sudo adduser $USER vboxsf
# Reinicie a VM
ls /media/sf_*   # pasta compartilhada aparece aqui
```

### Opção B — Pendrive USB

Conecte o pendrive e copie a pasta `mic1_pygame` para `~/`.

### Opção C — Download direto na VM

```bash
# Se tiver acesso à internet na VM:
# Copie o ZIP via navegador ou wget
unzip mic1_pygame.zip -d ~/
```

---

## 8. Executar o Simulador

```bash
cd ~/mic1_pygame
chmod +x run.sh
./run.sh
```

O script instala o pygame e abre o simulador automaticamente.

Ou manualmente:
```bash
pip install pygame
python3 main.py
```

---

## 9. Tirar Screenshot para o Relatório

No VirtualBox: **Visualizar → Tirar Screenshot**

Ou dentro da VM: `PrintScreen` → abre no aplicativo de capturas.

---

## Resolução de Problemas

| Problema | Solução |
|----------|---------|
| Janela muito pequena | VirtualBox → View → Auto-resize Guest Display |
| Pygame não instala | `sudo apt install python3-pygame` |
| Sem acesso à internet | Configurações → Rede → Adaptador: NAT |
| Pasta compartilhada não aparece | Adicionar usuário ao grupo vboxsf e reiniciar |
