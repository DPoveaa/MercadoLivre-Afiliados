#!/usr/bin/env python3
"""
Script de monitoramento do WhatsApp
Verifica a conexão do WAHA e notifica no Telegram quando há problemas
"""

import time
import schedule
import os
from dotenv import load_dotenv
from WhatsApp.wa_enviar import WhatsAppAPI, notify_telegram_connection_issue

load_dotenv()

def check_whatsapp_connection():
    """
    Verifica a conexão do WhatsApp e notifica se houver problemas
    """
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Verificando conexão do WhatsApp...")
    
    whatsapp = WhatsAppAPI()
    
    # Verifica se consegue conectar
    if not whatsapp.check_connection():
        print("❌ Problema de conexão detectado!")
        
        # Notifica no Telegram
        success = notify_telegram_connection_issue()
        if success:
            print("✅ Notificação enviada para o Telegram")
        else:
            print("❌ Falha ao enviar notificação para o Telegram")
    else:
        print("✅ Conexão do WhatsApp OK")

def main():
    """
    Função principal do monitoramento
    """
    print("🔍 Iniciando monitoramento do WhatsApp...")
    
    # Verifica imediatamente
    check_whatsapp_connection()
    
    # Agenda verificação a cada 5 minutos
    schedule.every(5).minutes.do(check_whatsapp_connection)
    
    print("📅 Monitoramento agendado para verificar a cada 5 minutos")
    print("⏹️  Pressione Ctrl+C para parar")
    
    # Loop principal
    while True:
        try:
            schedule.run_pending()
            time.sleep(30)  # Verifica a cada 30 segundos se há tarefas pendentes
        except KeyboardInterrupt:
            print("\n🛑 Monitoramento interrompido pelo usuário")
            break
        except Exception as e:
            print(f"❌ Erro no monitoramento: {e}")
            time.sleep(60)  # Espera 1 minuto antes de tentar novamente

if __name__ == "__main__":
    main() 