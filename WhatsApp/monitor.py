import time
from WhatsApp.wa_enviar import WhatsAppAPI, notify_telegram_connection_issue

def wait_for_whatsapp_auth(check_interval=10):
    """
    Aguarda até o WhatsApp estar autenticado no WAHA antes de continuar.
    Se não estiver autenticado, envia alerta no Telegram e pede para autenticar.
    """
    print("🔍 Verificando autenticação do WhatsApp...")
    waha = WhatsAppAPI()
    while True:
        if waha.healthcheck():
            print("✅ WhatsApp autenticado e pronto!")
            return True
        else:
            print("❌ WhatsApp não autenticado! Acesse o WAHA e autentique o número.")
            notify_telegram_connection_issue()
            print(f"⏳ Aguardando autenticação... (verificando novamente em {check_interval} segundos)")
            time.sleep(check_interval) 