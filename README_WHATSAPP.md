# Configuração do WhatsApp com Green-API

Este projeto agora suporta envio de mensagens para WhatsApp usando a API Green-API gratuita.

## Configuração da Green-API

### 1. Criar conta na Green-API
1. Acesse https://green-api.com/
2. Crie uma conta gratuita
3. Crie uma nova instância
4. Anote o `Instance ID` e `API Token`

### 2. Configurar o WhatsApp
1. Escaneie o QR Code com seu WhatsApp
2. Aguarde a autorização
3. Teste o status da instância

### 3. Configurar o arquivo .env

Adicione as seguintes variáveis ao seu arquivo `.env`:

```env
# Configurações do WhatsApp Green-API
WHATSAPP_ENABLED=true
GREEN_API_INSTANCE_ID=seu_instance_id_aqui
GREEN_API_TOKEN=seu_api_token_aqui

# Grupos e Canais do WhatsApp - PRODUÇÃO (IDs separados por vírgula)
WHATSAPP_GROUPS=120363025123456789@g.us,120363025987654321@g.us
WHATSAPP_CHANNELS=120363025123456789@c.us,120363025987654321@c.us

# Grupos e Canais do WhatsApp - TESTE (IDs separados por vírgula)
WHATSAPP_GROUPS_TESTE=120363025123456789@g.us
WHATSAPP_CHANNELS_TESTE=120363025123456789@c.us

# Admins para notificação de desconexão (IDs do Telegram)
ADMIN_CHAT_IDS=123456789,987654321
```

### 4. Variáveis de ambiente necessárias

- `WHATSAPP_ENABLED`: Habilita/desabilita o envio para WhatsApp (true/false)
- `GREEN_API_INSTANCE_ID`: ID da instância Green-API
- `GREEN_API_TOKEN`: Token da API Green-API

**Destinos de PRODUÇÃO:**
- `WHATSAPP_GROUPS`: IDs dos grupos do WhatsApp (separados por vírgula, formato: 120363025123456789@g.us)
- `WHATSAPP_CHANNELS`: IDs dos canais do WhatsApp (separados por vírgula, formato: 120363025123456789@c.us)

**Destinos de TESTE:**
- `WHATSAPP_GROUPS_TESTE`: IDs dos grupos de teste do WhatsApp
- `WHATSAPP_CHANNELS_TESTE`: IDs dos canais de teste do WhatsApp

- `ADMIN_CHAT_IDS`: IDs dos admins no Telegram para notificação de desconexão (separados por vírgula)

## Funcionalidades

### Envio de mensagens com imagem
- Os scrapers agora enviam mensagens com imagens dos produtos
- Suporte a diferentes formatos de imagem (JPG, PNG, GIF, WebP)
- Fallback para envio sem imagem em caso de erro

### Integração com todos os scrapers
- Mercado Livre (`scraper_ml.py`)
- Kabum (`scraper_kabum.py`)
- Amazon (`scraper_amazon.py`)

### Logs detalhados
- Logs de sucesso e erro para cada envio
- Verificação de conexão com a API
- Status de autorização da instância
- Notificação automática aos admins em caso de desconexão

## Como funciona

1. **Verificação de modo**: O sistema verifica se está em modo TESTE ou PRODUÇÃO
2. **Seleção de destinos**: 
   - **Modo TESTE**: Envia para grupos/canais de teste
   - **Modo PRODUÇÃO**: Envia para grupos/canais de produção
3. **Verificação de conexão**: No início de cada execução, o sistema verifica se o WhatsApp está conectado
4. **Notificação de desconexão**: Se desconectado, os admins são notificados automaticamente no Telegram
5. **Processamento**: Os scrapers processam os produtos normalmente
6. **Envio inteligente**: 
   - Se WhatsApp conectado: envia para Telegram E múltiplos grupos/canais do WhatsApp
   - Se WhatsApp desconectado: envia apenas para Telegram
7. A mensagem inclui:
   - Título do produto
   - Preços (original e com desconto)
   - Avaliações (se disponível)
   - Parcelamento (se disponível)
   - Link de afiliado
   - Imagem do produto

## Como obter IDs de grupos e canais

### Para grupos:
1. Adicione o bot do WhatsApp aos grupos desejados
2. Use a API para obter o ID do grupo
3. Formato: `120363025123456789@g.us`

### Para canais:
1. Adicione o bot do WhatsApp aos canais desejados
2. Use a API para obter o ID do canal
3. Formato: `120363025123456789@c.us`

## Procedimento em caso de desconexão

Quando o WhatsApp for desconectado:

1. **Notificação automática**: Os admins receberão uma mensagem no Telegram
2. **Instruções detalhadas**: A mensagem incluirá passos para reconectar
3. **Funcionamento contínuo**: Os scrapers continuarão funcionando apenas para Telegram
4. **Reconexão**: Siga as instruções na notificação para reautorizar o WhatsApp

## Teste da configuração

Para testar se a configuração está correta, execute:

```python
from WhatsApp.wa_green_api import send_whatsapp_message

# Teste de envio
success = send_whatsapp_message(
    message="Teste de configuração do WhatsApp",
    instance_id="seu_instance_id",
    api_token="seu_api_token",
    phone_number="5511999999999"
)

if success:
    print("✅ Configuração correta!")
else:
    print("❌ Erro na configuração")
```

## Limitações da versão gratuita

- Máximo de 100 mensagens por dia
- Uma instância por conta
- Necessário manter o WhatsApp conectado

## Suporte

Em caso de problemas:
1. Verifique se o WhatsApp está conectado
2. Confirme se as credenciais estão corretas
3. Teste a conexão com a API
4. Verifique os logs de erro 