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
    session = os.getenv("WPP_SESSION", "default")
    
    # Tenta com e sem sessão para garantir compatibilidade
    urls = [
        f"{base_url}/api/{session}/status",
        f"{base_url}/api/status",
        f"{base_url}/health",
        f"http://127.0.0.1:21465/api/{session}/status"
    ]
    
    for url in urls:
        try:
            r = requests.get(url, headers=_wpp_headers(), timeout=10)
            if r.status_code == 200:
                data = r.json()
                # Tenta extrair o estado de vários campos possíveis
                state = str(data.get("state") or data.get("internalStatus") or data.get("sessionStatus") or "").upper()
                is_ready = data.get("isReady") is True or data.get("status") == "success"
                
                valid_states = ("CONNECTED", "INCHAT", "ISLOGGED", "SYNCING", "STARTING", "MAIN", "NORMAL", "QRCODE")
                if state in valid_states or is_ready:
                    if state == "QRCODE":
                        return "QRCODE"
                    return 'CONNECTED'
                return state
        except:
            continue
    return 'OFFLINE'

def wpp_send_message(destinations, message, image_url=None):
    """
    Envia mensagem direta para a API WPPConnect com suporte a fallback.
    """
    if not destinations:
        log("Nenhum destino fornecido para envio.")
        return False
    
    # Normaliza a URL base removendo barras finais
    base_url = os.getenv("WPP_BASE_URL", "http://localhost:21465").rstrip('/')
    session = os.getenv("WPP_SESSION", "default")
    
    if not session:
        log("ERRO: WPP_SESSION não configurado no .env. Usando 'default'.")
        session = 'default'

    success_count = 0
    
    for dest in destinations:
        try:
            # Constrói o payload básico
            payload = {}
            if image_url:
                url_path = f"/api/{session}/send-file"
                payload = {"caption": message, "url": image_url, "fileName": "image.jpg"}
            else:
                url_path = f"/api/{session}/send-message"
                payload = {"message": message}

            # Define o destinatário
            if "@g.us" in dest:
                payload.update({"groupId": dest.strip()})
            else:
                phone = "".join(filter(str.isdigit, dest))
                if phone:
                    payload.update({"phone": phone})
                else:
                    log(f"⚠️ Destino inválido ignorado: {dest}")
                    continue

            # Tenta envio principal
            url = f"{base_url}{url_path}"
            log(f"Enviando para {dest} via {url}...")
            
            try:
                r = requests.post(url, headers=_wpp_headers(), json=payload, timeout=45)
                
                if r.status_code == 200:
                    success_count += 1
                    log(f"✅ Sucesso ao enviar para {dest}")
                    continue
                else:
                    log(f"❌ Falha ao enviar para {dest} (Status {r.status_code}): {r.text[:100]}")
            except requests.exceptions.RequestException as e:
                log(f"⚠️ Erro de rede na tentativa 1 para {dest}: {e}")

            # Fallback para 127.0.0.1 se falhar ou se o host for localhost
            if "localhost" in base_url or "127.0.0.1" not in base_url:
                url_alt = f"http://127.0.0.1:21465{url_path}"
                log(f"Tentando fallback para {url_alt}...")
                try:
                    r_alt = requests.post(url_alt, headers=_wpp_headers(), json=payload, timeout=45)
                    if r_alt.status_code == 200:
                        success_count += 1
                        log(f"✅ Sucesso no fallback para {dest}")
                    else:
                        log(f"❌ Falha no fallback para {dest} (Status {r_alt.status_code})")
                except requests.exceptions.RequestException as e_alt:
                    log(f"❌ Erro de rede no fallback para {dest}: {e_alt}")

        except Exception as e:
            log(f"🚨 Erro inesperado ao processar envio para {dest}: {e}")
            
    return success_count > 0
