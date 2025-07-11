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
    
    def send_text_message(self, message, chat_id=None):
        """
        Envia mensagem de texto via WhatsApp
        
        Args:
            message: Texto da mensagem
            chat_id: ID do chat (grupo/canal) ou None para número pessoal
            
        Returns:
            bool: True se enviado com sucesso, False caso contrário
        """
        if not self.api_url:
            log("Erro: Configuração incompleta da API WAHA")
            return False
            
        try:
            url = f"{self.api_url}/api/sendText"
            
            payload = {
                "text": message
            }
            
            # Se chat_id for fornecido, usa ele, senão usa o número pessoal
            if chat_id:
                payload["chatId"] = chat_id
            else:
                payload["phone"] = self.phone_number
            
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
    
    def send_media_message(self, message, media_url, chat_id=None):
        """
        Envia mensagem com mídia via WhatsApp
        
        Args:
            message: Texto da mensagem
            media_url: URL da imagem/vídeo
            chat_id: ID do chat (grupo/canal) ou None para número pessoal
            
        Returns:
            bool: True se enviado com sucesso, False caso contrário
        """
        if not self.api_url:
            log("Erro: Configuração incompleta da API WAHA")
            return False
            
        try:
            url = f"{self.api_url}/api/sendMedia"
            
            payload = {
                "caption": message,
                "media": media_url
            }
            
            # Se chat_id for fornecido, usa ele, senão usa o número pessoal
            if chat_id:
                payload["chatId"] = chat_id
            else:
                payload["phone"] = self.phone_number
            
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
    
    def get_chat_id_by_name(self, chat_name):
        """
        Busca o ID de um chat pelo nome
        
        Args:
            chat_name: Nome do grupo/canal
            
        Returns:
            str: ID do chat ou None se não encontrado
        """
        try:
            url = f"{self.api_url}/api/chats"
            headers = {}
            
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                chats = response.json()
                for chat in chats:
                    if chat.get('name') == chat_name:
                        return chat.get('id')
                
                log(f"Chat '{chat_name}' não encontrado")
                return None
            else:
                log(f"Erro ao buscar chats: {response.status_code}")
                return None
                
        except Exception as e:
            log(f"Erro ao buscar chat por nome: {str(e)}")
            return None
    
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

def send_whatsapp_message(message, image_url=None, api_url=None, api_key=None, phone_number=None, chat_name=None):
    """
    Função principal para envio de mensagens via WhatsApp
    
    Args:
        message: Texto da mensagem
        image_url: URL da imagem (opcional)
        api_url: URL da API WAHA
        api_key: Chave da API
        phone_number: Número do WhatsApp
        chat_name: Nome do grupo/canal (opcional)
        
    Returns:
        bool: True se enviado com sucesso, False caso contrário
    """
    whatsapp = WhatsAppAPI(api_url, api_key, phone_number)
    
    # Verifica conexão primeiro
    if not whatsapp.check_connection():
        log("Erro: Não foi possível conectar com a API WAHA")
        return False
    
    # Busca chat_id se chat_name for fornecido
    chat_id = None
    if chat_name:
        chat_id = whatsapp.get_chat_id_by_name(chat_name)
        if not chat_id:
            log(f"Erro: Não foi possível encontrar o chat '{chat_name}'")
            return False
    
    # Envia mensagem com ou sem mídia
    if image_url:
        return whatsapp.send_media_message(message, image_url, chat_id)
    else:
        return whatsapp.send_text_message(message, chat_id)

def send_whatsapp_to_multiple_targets(message, image_url=None):
    """
    Envia mensagem para múltiplos destinos (grupo e canal) baseado no modo de teste
    
    Args:
        message: Texto da mensagem
        image_url: URL da imagem (opcional)
        
    Returns:
        dict: Resultado do envio para cada destino
    """
    from dotenv import load_dotenv
    load_dotenv()
    
    TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"
    
    results = {}
    
    if TEST_MODE:
        # Modo teste - envia apenas para grupo de teste
        group_name = os.getenv("WHATSAPP_GROUP_NAME_TESTE")
        if group_name:
            results['teste'] = send_whatsapp_message(
                message=message,
                image_url=image_url,
                chat_name=group_name
            )
    else:
        # Modo produção - envia para grupo e canal
        group_name = os.getenv("WHATSAPP_GROUP_NAME")
        channel_name = os.getenv("WHATSAPP_CHANNEL_NAME", "Central De Descontos")
        
        if group_name:
            results['grupo'] = send_whatsapp_message(
                message=message,
                image_url=image_url,
                chat_name=group_name
            )
        
        if channel_name:
            results['canal'] = send_whatsapp_message(
                message=message,
                image_url=image_url,
                chat_name=channel_name
            )
    
    return results

def notify_telegram_connection_issue():
    """
    Notifica no Telegram quando há problema de conexão com WhatsApp
    """
    from dotenv import load_dotenv
    from Telegram.tl_enviar import send_telegram_message
    import os
    
    load_dotenv()
    
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("Erro: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados")
        return False
    
    message = "⚠️ *ALERTA: Problema de Conexão WhatsApp*\n\n"
    message += "O WhatsApp desconectou ou precisa de reautenticação.\n"
    message += "Acesse a interface do WAHA para reconectar.\n\n"
    message += "📱 *Interface:* http://localhost:3000"
    
    return send_telegram_message(
        message=message,
        bot_token=TELEGRAM_BOT_TOKEN,
        chat_id=TELEGRAM_CHAT_ID
    ) 