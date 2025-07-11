import time
from WhatsApp.wa_enviar_openwa import OpenWAAPI, notify_telegram_connection_issue

def wait_for_whatsapp_auth(check_interval=10):
    """
    Aguarda até o WhatsApp estar autenticado no Open-WA antes de continuar.
    Se não estiver autenticado, envia alerta no Telegram e pede para autenticar.
    """
    print("🔍 Verificando autenticação do WhatsApp...")
    openwa = OpenWAAPI()
    while True:
        if openwa.healthcheck():
            print("✅ WhatsApp autenticado e pronto!")
            return True
        else:
            print("❌ WhatsApp não autenticado! Acesse o Open-WA e autentique o número.")
            notify_telegram_connection_issue()
            print(f"⏳ Aguardando autenticação... (verificando novamente em {check_interval} segundos)")
            time.sleep(check_interval) 