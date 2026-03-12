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
    Retorna o estado da conexão do WhatsApp com logs detalhados para debug.
    """
    url = f"{WPP_BASE_URL}/api/status"
    try:
        log(f"Verificando conexão em: {url}")
        r = requests.get(url, headers=_wpp_headers(), timeout=10)
        
        log(f"Resposta do servidor: Status {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            log(f"Dados recebidos: {data}")
            
            # Pega o estado de qualquer um dos campos possíveis
            state = str(data.get("state") or data.get("internalStatus") or "").upper()
            log(f"Estado identificado: {state}")
            
            # Lista expandida de estados que consideramos como "online/conectado" para o scraper
            valid_states = ("CONNECTED", "INCHAT", "ISLOGGED", "SYNCING", "STARTING", "MAIN", "NORMAL")
            
            if state in valid_states or data.get("isReady") is True:
                return 'CONNECTED'
            
            log(f"Estado '{state}' não é considerado conectado.")
            return 'DISCONNECTED'
        
        log(f"Servidor respondeu com erro: {r.status_code}")
        return 'OFFLINE'

    except requests.exceptions.ConnectionError:
        log(f"Erro de Conexão: Não foi possível alcançar {WPP_BASE_URL}. O servidor Node.js está rodando?")
        return 'OFFLINE'
    except requests.exceptions.Timeout:
        log(f"Erro de Timeout: O servidor em {WPP_BASE_URL} demorou demais para responder.")
        return 'OFFLINE'
    except Exception as e:
        log(f"Erro inesperado na verificação de conexão: {str(e)}")
        return 'OFFLINE'

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

                # Aumentado timeout para 40s (o padrão era 20s)
                r = requests.post(url, headers=_wpp_headers(), json=payload, timeout=40)
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
