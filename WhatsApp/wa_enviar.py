import requests
import os
from datetime import datetime
import json

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

class WhatsAppAPI:
    def __init__(self, api_url=None, api_key=None, phone_number=None):
        """
        Inicializa a API do WhatsApp
        
        Args:
            api_url: URL da API WAHA (ex: http://localhost:3000)
            api_key: Chave da API (se necessário)
            phone_number: Número do WhatsApp para envio (ex: 5511999999999)
        """
        self.api_url = api_url or os.getenv("WAHA_API_URL")
        self.api_key = api_key or os.getenv("WAHA_API_KEY")
        self.phone_number = phone_number or os.getenv("WHATSAPP_PHONE_NUMBER")
        
        if not self.api_url:
            log("Erro: URL da API WAHA não configurada")
            return
            
        if not self.phone_number:
            log("Erro: Número do WhatsApp não configurado")
            return
    
    def send_text_message(self, message):
        """
        Envia mensagem de texto via WhatsApp
        
        Args:
            message: Texto da mensagem
            
        Returns:
            bool: True se enviado com sucesso, False caso contrário
        """
        if not self.api_url or not self.phone_number:
            log("Erro: Configuração incompleta da API WAHA")
            return False
            
        try:
            url = f"{self.api_url}/api/sendText"
            
            payload = {
                "phone": self.phone_number,
                "text": message
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                log("Mensagem enviada com sucesso para WhatsApp")
                return True
            else:
                log(f"Erro ao enviar mensagem: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            log(f"Erro ao enviar mensagem para WhatsApp: {str(e)}")
            return False
    
    def send_media_message(self, message, media_url):
        """
        Envia mensagem com mídia via WhatsApp
        
        Args:
            message: Texto da mensagem
            media_url: URL da imagem/vídeo
            
        Returns:
            bool: True se enviado com sucesso, False caso contrário
        """
        if not self.api_url or not self.phone_number:
            log("Erro: Configuração incompleta da API WAHA")
            return False
            
        try:
            url = f"{self.api_url}/api/sendMedia"
            
            payload = {
                "phone": self.phone_number,
                "caption": message,
                "media": media_url
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                log("Mídia enviada com sucesso para WhatsApp")
                return True
            else:
                log(f"Erro ao enviar mídia: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            log(f"Erro ao enviar mídia para WhatsApp: {str(e)}")
            return False
    
    def check_connection(self):
        """
        Verifica se a API está conectada
        
        Returns:
            bool: True se conectado, False caso contrário
        """
        try:
            url = f"{self.api_url}/api/status"
            headers = {}
            
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                status = response.json()
                log(f"Status da API WAHA: {status}")
                return True
            else:
                log(f"Erro ao verificar status: {response.status_code}")
                return False
                
        except Exception as e:
            log(f"Erro ao verificar conexão: {str(e)}")
            return False

def send_whatsapp_message(message, image_url=None, api_url=None, api_key=None, phone_number=None):
    """
    Função principal para envio de mensagens via WhatsApp
    
    Args:
        message: Texto da mensagem
        image_url: URL da imagem (opcional)
        api_url: URL da API WAHA
        api_key: Chave da API
        phone_number: Número do WhatsApp
        
    Returns:
        bool: True se enviado com sucesso, False caso contrário
    """
    whatsapp = WhatsAppAPI(api_url, api_key, phone_number)
    
    # Verifica conexão primeiro
    if not whatsapp.check_connection():
        log("Erro: Não foi possível conectar com a API WAHA")
        return False
    
    # Envia mensagem com ou sem mídia
    if image_url:
        return whatsapp.send_media_message(message, image_url)
    else:
        return whatsapp.send_text_message(message) 