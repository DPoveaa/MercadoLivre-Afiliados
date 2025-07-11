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
    test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
    
    # Verifica destinos baseado no modo
    if test_mode:
        whatsapp_groups = os.getenv("WHATSAPP_GROUPS_TESTE", "")
        whatsapp_channels = os.getenv("WHATSAPP_CHANNELS_TESTE", "")
        mode_text = "TESTE"
    else:
        whatsapp_groups = os.getenv("WHATSAPP_GROUPS", "")
        whatsapp_channels = os.getenv("WHATSAPP_CHANNELS", "")
        mode_text = "PRODUÇÃO"
    
    print(f"WHATSAPP_ENABLED: {whatsapp_enabled}")
    print(f"TEST_MODE: {test_mode} ({mode_text})")
    print(f"GREEN_API_INSTANCE_ID: {'✅ Configurado' if instance_id else '❌ Não configurado'}")
    print(f"GREEN_API_TOKEN: {'✅ Configurado' if api_token else '❌ Não configurado'}")
    print(f"WHATSAPP_GROUPS ({mode_text}): {'✅ Configurado' if whatsapp_groups else '❌ Não configurado'}")
    print(f"WHATSAPP_CHANNELS ({mode_text}): {'✅ Configurado' if whatsapp_channels else '❌ Não configurado'}")
    
    if not whatsapp_enabled:
        print("\n⚠️ WhatsApp está desabilitado. Configure WHATSAPP_ENABLED=true no .env")
        return False
    
    if not all([instance_id, api_token]):
        print("\n❌ Configuração incompleta. Verifique GREEN_API_INSTANCE_ID e GREEN_API_TOKEN no .env")
        return False
    
    if not whatsapp_groups and not whatsapp_channels:
        print(f"\n⚠️ Nenhum grupo ou canal configurado para modo {mode_text}.")
        if test_mode:
            print("Configure WHATSAPP_GROUPS_TESTE ou WHATSAPP_CHANNELS_TESTE no .env")
        else:
            print("Configure WHATSAPP_GROUPS ou WHATSAPP_CHANNELS no .env")
        print("Execute 'python get_whatsapp_ids.py' para obter os IDs")
        return False
    
    # Testa conexão com a API
    print("\n🔗 Testando conexão com a Green-API...")
    api = GreenAPI(instance_id, api_token)
    
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
        api_token=api_token
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
        api_token=api_token
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