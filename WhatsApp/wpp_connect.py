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

import traceback

import socket

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def wpp_check_connection_state():
    """
    Retorna o estado da conexão do WhatsApp.
    Tenta resolver o endereço de forma robusta para Ubuntu Server.
    """
    load_dotenv()
    
    # Prioriza a URL configurada no .env
    base_url = os.getenv("WPP_BASE_URL", "http://localhost:21465").rstrip('/')
    local_ip = get_local_ip()
    
    urls_to_try = [
        f"{base_url}/api/status",
        "http://127.0.0.1:21465/api/status",
        "http://localhost:21465/api/status",
        f"http://{local_ip}:21465/api/status"
    ]
    
    # Remove duplicatas mantendo a ordem
    urls_to_try = list(dict.fromkeys(urls_to_try))
    
    last_error = ""
    for url in urls_to_try:
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [WPP-DEBUG] Testando conexão em: {url}")
            
            # Usando uma sessão para evitar problemas de DNS cache
            with requests.Session() as s:
                r = s.get(url, headers=_wpp_headers(), timeout=10)
                
                if r.status_code == 200:
                    data = r.json()
                    # Verifica múltiplos campos de status para compatibilidade
                    state = str(data.get("state") or data.get("internalStatus") or data.get("status") or "").upper()
                    print(f"[{timestamp}] [WPP-DEBUG] SUCESSO em {url}. Estado: {state}")
                    
                    valid_states = ("CONNECTED", "INCHAT", "ISLOGGED", "SYNCING", "STARTING", "MAIN", "NORMAL")
                    if state in valid_states or data.get("isReady") is True:
                        return 'CONNECTED'
                    
                    return 'DISCONNECTED'
                else:
                    print(f"[{timestamp}] [WPP-DEBUG] URL {url} respondeu status {r.status_code}")
                    
        except Exception as e:
            last_error = str(e)
            print(f"[{timestamp}] [WPP-DEBUG] FALHA em {url}: {last_error}")
            continue
            
    print(f"[{timestamp}] [WPP-DEBUG] Todas as tentativas falharam. Erro final: {last_error}")
    return 'OFFLINE'

def wpp_send_message(destinations, message, image_url=None):
    """
    Envia uma mensagem (com ou sem imagem) para uma lista de destinos.
    """
    if not destinations:
        return False
    
    # Recarrega a URL para garantir que está correta
    base_url = os.getenv("WPP_BASE_URL", "http://localhost:21465").rstrip('/')
    
    success_count = 0
    for dest in destinations:
        # Tenta até 2 vezes em caso de timeout ou erro de URL
        for attempt in range(2):
            try:
                payload = {"caption": message}
                # O wpp_server.js NÃO usa a sessão na URL para send-message e send-file
                if image_url:
                    url = f"{base_url}/api/send-file"
                    payload.update({"url": image_url, "fileName": "image.jpg"})
                else:
                    url = f"{base_url}/api/send-message"
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
