import os
import time
import requests
import sys
from dotenv import load_dotenv

# Garante que as variáveis do .env estão disponíveis
load_dotenv()

def log(message):
    """Função para logging simples"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [WPP-Client] {message}", flush=True)

def _wpp_headers():
    return {"Content-Type": "application/json"}

def wpp_check_connection_state():
    """
    Verifica o status do WhatsApp via API HTTP.
    Retorna 'CONNECTED' se estiver ok, ou o estado retornado pela API.
    """
    base_url = os.getenv("WPP_BASE_URL", "http://localhost:21465").rstrip('/')
    # No Ubuntu, 127.0.0.1 costuma ser mais estável que localhost
    urls = [f"{base_url}/api/status", "http://127.0.0.1:21465/api/status"]
    
    for url in urls:
        try:
            r = requests.get(url, headers=_wpp_headers(), timeout=5)
            if r.status_code == 200:
                data = r.json()
                state = str(data.get("state") or data.get("internalStatus") or "").upper()
                is_ready = data.get("isReady") is True
                
                valid_states = ("CONNECTED", "INCHAT", "ISLOGGED", "SYNCING", "STARTING", "MAIN", "NORMAL")
                if state in valid_states or is_ready:
                    return 'CONNECTED'
                return state
        except:
            continue
    return 'OFFLINE'

def wpp_send_message(destinations, message, image_url=None):
    """
    Envia mensagem direta para a API WPPConnect.
    """
    if not destinations:
        return False
    
    base_url = os.getenv("WPP_BASE_URL", "http://localhost:21465").rstrip('/')
    success_count = 0
    
    for dest in destinations:
        try:
            payload = {"caption": message}
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

            log(f"Enviando para {dest}...")
            r = requests.post(url, headers=_wpp_headers(), json=payload, timeout=30)
            
            if r.status_code == 200:
                success_count += 1
            else:
                # Tenta fallback para 127.0.0.1 se localhost falhar
                if "localhost" in url:
                    url = url.replace("localhost", "127.0.0.1")
                    r = requests.post(url, headers=_wpp_headers(), json=payload, timeout=30)
                    if r.status_code == 200:
                        success_count += 1
        except Exception as e:
            log(f"Erro ao enviar para {dest}: {e}")
            
    return success_count > 0
