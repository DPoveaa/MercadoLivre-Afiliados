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
    # Recarrega as variáveis do .env a cada chamada para garantir que não estamos usando cache
    load_dotenv()
    
    base_url = os.getenv("WPP_BASE_URL", "http://127.0.0.1:21465")
    
    # Lista de endereços para tentar (priorizando 127.0.0.1 que é mais estável no Ubuntu)
    urls_to_try = [f"{base_url}/api/status"]
    if "localhost" in base_url:
        urls_to_try.append(base_url.replace("localhost", "127.0.0.1") + "/api/status")
    elif "127.0.0.1" in base_url:
        urls_to_try.append(base_url.replace("127.0.0.1", "localhost") + "/api/status")
    
    # Se nenhuma das anteriores funcionar, tenta o IP interno padrão do Docker/Ubuntu
    urls_to_try.append("http://127.0.0.1:21465/api/status")
    
    last_error = ""
    for url in urls_to_try:
        try:
            # USANDO PRINT DIRETO para garantir que apareça no terminal mesmo se o log() falhar
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [WPP-DEBUG] Verificando conexão em: {url}")
            
            r = requests.get(url, headers=_wpp_headers(), timeout=5)
            
            if r.status_code == 200:
                data = r.json()
                state = str(data.get("state") or data.get("internalStatus") or "").upper()
                print(f"[{timestamp}] [WPP-DEBUG] URL {url} respondeu 200. Estado: {state}")
                
                valid_states = ("CONNECTED", "INCHAT", "ISLOGGED", "SYNCING", "STARTING", "MAIN", "NORMAL")
                if state in valid_states or data.get("isReady") is True:
                    return 'CONNECTED'
                
                return 'DISCONNECTED'
            else:
                print(f"[{timestamp}] [WPP-DEBUG] URL {url} respondeu status {r.status_code}")
                
        except Exception as e:
            last_error = str(e)
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
