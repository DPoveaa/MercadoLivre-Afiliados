import requests
import os
from datetime import datetime
import json
import base64
from urllib.parse import urlparse
from Telegram.tl_enviar import send_telegram_message

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

class GreenAPI:
    def __init__(self, instance_id=None, api_token=None, phone_number=None):
        """
        Inicializa a API Green-API do WhatsApp
        
        Args:
            instance_id: ID da instância Green-API
            api_token: Token da API Green-API
            phone_number: Número do WhatsApp para envio (ex: 5511999999999)
        """
        self.instance_id = instance_id or os.getenv("GREEN_API_INSTANCE_ID")
        self.api_token = api_token or os.getenv("GREEN_API_TOKEN")
        self.phone_number = phone_number or os.getenv("WHATSAPP_PHONE_NUMBER")
        
        if not self.instance_id:
            log("Erro: Instance ID da Green-API não configurado")
            return
            
        if not self.api_token:
            log("Erro: Token da Green-API não configurado")
            return
            
        if not self.phone_number:
            log("Erro: Número do WhatsApp não configurado")
            return
    
    def send_text_message(self, message):
        """
        Envia mensagem de texto via WhatsApp usando Green-API
        
        Args:
            message: Texto da mensagem
            
        Returns:
            bool: True se enviado com sucesso, False caso contrário
        """
        if not self.instance_id or not self.api_token or not self.phone_number:
            log("Erro: Configuração incompleta da Green-API")
            return False
            
        try:
            url = f"https://api.green-api.com/waInstance{self.instance_id}/SendMessage/{self.api_token}"
            
            payload = {
                "chatId": f"{self.phone_number}@c.us",
                "message": message
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("idMessage"):
                    log("Mensagem enviada com sucesso para WhatsApp via Green-API")
                    return True
                else:
                    log(f"Erro na resposta da Green-API: {result}")
                    return False
            else:
                log(f"Erro ao enviar mensagem: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            log(f"Erro ao enviar mensagem para WhatsApp via Green-API: {str(e)}")
            return False
    
    def send_media_message(self, message, media_url):
        """
        Envia mensagem com mídia via WhatsApp usando Green-API
        
        Args:
            message: Texto da mensagem
            media_url: URL da imagem/vídeo
            
        Returns:
            bool: True se enviado com sucesso, False caso contrário
        """
        if not self.instance_id or not self.api_token or not self.phone_number:
            log("Erro: Configuração incompleta da Green-API")
            return False
            
        try:
            # Primeiro, baixa a imagem
            image_response = requests.get(media_url)
            if image_response.status_code != 200:
                log(f"Erro ao baixar imagem: {image_response.status_code}")
                return False
            
            # Converte para base64
            image_base64 = base64.b64encode(image_response.content).decode('utf-8')
            
            # Determina o tipo de mídia baseado na URL
            parsed_url = urlparse(media_url)
            file_extension = parsed_url.path.split('.')[-1].lower()
            
            # Mapeia extensões para tipos MIME
            mime_types = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'gif': 'image/gif',
                'webp': 'image/webp',
                'mp4': 'video/mp4',
                'avi': 'video/x-msvideo',
                'mov': 'video/quicktime'
            }
            
            mime_type = mime_types.get(file_extension, 'image/jpeg')
            
            url = f"https://api.green-api.com/waInstance{self.instance_id}/SendFileByUrl/{self.api_token}"
            
            payload = {
                "chatId": f"{self.phone_number}@c.us",
                "urlFile": media_url,
                "fileName": f"image.{file_extension}",
                "caption": message
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("idMessage"):
                    log("Mídia enviada com sucesso para WhatsApp via Green-API")
                    return True
                else:
                    log(f"Erro na resposta da Green-API: {result}")
                    return False
            else:
                log(f"Erro ao enviar mídia: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            log(f"Erro ao enviar mídia para WhatsApp via Green-API: {str(e)}")
            return False
    
    def check_connection(self):
        """
        Verifica se a API está conectada
        
        Returns:
            bool: True se conectado, False caso contrário
        """
        try:
            url = f"https://api.green-api.com/waInstance{self.instance_id}/getStateInstance/{self.api_token}"
            
            response = requests.get(url)
            
            if response.status_code == 200:
                result = response.json()
                state = result.get("stateInstance")
                log(f"Status da Green-API: {state}")
                return state == "authorized"
            else:
                log(f"Erro ao verificar status: {response.status_code}")
                return False
                
        except Exception as e:
            log(f"Erro ao verificar conexão: {str(e)}")
            return False
    
    def notify_admins_disconnected(self, admin_chat_ids):
        """
        Notifica os admins no Telegram sobre a desconexão do WhatsApp
        
        Args:
            admin_chat_ids: Lista de IDs dos admins no Telegram
        """
        if not admin_chat_ids:
            log("Nenhum admin configurado para notificação")
            return
        
        message = """
🚨 **ALERTA: WhatsApp Desconectado**

O WhatsApp foi desconectado da Green-API e precisa ser reautorizado.

**Para reconectar:**
1. Acesse https://green-api.com/
2. Faça login na sua conta
3. Vá para sua instância
4. Escaneie o QR Code novamente
5. Aguarde a autorização

**Status atual:** Desconectado
**Ação necessária:** Reautorização manual

Os scrapers continuarão funcionando apenas para Telegram até a reconexão.
        """.strip()
        
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        
        for admin_id in admin_chat_ids:
            try:
                send_telegram_message(
                    message=message,
                    bot_token=bot_token,
                    chat_id=admin_id
                )
                log(f"Notificação enviada para admin: {admin_id}")
            except Exception as e:
                log(f"Erro ao notificar admin {admin_id}: {str(e)}")
    
    def verify_and_notify_connection(self, admin_chat_ids=None):
        """
        Verifica conexão e notifica admins se desconectado
        
        Args:
            admin_chat_ids: Lista de IDs dos admins (opcional)
            
        Returns:
            bool: True se conectado, False caso contrário
        """
        is_connected = self.check_connection()
        
        if not is_connected and admin_chat_ids:
            log("WhatsApp desconectado - notificando admins...")
            self.notify_admins_disconnected(admin_chat_ids)
        
        return is_connected

def send_whatsapp_message(message, image_url=None, instance_id=None, api_token=None, phone_number=None):
    """
    Função principal para envio de mensagens via WhatsApp usando Green-API
    
    Args:
        message: Texto da mensagem
        image_url: URL da imagem (opcional)
        instance_id: ID da instância Green-API
        api_token: Token da API Green-API
        phone_number: Número do WhatsApp
        
    Returns:
        bool: True se enviado com sucesso, False caso contrário
    """
    whatsapp = GreenAPI(instance_id, api_token, phone_number)
    
    # Verifica conexão primeiro
    if not whatsapp.check_connection():
        log("Erro: Não foi possível conectar com a Green-API")
        return False
    
    # Envia mensagem com ou sem mídia
    if image_url:
        return whatsapp.send_media_message(message, image_url)
    else:
        return whatsapp.send_text_message(message) 