import requests
import os
from datetime import datetime

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def send_telegram_message(message, image_url=None, bot_token=None, chat_id=None):
    """
    Envia mensagem para o Telegram via URL da imagem
    """
    if not bot_token or not chat_id:
        log("Erro: Token ou Chat ID do Telegram não informado")
        return False

    try:
        # Envio com imagem (URL)
        if image_url:
            response = requests.post(
                f'https://api.telegram.org/bot{bot_token}/sendPhoto',
                data={
                    'chat_id': chat_id,
                    'caption': message,
                    'parse_mode': 'Markdown'
                },
                files={'photo': requests.get(image_url).content}
            )
            if response.status_code == 200:
                return True

        # Envio apenas texto
        response = requests.post(
            f'https://api.telegram.org/bot{bot_token}/sendMessage',
            data={
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
        )
        return response.status_code == 200

    except Exception as e:
        log(f"Erro ao enviar para Telegram: {str(e)}")
        return False