# Guia de Deploy no Ubuntu Server

## 1. Preparação do Servidor

### Instalar dependências básicas:
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git curl wget unzip
```

### Instalar Chrome/Chromium:
```bash
# Instalar Google Chrome
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update
sudo apt install -y google-chrome-stable

# OU instalar Chromium (alternativa)
# sudo apt install -y chromium-browser
```

### Instalar ChromeDriver:
```bash
# Baixar ChromeDriver
CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | awk -F'.' '{print $1}')
wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION"
CHROMEDRIVER_VERSION=$(cat /tmp/chromedriver.zip)
wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip"
unzip /tmp/chromedriver.zip -d /tmp/
sudo mv /tmp/chromedriver /usr/bin/chromedriver
sudo chmod +x /usr/bin/chromedriver
```

### Instalar Docker e Docker Compose:
```bash
# Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

## 2. Configurar o Projeto

### Clonar o repositório:
```bash
git clone <seu-repositorio>
cd "MercadoLivre Afiliados"
```

### Criar ambiente virtual Python:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configurar arquivo .env:
```bash
cp .env.example .env
nano .env
```

Adicione as seguintes variáveis ao .env:
```env
# WhatsApp Open-WA
WHATSAPP_PHONE_NUMBER=5511999999999

# WhatsApp Grupos e Canais
WHATSAPP_GROUP_NAME_TESTE="Grupo Teste"
WHATSAPP_GROUP_NAME="Central De Descontos"
WHATSAPP_CHANNEL_NAME="Central De Descontos"

# Telegram
TELEGRAM_BOT_TOKEN=seu_token
TELEGRAM_GROUP_ID=seu_group_id
TELEGRAM_CHAT_ID=1689537480

# Outras configurações existentes...
```

## 3. Configurar o Open-WA

### Instalar dependências:
```bash
npm install @open-wa/wa-automate
```

### Iniciar o Open-WA:
```bash
cd WhatsApp
node start_openwa.js
```

### Verificar se está rodando:
```bash
ps aux | grep node
```

## 4. Configurar WhatsApp

### Autenticar o Open-WA:
- Execute `node start_openwa.js` no terminal
- Escaneie o QR Code que aparecer no terminal com o WhatsApp do número configurado
- Aguarde a conexão ser estabelecida (aparecerá "✅ Conectado!")

### Adicionar aos grupos e canais:
1. **Grupo de Teste**: Adicione o número do WhatsApp ao grupo "Grupo Teste"
2. **Grupo Principal**: Adicione o número ao grupo "Central De Descontos"
3. **Canal**: Adicione o número ao canal "Central De Descontos"

## 5. Testar a Integração

### Testar envio de mensagem:
```bash
# Ativar ambiente virtual
source venv/bin/activate

# Testar envio
python3 -c "
from WhatsApp.wa_enviar_openwa import send_whatsapp_to_multiple_targets
result = send_whatsapp_to_multiple_targets('Teste de integração WhatsApp!')
print('Resultado:', result)
"
```

## 6. Executar os Scrapers

### Executar individualmente:
```bash
# Mercado Livre
python3 scraper_ml.py

# Kabum
python3 scraper_kabum.py

# Amazon
python3 scraper_amazon.py
```

### Executar em background com screen:
```bash
# Instalar screen
sudo apt install screen

# Criar sessões para cada scraper
screen -S scraper_ml
python3 scraper_ml.py
# Ctrl+A, D para sair

screen -S scraper_kabum
python3 scraper_kabum.py
# Ctrl+A, D para sair

screen -S scraper_amazon
python3 scraper_amazon.py
# Ctrl+A, D para sair

# Monitoramento do WhatsApp
screen -S whatsapp_monitor
python3 whatsapp_monitor.py
# Ctrl+A, D para sair
```

### Verificar sessões:
```bash
screen -ls
screen -r scraper_ml  # para reentrar na sessão
```

## 7. Configurar Auto-start (Opcional)

### Criar serviço systemd para scrapers:
```bash
sudo nano /etc/systemd/system/scrapers.service
```

Conteúdo do arquivo:
```ini
[Unit]
Description=MercadoLivre Afiliados Scrapers
After=network.target

[Service]
Type=simple
User=seu_usuario
WorkingDirectory=/caminho/para/MercadoLivre Afiliados
Environment=PATH=/caminho/para/MercadoLivre Afiliados/venv/bin
ExecStart=/caminho/para/MercadoLivre Afiliados/venv/bin/python3 scraper_ml.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Criar serviço systemd para monitoramento:
```bash
sudo nano /etc/systemd/system/whatsapp_monitor.service
```

Conteúdo do arquivo:
```ini
[Unit]
Description=WhatsApp Connection Monitor
After=network.target

[Service]
Type=simple
User=seu_usuario
WorkingDirectory=/caminho/para/MercadoLivre Afiliados
Environment=PATH=/caminho/para/MercadoLivre Afiliados/venv/bin
ExecStart=/caminho/para/MercadoLivre Afiliados/venv/bin/python3 whatsapp_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Ativar os serviços:
```bash
sudo systemctl daemon-reload
sudo systemctl enable scrapers
sudo systemctl enable whatsapp_monitor
sudo systemctl start scrapers
sudo systemctl start whatsapp_monitor
sudo systemctl status scrapers
sudo systemctl status whatsapp_monitor
```

## 8. Monitoramento

### Verificar logs:
```bash
# Logs do WAHA
docker logs waha

# Logs dos scrapers (se usando systemd)
sudo journalctl -u scrapers -f

# Logs do monitoramento
sudo journalctl -u whatsapp_monitor -f

# Logs do Docker Compose
docker-compose logs -f
```

### Verificar status:
```bash
# Status dos containers
docker ps

# Status dos serviços
sudo systemctl status scrapers
sudo systemctl status whatsapp_monitor

# Testar API WAHA
curl http://localhost:3000/api/status
```

## 9. Comportamento dos Envios

### Modo Teste (TEST_MODE=true):
- ✅ Envia apenas para o grupo "Grupo Teste"
- ✅ Notifica no Telegram se houver problemas de conexão

### Modo Produção (TEST_MODE=false):
- ✅ Envia para o grupo "Central De Descontos"
- ✅ Envia para o canal "Central De Descontos"
- ✅ Notifica no Telegram (chat_id: 1689537480) se houver problemas

## 10. Troubleshooting

### Problemas comuns:

1. **WAHA não conecta:**
   - Verificar se o container está rodando: `docker ps`
   - Verificar logs: `docker logs waha`
   - Reinstalar: `docker-compose down && docker-compose up -d`

2. **Grupos/canais não encontrados:**
   - Verificar se o número está adicionado aos grupos/canais
   - Verificar nomes exatos no .env
   - Testar busca: `curl http://localhost:3000/api/chats`

3. **Chrome/ChromeDriver não funciona:**
   - Verificar versões: `google-chrome --version && chromedriver --version`
   - Reinstalar ChromeDriver se necessário

4. **Scrapers não enviam para WhatsApp:**
   - Verificar variáveis de ambiente no .env
   - Testar conexão: `curl http://localhost:3000/api/status`
   - Verificar se o WhatsApp está conectado na interface web

5. **Notificações do Telegram não chegam:**
   - Verificar TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID
   - Testar envio manual de mensagem para o chat

6. **Erro de permissão:**
   - Adicionar usuário ao grupo docker: `sudo usermod -aG docker $USER`
   - Fazer logout e login novamente

## 11. Backup e Restore

### Backup dos dados:
```bash
# Backup do volume WAHA
docker run --rm -v waha-data:/data -v $(pwd):/backup alpine tar czf /backup/waha-backup.tar.gz -C /data .

# Backup dos arquivos de configuração
tar czf config-backup.tar.gz .env *.json
```

### Restore:
```bash
# Restore do volume WAHA
docker run --rm -v waha-data:/data -v $(pwd):/backup alpine tar xzf /backup/waha-backup.tar.gz -C /data

# Restore dos arquivos de configuração
tar xzf config-backup.tar.gz
``` 