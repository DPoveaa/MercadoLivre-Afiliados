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

_HTTP = requests.Session()
# Avoid surprises with HTTP_PROXY/HTTPS_PROXY in cron/docker environments.
_HTTP.trust_env = False

def _normalize_base_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    # Some users set WPP_BASE_URL ending with /api; our callers add /api/... already.
    if url.lower().endswith("/api"):
        url = url[:-4]
    return url.rstrip("/")

def _candidate_base_urls() -> list:
    """
    Returns base URLs to try in order.

    Notes:
    - In Docker, "localhost" points to the container itself, not the host.
    - requests may try to use a proxy from env; we disable that via _HTTP.trust_env=False.
    """
    candidates = []

    def add(u: str):
        u = _normalize_base_url(u)
        if not u:
            return
        if u not in candidates:
            candidates.append(u)

    add(os.getenv("WPP_BASE_URL", "http://localhost:21465"))

    # Optional: comma-separated extra base URLs (useful for Docker/WSL).
    extra = os.getenv("WPP_BASE_URLS", "")
    for part in (p.strip() for p in extra.split(",")):
        add(part)

    # Common fallbacks for "works on host but not in container".
    add("http://127.0.0.1:21465")
    add("http://localhost:21465")
    add("http://host.docker.internal:21465")
    add("http://172.17.0.1:21465")

    return candidates

def _wpp_debug_enabled() -> bool:
    return os.getenv("WPP_DEBUG", "false").lower() == "true"

def _debug(msg: str):
    if _wpp_debug_enabled():
        log(msg)

def wpp_check_connection_state():
    """
    Verifica o status do WhatsApp via API HTTP.
    Retorna 'CONNECTED' se estiver ok, ou o estado retornado pela API.
    """
    session = os.getenv("WPP_SESSION", "default")

    # Try cheap/compatible endpoints first.
    paths = [
        "/health",
        f"/api/{session}/status",
        "/api/status",
    ]

    for base_url in _candidate_base_urls():
        for path in paths:
            url = f"{base_url}{path}"
            try:
                r = _HTTP.get(url, headers=_wpp_headers(), timeout=5, allow_redirects=True)
                if r.status_code != 200:
                    _debug(f"Status check non-200 via {url}: {r.status_code}")
                    continue

                try:
                    data = r.json()
                except Exception:
                    _debug(f"Status check non-JSON via {url}")
                    return "CONNECTED"

                # Tenta extrair o estado de vários campos possíveis
                state = str(data.get("state") or data.get("internalStatus") or data.get("sessionStatus") or "").upper()
                # "status" (success/ok) means the HTTP endpoint responded, not that WhatsApp is connected.
                is_ready = data.get("isReady") is True

                # Treat only "connected-like" states as ready. STARTING/SYNCING are not ready for sending.
                valid_states = ("CONNECTED", "INCHAT", "ISLOGGED", "MAIN", "NORMAL", "QRCODE")
                if state in valid_states or is_ready:
                    if state == "QRCODE":
                        return "QRCODE"
                    return "CONNECTED"

                if state:
                    return state

                _debug(f"Status check empty-state via {url}: {str(data)[:200]}")
            except Exception as e:
                _debug(f"Status check failed via {url}: {e}")
                continue
    return 'OFFLINE'


def wpp_wait_until_connected():
    """
    Blocks until WPPConnect is CONNECTED (when WhatsApp delivery is required).

    Env knobs:
    - WPP_WAIT_INTERVAL_SECONDS (default: 10)
    - WPP_WAIT_TIMEOUT_SECONDS  (default: 0 => infinite)
    """
    try:
        interval = int(os.getenv("WPP_WAIT_INTERVAL_SECONDS", "10"))
    except Exception:
        interval = 10
    if interval <= 0:
        interval = 10

    try:
        timeout = int(os.getenv("WPP_WAIT_TIMEOUT_SECONDS", "0"))
    except Exception:
        timeout = 0

    started = time.time()
    attempts = 0

    while True:
        attempts += 1
        state = wpp_check_connection_state()
        if state == "CONNECTED":
            if attempts > 1:
                log("✅ WhatsApp conectado. Continuando.")
            return True

        log(f"⚠️ WhatsApp não está pronto (state={state}). Tentando novamente em {interval}s...")
        if timeout > 0 and (time.time() - started) >= timeout:
            log(f"❌ Timeout esperando WhatsApp conectar (state={state}).")
            return False

        time.sleep(interval)

def wpp_send_message(destinations, message, image_url=None):
    """
    Envia mensagem direta para a API WPPConnect com suporte a fallback.
    """
    if not destinations:
        log("Nenhum destino fornecido para envio.")
        return False

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

            dest = (dest or "").strip()
            if not dest:
                continue

            # Define o destinatário:
            # - grupos: use groupId (ex: 120...@g.us)
            # - destinos com '@' (ex: canais/newsletter): mande como "phone" sem mutilar o sufixo
            # - telefones: extrai apenas dígitos
            if "@g.us" in dest:
                payload.update({"groupId": dest})
            elif "@" in dest:
                payload.update({"phone": dest})
            else:
                phone = "".join(filter(str.isdigit, dest))
                if phone:
                    payload.update({"phone": phone})
                else:
                    log(f"⚠️ Destino inválido ignorado: {dest}")
                    continue

            sent = False
            last_err = None
            for base_url in _candidate_base_urls():
                url = f"{base_url}{url_path}"
                log(f"Enviando para {dest} via {url}...")
                try:
                    r = _HTTP.post(url, headers=_wpp_headers(), json=payload, timeout=45)
                    if r.status_code == 200:
                        success_count += 1
                        log(f"✅ Sucesso ao enviar para {dest}")
                        sent = True
                        break
                    last_err = f"HTTP {r.status_code}: {r.text[:200]}"
                    _debug(f"Send failed via {url}: {last_err}")
                except requests.exceptions.RequestException as e:
                    last_err = str(e)
                    _debug(f"Send network error via {url}: {e}")

            if not sent and last_err:
                log(f"❌ Falha ao enviar para {dest}: {last_err[:200]}")

        except Exception as e:
            log(f"🚨 Erro inesperado ao processar envio para {dest}: {e}")
            
    return success_count > 0
