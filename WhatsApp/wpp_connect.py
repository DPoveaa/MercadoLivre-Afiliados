import os
import time
import requests

# Configurações carregadas do ambiente
WPP_BASE_URL = os.getenv("WPP_BASE_URL", "http://localhost:21465")
WPP_SESSION = os.getenv("WPP_SESSION", "default")

def log(message):
    """Função para logging com timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [WPP-Client] {message}")

def _wpp_headers():
    return {"Content-Type": "application/json"}

def wpp_server_is_up():
    """Verifica se o servidor WPPConnect (que deve rodar via PM2) está online"""
    try:
        url = f"{WPP_BASE_URL}/api-docs"
        r = requests.get(url, timeout=3)
        return r.status_code == 200
    except Exception:
        return False

def wpp_check_connection_state():
    """
    Retorna o estado da conexão do WhatsApp.
    Retorna:
      - 'CONNECTED': Tudo OK
      - 'DISCONNECTED': Servidor online mas WhatsApp deslogado
      - 'OFFLINE': Servidor PM2 está desligado
      - 'ERROR': Outro erro de comunicação
    """
    if not wpp_server_is_up():
        return 'OFFLINE'
        
    try:
        url = f"{WPP_BASE_URL}/api/{WPP_SESSION}/check-connection-state"
        r = requests.get(url, headers=_wpp_headers(), timeout=5)
        
        if r.status_code != 200:
            return 'ERROR'
        
        data = r.json()
        state = str(data.get("state", "")).upper()
        
        if state in ("CONNECTED", "INCHAT", "ISLOGGED"):
            return 'CONNECTED'
        return 'DISCONNECTED'
    except Exception:
        return 'ERROR'

def wpp_send_message(destinations, message, image_url=None):
    """
    Envia uma mensagem (com ou sem imagem) para uma lista de destinos.
    """
    if not destinations:
        return False
    
    success_count = 0
    for dest in destinations:
        # Tenta até 2 vezes em caso de timeout
        for attempt in range(2):
            try:
                payload = {"caption": message}
                if image_url:
                    url = f"{WPP_BASE_URL}/api/{WPP_SESSION}/send-file"
                    payload.update({"url": image_url, "fileName": "image.jpg"})
                else:
                    url = f"{WPP_BASE_URL}/api/{WPP_SESSION}/send-message"
                    payload.update({"message": message})

                if dest.endswith("@g.us"):
                    payload.update({"groupId": dest})
                else:
                    payload.update({"phone": dest.split("@")[0]})

                # Aumentado timeout para 60s (o anterior era 40s)
                r = requests.post(url, headers=_wpp_headers(), json=payload, timeout=60)
                if r.status_code == 200:
                    success_count += 1
                    break # Sucesso, sai do loop de tentativas
                else:
                    log(f"Falha ao enviar para {dest} (tentativa {attempt+1}): Status {r.status_code}")
            except requests.exceptions.Timeout:
                log(f"Timeout ao enviar para {dest} (tentativa {attempt+1})")
                if attempt == 0:
                    time.sleep(2) # Espera um pouco antes de tentar de novo
            except Exception as e:
                log(f"Erro ao enviar para {dest}: {e}")
                break # Erro crítico, não tenta de novo para este destino
            
    return success_count > 0
