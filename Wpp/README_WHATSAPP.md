# Solução de Problemas - WhatsApp

## Problema: WhatsApp aparece como logado mesmo sem arquivo .wwebjs_auth

### Diagnóstico

1. **Verifique o status atual:**
   ```bash
   node Wpp/check_auth.js
   ```

2. **Se o diagnóstico mostrar problemas, execute a limpeza:**
   ```bash
   node Wpp/clear_auth.js
   ```

3. **Reautentique o WhatsApp:**
   ```bash
   node Wpp/wpp_auth.js
   ```

### Soluções por Situação

#### Situação 1: PM2 Restart não resolve
- **Problema:** O PM2 mantém o estado do processo
- **Solução:** 
  ```bash
  pm2 stop scraper_kabum
  pm2 delete scraper_kabum
  pm2 start scraper_kabum.py --name scraper_kabum
  ```

#### Situação 2: Diretório .wwebjs_auth corrompido
- **Problema:** Arquivos de autenticação corrompidos
- **Solução:**
  ```bash
  node Wpp/clear_auth.js
  node Wpp/wpp_auth.js
  ```

#### Situação 3: Múltiplas instâncias
- **Problema:** Várias instâncias do WhatsApp Web rodando
- **Solução:**
  ```bash
  # Pare todas as instâncias
  pm2 stop all
  # Limpe autenticação
  node Wpp/clear_auth.js
  # Reinicie apenas o scraper necessário
  pm2 start scraper_kabum.py --name scraper_kabum
  ```

### Scripts Disponíveis

1. **`check_auth.js`** - Verifica status da autenticação
2. **`clear_auth.js`** - Limpa diretório de autenticação
3. **`wpp_auth.js`** - Reautentica o WhatsApp
4. **`wpp_envio.js`** - Envia mensagens

### Logs Importantes

- **Código 0:** WhatsApp autenticado ✅
- **Código 1:** WhatsApp não autenticado ❌
- **Código 2:** Erro de autenticação ❌

### Comandos Úteis

```bash
# Verificar logs do PM2
pm2 logs scraper_kabum

# Verificar status do PM2
pm2 status

# Reiniciar com limpeza completa
pm2 stop scraper_kabum
node Wpp/clear_auth.js
pm2 start scraper_kabum.py --name scraper_kabum
```

### Estrutura de Arquivos

```
Wpp/
├── wpp_auth.js      # Autenticação
├── wpp_envio.js     # Envio de mensagens
├── clear_auth.js    # Limpeza de autenticação
├── check_auth.js    # Verificação de status
└── README_WHATSAPP.md
``` 