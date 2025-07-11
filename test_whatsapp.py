#!/usr/bin/env python3
"""
Script de teste para verificar a configuração do WhatsApp com Green-API
"""

import os
from dotenv import load_dotenv
from WhatsApp.wa_green_api import send_whatsapp_message, GreenAPI

def test_whatsapp_config():
    """Testa a configuração do WhatsApp"""
    load_dotenv()
    
    print("🔍 Testando configuração do WhatsApp...")
    
    # Verifica variáveis de ambiente
    whatsapp_enabled = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
    instance_id = os.getenv("GREEN_API_INSTANCE_ID")
    api_token = os.getenv("GREEN_API_TOKEN")
    phone_number = os.getenv("WHATSAPP_PHONE_NUMBER")
    
    print(f"WHATSAPP_ENABLED: {whatsapp_enabled}")
    print(f"GREEN_API_INSTANCE_ID: {'✅ Configurado' if instance_id else '❌ Não configurado'}")
    print(f"GREEN_API_TOKEN: {'✅ Configurado' if api_token else '❌ Não configurado'}")
    print(f"WHATSAPP_PHONE_NUMBER: {'✅ Configurado' if phone_number else '❌ Não configurado'}")
    
    if not whatsapp_enabled:
        print("\n⚠️ WhatsApp está desabilitado. Configure WHATSAPP_ENABLED=true no .env")
        return False
    
    if not all([instance_id, api_token, phone_number]):
        print("\n❌ Configuração incompleta. Verifique todas as variáveis no .env")
        return False
    
    # Testa conexão com a API
    print("\n🔗 Testando conexão com a Green-API...")
    api = GreenAPI(instance_id, api_token, phone_number)
    
    if not api.check_connection():
        print("❌ Falha na conexão com a Green-API")
        print("Verifique se:")
        print("1. O WhatsApp está conectado")
        print("2. As credenciais estão corretas")
        print("3. A instância está autorizada")
        return False
    
    print("✅ Conexão com a Green-API estabelecida")
    
    # Testa envio de mensagem
    print("\n📤 Testando envio de mensagem...")
    
    test_message = """
🟡 Teste de Configuração

Este é um teste da configuração do WhatsApp com Green-API.

✅ Se você recebeu esta mensagem, a configuração está funcionando corretamente!

🔗 Link de teste: https://green-api.com/
    """.strip()
    
    success = send_whatsapp_message(
        message=test_message,
        instance_id=instance_id,
        api_token=api_token,
        phone_number=phone_number
    )
    
    if success:
        print("✅ Mensagem de teste enviada com sucesso!")
        print("Verifique se você recebeu a mensagem no WhatsApp")
        return True
    else:
        print("❌ Falha ao enviar mensagem de teste")
        return False

def test_with_image():
    """Testa envio com imagem"""
    load_dotenv()
    
    print("\n🖼️ Testando envio com imagem...")
    
    instance_id = os.getenv("GREEN_API_INSTANCE_ID")
    api_token = os.getenv("GREEN_API_TOKEN")
    phone_number = os.getenv("WHATSAPP_PHONE_NUMBER")
    
    test_message = """
🟡 Teste com Imagem

Este é um teste de envio com imagem usando a Green-API.

✅ Se você recebeu esta mensagem com uma imagem, tudo está funcionando!
    """.strip()
    
    # URL de uma imagem de teste (usando um servidor mais confiável)
    test_image_url = "https://httpbin.org/image/png"
    
    success = send_whatsapp_message(
        message=test_message,
        image_url=test_image_url,
        instance_id=instance_id,
        api_token=api_token,
        phone_number=phone_number
    )
    
    if success:
        print("✅ Mensagem com imagem enviada com sucesso!")
        return True
    else:
        print("❌ Falha ao enviar mensagem com imagem")
        return False

if __name__ == "__main__":
    print("🚀 Iniciando testes do WhatsApp...")
    print("=" * 50)
    
    # Teste básico
    basic_success = test_whatsapp_config()
    
    if basic_success:
        # Teste com imagem
        image_success = test_with_image()
        
        print("\n" + "=" * 50)
        if image_success:
            print("🎉 Todos os testes passaram! WhatsApp configurado corretamente.")
        else:
            print("⚠️ Teste básico passou, mas envio com imagem falhou.")
    else:
        print("\n❌ Teste falhou. Verifique a configuração.")
    
    print("\n📝 Para mais informações, consulte o README_WHATSAPP.md") 