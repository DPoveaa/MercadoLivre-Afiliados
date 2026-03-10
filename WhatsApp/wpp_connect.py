import os
import time
import requests
import base64
from Telegram.tl_enviar import send_telegram_message

# Configurações carregadas do ambiente
WPP_BASE_URL = os.getenv("WPP_BASE_URL", "http://localhost:21465")
WPP_SESSION = os.getenv("WPP_SESSION", "default")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

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

def _send_telegram_photo_bytes(caption, image_bytes, chat_id):
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
            data={"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"},
            files={"photo": ("qrcode.jpg", image_bytes)},
            timeout=20,
        )
        return resp.status_code == 200
    except Exception:
        return False

def wpp_get_qrcode_bytes():
    """Tenta obter o QR Code do servidor WPPConnect"""
    try:
        url = f"{WPP_BASE_URL}/api/{WPP_SESSION}/start-session"
        body = {"waitQrCode": True}
        r = requests.post(url, headers=_wpp_headers(), json=body, timeout=65)
        
        if r.status_code == 200:
            j = r.json()
            b64 = j.get("qrcode") or j.get("qrCode") or j.get("base64")
            if b64:
                return base64.b64decode(b64.split(",")[-1])
        
        # Fallback para o endpoint direto de getQrCode
        alt = f"{WPP_BASE_URL}/api/{WPP_SESSION}/getQrCode"
        r2 = requests.get(alt, headers=_wpp_headers(), timeout=10)
        if r2.status_code == 200:
            j2 = r2.json()
            b64 = j2.get("qrcode") or j2.get("qrCode")
            if b64:
                return base64.b64decode(b64.split(",")[-1])
        return None
    except Exception:
        return None

def wpp_check_connection_state():
    """Retorna se o WhatsApp está conectado no servidor"""
    try:
        url = f"{WPP_BASE_URL}/api/{WPP_SESSION}/check-connection-state"
        r = requests.get(url, headers=_wpp_headers(), timeout=10)
        
        if r.status_code != 200:
            return False
        
        data = r.json()
        state = str(data.get("state", "")).upper()
        return state in ("CONNECTED", "INCHAT", "ISLOGGED")
    except Exception:
        return False

def wpp_ensure_connection(admin_chat_ids, wait_seconds=300):
    """
    Garante a conexão do WhatsApp. Se não estiver conectado, inicia o processo
    de envio de QR Code via Telegram e aguarda o escaneamento.
    """
    try:
        if wpp_check_connection_state():
            return True

        log("WhatsApp desconectado no servidor. Iniciando processo de recuperação...")
        
        # Tenta disparar a sessão no servidor PM2
        try:
            requests.post(f"{WPP_BASE_URL}/api/{WPP_SESSION}/start-session", 
                         headers=_wpp_headers(), json={"waitQrCode": True}, timeout=5)
        except:
            pass
        
        if admin_chat_ids:
            for admin_id in admin_chat_ids:
                send_telegram_message("⚠️ WhatsApp desconectado no servidor. Preparando QR Code...", 
                                   bot_token=TELEGRAM_BOT_TOKEN, chat_id=admin_id)

        start_time = time.time()
        last_qr_b64 = None
        
        while time.time() - start_time < wait_seconds:
            if wpp_check_connection_state():
                log("WhatsApp conectado com sucesso!")
                if admin_chat_ids:
                    for admin_id in admin_chat_ids:
                        send_telegram_message("✅ WhatsApp conectado!", 
                                           bot_token=TELEGRAM_BOT_TOKEN, chat_id=admin_id)
                return True

            qr_bytes = wpp_get_qrcode_bytes()
            if qr_bytes:
                curr_b64 = base64.b64encode(qr_bytes).decode('utf-8')
                if curr_b64 != last_qr_b64:
                    log("Novo QR Code detectado. Enviando para admins...")
                    last_qr_b64 = curr_b64
                    if admin_chat_ids:
                        for admin_id in admin_chat_ids:
                            _send_telegram_photo_bytes("📲 Escaneie o novo QR Code para conectar o WPPConnect.", 
                                                    qr_bytes, admin_id)
            
            time.sleep(5)
        
        log(f"Tempo limite de espera ({wait_seconds}s) esgotado.")
        return False
    except Exception as e:
        log(f"Erro ao garantir conexão: {str(e)}")
        return False

def wpp_send_message(destinations, message, image_url=None):
    """
    Envia uma mensagem (com ou sem imagem) para uma lista de destinos.
    """
    if not destinations:
        return False
    
    success_count = 0
    for dest in destinations:
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

            r = requests.post(url, headers=_wpp_headers(), json=payload, timeout=20)
            if r.status_code == 200:
                success_count += 1
        except Exception as e:
            log(f"Erro ao enviar para {dest}: {e}")
            
    return success_count > 0
