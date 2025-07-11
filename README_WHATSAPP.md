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
WHATSAPP_PHONE_NUMBER=5511999999999

# Admins para notificação de desconexão (IDs do Telegram)
ADMIN_CHAT_IDS=123456789,987654321
```

### 4. Variáveis de ambiente necessárias

- `WHATSAPP_ENABLED`: Habilita/desabilita o envio para WhatsApp (true/false)
- `GREEN_API_INSTANCE_ID`: ID da instância Green-API
- `GREEN_API_TOKEN`: Token da API Green-API
- `WHATSAPP_PHONE_NUMBER`: Número do WhatsApp para envio (formato: 5511999999999)
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

1. **Verificação de conexão**: No início de cada execução, o sistema verifica se o WhatsApp está conectado
2. **Notificação de desconexão**: Se desconectado, os admins são notificados automaticamente no Telegram
3. **Processamento**: Os scrapers processam os produtos normalmente
4. **Envio inteligente**: 
   - Se WhatsApp conectado: envia para Telegram E WhatsApp
   - Se WhatsApp desconectado: envia apenas para Telegram
5. A mensagem inclui:
   - Título do produto
   - Preços (original e com desconto)
   - Avaliações (se disponível)
   - Parcelamento (se disponível)
   - Link de afiliado
   - Imagem do produto

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