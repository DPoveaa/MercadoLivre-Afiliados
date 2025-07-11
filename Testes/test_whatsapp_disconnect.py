#!/usr/bin/env python3
"""
Script para testar a notificação de desconexão do WhatsApp
"""

import os
from dotenv import load_dotenv
from WhatsApp.wa_green_api import GreenAPI

def test_disconnect_notification():
    """Testa a notificação de desconexão"""
    load_dotenv()
    
    print("🔍 Testando notificação de desconexão do WhatsApp...")
    
    # Verifica variáveis de ambiente
    instance_id = os.getenv("GREEN_API_INSTANCE_ID")
    api_token = os.getenv("GREEN_API_TOKEN")
    phone_number = os.getenv("WHATSAPP_PHONE_NUMBER")
    admin_chat_ids = os.getenv("ADMIN_CHAT_IDS", "").split(",") if os.getenv("ADMIN_CHAT_IDS") else []
    
    print(f"GREEN_API_INSTANCE_ID: {'✅ Configurado' if instance_id else '❌ Não configurado'}")
    print(f"GREEN_API_TOKEN: {'✅ Configurado' if api_token else '❌ Não configurado'}")
    print(f"WHATSAPP_PHONE_NUMBER: {'✅ Configurado' if phone_number else '❌ Não configurado'}")
    print(f"ADMIN_CHAT_IDS: {'✅ Configurado' if admin_chat_ids else '❌ Não configurado'}")
    
    if not all([instance_id, api_token, phone_number]):
        print("\n❌ Configuração incompleta. Verifique todas as variáveis no .env")
        return False
    
    if not admin_chat_ids:
        print("\n⚠️ ADMIN_CHAT_IDS não configurado. Configure os IDs dos admins no .env")
        return False
    
    # Cria instância da API
    api = GreenAPI(instance_id, api_token, phone_number)
    
    # Verifica status atual
    print("\n🔗 Verificando status atual...")
    current_status = api.check_connection()
    print(f"Status atual: {'✅ Conectado' if current_status else '❌ Desconectado'}")
    
    if current_status:
        print("\n⚠️ WhatsApp está conectado. Para testar a notificação:")
        print("1. Desconecte o WhatsApp na Green-API")
        print("2. Execute este script novamente")
        return True
    
    # Testa notificação de desconexão
    print("\n📤 Testando notificação de desconexão...")
    api.notify_admins_disconnected(admin_chat_ids)
    
    print("✅ Notificação de desconexão enviada!")
    print("Verifique se os admins receberam a mensagem no Telegram")
    
    return True

def test_connection_verification():
    """Testa a verificação de conexão com notificação"""
    load_dotenv()
    
    print("\n🔍 Testando verificação de conexão com notificação...")
    
    instance_id = os.getenv("GREEN_API_INSTANCE_ID")
    api_token = os.getenv("GREEN_API_TOKEN")
    phone_number = os.getenv("WHATSAPP_PHONE_NUMBER")
    admin_chat_ids = os.getenv("ADMIN_CHAT_IDS", "").split(",") if os.getenv("ADMIN_CHAT_IDS") else []
    
    if not all([instance_id, api_token, phone_number]):
        print("❌ Configuração incompleta")
        return False
    
    # Cria instância da API
    api = GreenAPI(instance_id, api_token, phone_number)
    
    # Testa verificação com notificação
    print("🔗 Verificando conexão...")
    is_connected = api.verify_and_notify_connection(admin_chat_ids)
    
    if is_connected:
        print("✅ WhatsApp conectado - nenhuma notificação enviada")
    else:
        print("❌ WhatsApp desconectado - notificação enviada aos admins")
    
    return True

if __name__ == "__main__":
    print("🚀 Testando sistema de notificação de desconexão...")
    print("=" * 60)
    
    # Teste de notificação
    notification_success = test_disconnect_notification()
    
    if notification_success:
        # Teste de verificação
        verification_success = test_connection_verification()
        
        print("\n" + "=" * 60)
        if verification_success:
            print("🎉 Testes concluídos com sucesso!")
        else:
            print("⚠️ Teste de verificação falhou")
    else:
        print("\n❌ Teste de notificação falhou")
    
    print("\n📝 Para mais informações, consulte o README_WHATSAPP.md") 