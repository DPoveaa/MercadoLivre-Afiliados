import os
import time
import requests
from dotenv import load_dotenv

# Garante que as variáveis do .env estão disponíveis para este módulo
load_dotenv()

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
        # Tenta o endpoint de status que criamos no wpp_server.js
        url = f"{WPP_BASE_URL}/api/status"
        r = requests.get(url, timeout=3)
        return r.status_code == 200
    except Exception:
        # Se falhar, tenta o root ou api-docs como fallback
        try:
            r = requests.get(f"{WPP_BASE_URL}/", timeout=2)
            return r.status_code in (200, 404) # 404 também significa que o express está rodando
        except:
            return False

def wpp_check_connection_state():
    """
    Retorna o estado da conexão do WhatsApp.
    Tenta resolver o endereço de forma robusta para Ubuntu Server.
    """
    base_url = os.getenv("WPP_BASE_URL", "http://localhost:21465")
    
    # Lista de endereços para tentar (priorizando localhost e 127.0.0.1)
    urls_to_try = [f"{base_url}/api/status"]
    if "localhost" in base_url:
        urls_to_try.append(base_url.replace("localhost", "127.0.0.1") + "/api/status")
    
    last_error = ""
    for url in urls_to_try:
        try:
            log(f"DEBUG: Tentando checar conexão em {url}...")
            # Timeout curto para falhar rápido se não houver resposta e tentar o próximo
            r = requests.get(url, headers=_wpp_headers(), timeout=5)
            
            if r.status_code == 200:
                data = r.json()
                state = str(data.get("state") or data.get("internalStatus") or "").upper()
                
                # Estados considerados como conexão ativa ou pronta
                valid_states = ("CONNECTED", "INCHAT", "ISLOGGED", "SYNCING", "STARTING", "MAIN", "NORMAL")
                if state in valid_states or data.get("isReady") is True:
                    return 'CONNECTED'
                
                log(f"DEBUG: Estado '{state}' recebido de {url}, mas não é considerado pronto.")
                return 'DISCONNECTED'
            else:
                log(f"DEBUG: URL {url} respondeu com status {r.status_code}")
                
        except requests.exceptions.ConnectionError as e:
            last_error = f"Erro de conexão em {url}: {str(e)}"
            continue
        except Exception as e:
            last_error = f"Erro inesperado em {url}: {str(e)}"
            continue
            
    log(f"DEBUG: Todas as tentativas de checagem de conexão falharam. Último erro: {last_error}")
    return 'OFFLINE'

def wpp_send_message(destinations, message, image_url=None):
    """
    Envia uma mensagem (com ou sem imagem) para uma lista de destinos.
    """
    if not destinations:
        return False
    
    # Recarrega a URL para garantir que está correta
    base_url = os.getenv("WPP_BASE_URL", "http://localhost:21465")
    session = os.getenv("WPP_SESSION", "default")
    
    success_count = 0
    for dest in destinations:
        # Tenta até 2 vezes em caso de timeout
        for attempt in range(2):
            try:
                payload = {"caption": message}
                if image_url:
                    url = f"{base_url}/api/{session}/send-file"
                    payload.update({"url": image_url, "fileName": "image.jpg"})
                else:
                    url = f"{base_url}/api/{session}/send-message"
                    payload.update({"message": message})

                if dest.endswith("@g.us"):
                    payload.update({"groupId": dest})
                else:
                    payload.update({"phone": dest.split("@")[0]})

                log(f"Enviando para {dest} via {url}...")
                r = requests.post(url, headers=_wpp_headers(), json=payload, timeout=40)
                
                if r.status_code == 200:
                    success_count += 1
                    break 
                else:
                    log(f"❌ Erro HTTP {r.status_code}: {r.text}")
                    # Se falhar localhost, tenta 127.0.0.1 como último recurso
                    if "localhost" in url:
                        url = url.replace("localhost", "127.0.0.1")
                        log(f"Tentando via IP 127.0.0.1...")
                        r = requests.post(url, headers=_wpp_headers(), json=payload, timeout=40)
                        if r.status_code == 200:
                            success_count += 1
                            break

            except Exception as e:
                log(f"❌ Erro de conexão ao enviar para {dest}: {str(e)}")
                break 
            
    return success_count > 0
