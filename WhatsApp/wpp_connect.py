import os
import time
import requests
import socket
import json
import subprocess
import sys
from dotenv import load_dotenv

# Garante que as variáveis do .env estão disponíveis para este módulo
load_dotenv()

def log(message):
    """Função para logging com timestamp e flush forçado"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [WPP-Client] {message}", flush=True)
    sys.stdout.flush()

def _wpp_headers():
    return {"Content-Type": "application/json"}

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def check_port_open(host, port, timeout=2):
    """Verifica se uma porta TCP está aberta usando sockets (mais rápido e imune a proxy)"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False

def wpp_check_connection_state():
    """
    Retorna o estado da conexão do WhatsApp com tripla verificação: Socket -> HTTP -> Curl
    """
    load_dotenv()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Verificação rápida via Socket (Porta 21465)
    # No Ubuntu, 127.0.0.1 é SEMPRE mais seguro que localhost
    if not check_port_open("127.0.0.1", 21465):
        print(f"[{timestamp}] [WPP-DEBUG] Porta 21465 fechada em 127.0.0.1. Servidor parece offline.", flush=True)
        return 'OFFLINE'

    # 2. Verificação via HTTP (API Status)
    # Forçamos bypass de proxy (importante no Linux)
    url = "http://127.0.0.1:21465/api/status"
    try:
        with requests.Session() as s:
            s.trust_env = False # Ignora variáveis de ambiente de proxy (http_proxy, etc)
            r = s.get(url, headers=_wpp_headers(), timeout=10, proxies={"http": None, "https": None})
            
            if r.status_code == 200:
                data = r.json()
                print(f"[{timestamp}] [WPP-DEBUG] HTTP Sucesso: {data}", flush=True)
                state = str(data.get("state") or data.get("internalStatus") or "").upper()
                is_ready = data.get("isReady") is True
                
                valid_states = ("CONNECTED", "INCHAT", "ISLOGGED", "SYNCING", "STARTING", "MAIN", "NORMAL")
                if state in valid_states or is_ready:
                    return 'CONNECTED'
                return 'DISCONNECTED'
    except Exception as e:
        print(f"[{timestamp}] [WPP-DEBUG] Erro HTTP (requests): {e}", flush=True)

    # 3. Fallback via Curl (Comando do sistema - última tentativa)
    try:
        print(f"[{timestamp}] [WPP-DEBUG] Tentando fallback via comando curl...", flush=True)
        cmd = ["curl", "-s", "-X", "GET", url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            print(f"[{timestamp}] [WPP-DEBUG] Curl Sucesso: {data}", flush=True)
            state = str(data.get("state") or data.get("internalStatus") or "").upper()
            if state in ("CONNECTED", "INCHAT", "ISLOGGED", "SYNCING", "STARTING", "MAIN", "NORMAL"):
                return 'CONNECTED'
    except Exception as e:
        print(f"[{timestamp}] [WPP-DEBUG] Erro Fallback (curl): {e}", flush=True)

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
