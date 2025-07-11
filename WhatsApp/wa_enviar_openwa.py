import os
import subprocess
import json
import time
from datetime import datetime
from dotenv import load_dotenv

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

class OpenWAAPI:
    def __init__(self):
        self.node_script_path = os.path.join(os.path.dirname(__file__), 'wa_enviar_openwa.js')
        self.is_initialized = False
        
    def _run_node_script(self, function_name, *args):
        """Executa uma função no script Node.js"""
        try:
            # Constrói o comando para executar a função específica
            cmd = ['node', '-e', f'''
                const {{ {function_name} }} = require('./{os.path.basename(self.node_script_path)}');
                {function_name}(...{json.dumps(args)}).then(result => {{
                    console.log(JSON.stringify({{ success: true, result }}));
                }}).catch(error => {{
                    console.log(JSON.stringify({{ success: false, error: error.message }}));
                }});
            ''']
            
            # Executa o comando
            result = subprocess.run(
                cmd,
                cwd=os.path.dirname(self.node_script_path),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                try:
                    output = json.loads(result.stdout.strip())
                    if output.get('success'):
                        return output.get('result')
                    else:
                        log(f"Erro no Node.js: {output.get('error')}")
                        return False
                except json.JSONDecodeError:
                    log(f"Erro ao parsear resposta do Node.js: {result.stdout}")
                    return False
            else:
                log(f"Erro ao executar Node.js: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            log("Timeout ao executar script Node.js")
            return False
        except Exception as e:
            log(f"Erro ao executar script Node.js: {str(e)}")
            return False
    
    def healthcheck(self):
        """Verifica se o Open-WA está funcionando"""
        try:
            result = self._run_node_script('healthcheck')
            return result if result is not None else False
        except Exception as e:
            log(f"Erro no healthcheck: {str(e)}")
            return False
    
    def send_text(self, chat_id, message):
        """Envia mensagem de texto"""
        try:
            result = self._run_node_script('sendTextMessage', chat_id, message)
            return result if result is not None else False
        except Exception as e:
            log(f"Erro ao enviar texto: {str(e)}")
            return False
    
    def send_media(self, chat_id, message, media_url):
        """Envia imagem com legenda"""
        try:
            result = self._run_node_script('sendImageMessage', chat_id, message, media_url)
            return result if result is not None else False
        except Exception as e:
            log(f"Erro ao enviar mídia: {str(e)}")
            return False

def send_whatsapp_to_multiple_targets(message, image_url=None):
    """Função principal para enviar mensagens para múltiplos destinos"""
    load_dotenv()
    
    TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"
    openwa = OpenWAAPI()
    
    if not openwa.healthcheck():
        log("Open-WA offline!")
        return False
    
    results = {}
    
    try:
        if TEST_MODE:
            group_id = os.getenv("WHATSAPP_GROUP_ID_TESTE", "120363399821087134@g.us")
            if image_url:
                results['grupo_teste'] = openwa.send_media(group_id, message, image_url)
            else:
                results['grupo_teste'] = openwa.send_text(group_id, message)
        else:
            group_id = os.getenv("WHATSAPP_GROUP_ID", "120363400146352860@g.us")
            channel_id = os.getenv("WHATSAPP_CHANNEL_ID", "120363401669269114@newsletter")
            
            if image_url:
                results['grupo'] = openwa.send_media(group_id, message, image_url)
                results['canal'] = openwa.send_media(channel_id, message, image_url)
            else:
                results['grupo'] = openwa.send_text(group_id, message)
                results['canal'] = openwa.send_text(channel_id, message)
        
        log(f"Resultado envio WhatsApp: {results}")
        return results
        
    except Exception as e:
        log(f"Erro geral no envio WhatsApp: {str(e)}")
        return { 'error': str(e) }

def notify_telegram_connection_issue():
    """Notifica problemas de conexão no Telegram"""
    from Telegram.tl_enviar import send_telegram_message
    
    load_dotenv()
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID1 = os.getenv("TELEGRAM_CHAT_ID")
    TELEGRAM_CHAT_ID2 = os.getenv("TELEGRAM_CHAT_ID2")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID1:
        log("Erro: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados")
        return False
    
    message = (
        "⚠️ *ALERTA: Problema de Conexão WhatsApp*\n\n"
        "O WhatsApp desconectou ou precisa de reautenticação.\n"
        "Verifique a conexão do Open-WA.\n\n"
        "*Status:* Aguardando reconexão automática"
    )
    
    results = {}
    
    # Envia para o primeiro chat
    results['chat1'] = send_telegram_message(
        message=message,
        bot_token=TELEGRAM_BOT_TOKEN,
        chat_id=TELEGRAM_CHAT_ID1
    )
    
    # Envia para o segundo chat, se existir
    if TELEGRAM_CHAT_ID2:
        results['chat2'] = send_telegram_message(
            message=message,
            bot_token=TELEGRAM_BOT_TOKEN,
            chat_id=TELEGRAM_CHAT_ID2
        )
    
    return results

def wait_for_whatsapp_auth(check_interval=10):
    """Aguarda até o WhatsApp estar autenticado"""
    log("🔍 Verificando autenticação do WhatsApp...")
    openwa = OpenWAAPI()
    
    while True:
        if openwa.healthcheck():
            log("✅ WhatsApp autenticado e pronto!")
            return True
        else:
            log("❌ WhatsApp não autenticado! Aguardando QR code...")
            notify_telegram_connection_issue()
            log(f"⏳ Aguardando autenticação... (verificando novamente em {check_interval} segundos)")
            time.sleep(check_interval) 