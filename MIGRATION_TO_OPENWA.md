# Migração do WAHA para Open-WA

Este documento descreve a migração do sistema de WhatsApp do WAHA para o Open-WA, uma alternativa gratuita que suporta envio de imagens com legenda.

## 🚀 Por que migrar?

- **Gratuito**: Open-WA é completamente gratuito
- **Suporte a imagens**: Envio de imagem com legenda funcionando
- **Mais estável**: Menos problemas de conexão
- **Melhor performance**: Mais rápido e eficiente

## 📋 Pré-requisitos

1. **Node.js** instalado (versão 14 ou superior)
2. **Python** com as dependências já instaladas
3. **Chrome/Chromium** instalado no sistema

## 🔧 Instalação

### 1. Instalar dependências do Open-WA

```bash
npm install @open-wa/wa-automate node-fetch
```

### 2. Parar o WAHA (se estiver rodando)

```bash
# Se estiver usando Docker
docker stop waha
docker rm waha

# Ou se estiver rodando como processo
pkill -f waha
```

### 3. Configurar variáveis de ambiente

No arquivo `.env`, remova as variáveis do WAHA e mantenha apenas:

```env
# WhatsApp Open-WA
WHATSAPP_PHONE_NUMBER=5511999999999

# WhatsApp Grupos e Canais
WHATSAPP_GROUP_ID_TESTE=120363399821087134@g.us
WHATSAPP_GROUP_ID=120363400146352860@g.us
WHATSAPP_CHANNEL_ID=120363401669269114@newsletter

# Telegram (mantém as mesmas)
TELEGRAM_BOT_TOKEN=seu_token
TELEGRAM_GROUP_ID=seu_group_id
TELEGRAM_CHAT_ID=1689537480
```

## 🔐 Primeira Autenticação

### 1. Iniciar o Open-WA

```bash
cd WhatsApp
node start_openwa.js
```

### 2. Escanear QR Code

- O QR Code aparecerá no terminal
- Escaneie com o WhatsApp do número configurado
- Aguarde a mensagem "✅ Conectado!"

### 3. Adicionar aos Grupos

- Adicione o número do WhatsApp aos grupos configurados
- Para canais, adicione como administrador

## 🧪 Testar a Integração

### 1. Executar teste completo

```bash
python test_openwa.py
```

### 2. Testar envio manual

```bash
python -c "
from WhatsApp.wa_enviar_openwa import send_whatsapp_to_multiple_targets
result = send_whatsapp_to_multiple_targets('Teste de integração Open-WA!')
print('Resultado:', result)
"
```

## 📁 Arquivos Modificados

### Novos arquivos criados:
- `WhatsApp/wa_enviar_openwa.js` - Implementação Node.js do Open-WA
- `WhatsApp/wa_enviar_openwa.py` - Wrapper Python para o Open-WA
- `WhatsApp/start_openwa.js` - Script de inicialização
- `test_openwa.py` - Script de teste

### Arquivos modificados:
- `scraper_kabum.py` - Import atualizado
- `scraper_ml.py` - Import atualizado  
- `scraper_amazon.py` - Import atualizado
- `WhatsApp/monitor.py` - Import atualizado
- `DEPLOY_UBUNTU.md` - Instruções atualizadas

## 🔄 Diferenças Principais

### WAHA (antigo):
- Requer Docker
- Versão Plus paga para imagens
- API REST via HTTP
- Interface web

### Open-WA (novo):
- Execução direta via Node.js
- Gratuito com suporte completo a imagens
- API nativa do WhatsApp
- Sem interface web (terminal apenas)

## 🚨 Solução de Problemas

### Erro: "Open-WA não está rodando"
```bash
# Iniciar o Open-WA
cd WhatsApp
node start_openwa.js
```

### Erro: "QR Code não aparece"
- Verifique se o Chrome está instalado
- Tente executar com `--headless=false` no script

### Erro: "Falha ao enviar imagem"
- Verifique se a URL da imagem é acessível
- O sistema fará fallback para texto automaticamente

### Erro: "Timeout ao executar script"
- Aumente o timeout no arquivo `wa_enviar_openwa.py`
- Verifique se o Node.js está funcionando

## 📊 Monitoramento

### Verificar status:
```bash
ps aux | grep node
```

### Logs:
- Os logs aparecem no terminal onde o Open-WA está rodando
- Use `screen` ou `tmux` para manter rodando em background

### Reiniciar:
```bash
# Parar processo
pkill -f "start_openwa.js"

# Iniciar novamente
cd WhatsApp
node start_openwa.js
```

## ✅ Checklist de Migração

- [ ] Instalar dependências do Open-WA
- [ ] Parar o WAHA
- [ ] Atualizar variáveis de ambiente
- [ ] Iniciar Open-WA pela primeira vez
- [ ] Escanear QR Code
- [ ] Adicionar aos grupos/canais
- [ ] Executar testes
- [ ] Verificar scrapers funcionando
- [ ] Configurar monitoramento

## 🎯 Benefícios da Migração

1. **Custo zero**: Não precisa mais da versão Plus
2. **Imagens funcionando**: Envio de imagem com legenda
3. **Mais estável**: Menos desconexões
4. **Mais rápido**: Performance melhorada
5. **Menos complexo**: Sem Docker necessário

## 📞 Suporte

Se encontrar problemas:

1. Verifique os logs no terminal
2. Execute `python test_openwa.py`
3. Reinicie o Open-WA se necessário
4. Verifique se o WhatsApp está conectado

---

**Status da Migração**: ✅ Concluída
**Data**: 2025-01-11
**Versão**: 1.0 