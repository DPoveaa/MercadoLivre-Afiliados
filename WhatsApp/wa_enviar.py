import requests
import os
from datetime import datetime
import json

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

class WhatsAppAPI:
    def __init__(self, api_url=None, api_key=None):
        self.api_url = api_url or os.getenv("WAHA_API_URL")
        self.api_key = api_key or os.getenv("WAHA_API_KEY")
        if not self.api_url:
            log("Erro: URL da API WAHA não configurada")
            return
    def healthcheck(self):
        try:
            url = f"{self.api_url}/ping"
            resp = requests.get(url)
            return resp.status_code == 200
        except Exception as e:
            log(f"Erro no healthcheck WAHA: {str(e)}")
            return False
    def send_text(self, chat_id, message):
        try:
            url = f"{self.api_url}/api/sendText"
            payload = {"chatId": chat_id, "text": message}
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            resp = requests.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                log(f"Mensagem enviada para {chat_id}")
                return True
            else:
                log(f"Erro ao enviar mensagem: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            log(f"Erro ao enviar mensagem: {str(e)}")
            return False
    def send_media(self, chat_id, message, media_url):
        try:
            url = f"{self.api_url}/api/sendMedia"
            payload = {"chatId": chat_id, "media": media_url, "caption": message}
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            resp = requests.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                log(f"Mídia enviada para {chat_id}")
                return True
            else:
                log(f"Erro ao enviar mídia: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            log(f"Erro ao enviar mídia: {str(e)}")
            return False

def send_whatsapp_to_multiple_targets(message, image_url=None):
    from dotenv import load_dotenv
    load_dotenv()
    TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"
    waha = WhatsAppAPI()
    if not waha.healthcheck():
        log("WAHA offline!")
        return False
    results = {}
    if TEST_MODE:
        group_id = os.getenv("WHATSAPP_GROUP_ID_TESTE", "120363399821087134@g.us")
        if image_url:
            results['grupo_teste'] = waha.send_media(group_id, message, image_url)
        else:
            results['grupo_teste'] = waha.send_text(group_id, message)
    else:
        group_id = os.getenv("WHATSAPP_GROUP_ID", "120363400146352860@g.us")
        channel_id = os.getenv("WHATSAPP_CHANNEL_ID", "120363401669269114@newsletter")
        if image_url:
            results['grupo'] = waha.send_media(group_id, message, image_url)
            results['canal'] = waha.send_media(channel_id, message, image_url)
        else:
            results['grupo'] = waha.send_text(group_id, message)
            results['canal'] = waha.send_text(channel_id, message)
    return results

def notify_telegram_connection_issue():
    from dotenv import load_dotenv
    from Telegram.tl_enviar import send_telegram_message
    load_dotenv()
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("Erro: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados")
        return False
    message = "⚠️ *ALERTA: Problema de Conexão WhatsApp*\n\nO WhatsApp desconectou ou precisa de reautenticação.\nAcesse a interface do WAHA para reconectar.\n\n📱 *Interface:* http://localhost:3000"
    return send_telegram_message(message=message, bot_token=TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHAT_ID) 