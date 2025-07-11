#!/usr/bin/env python3
"""
Script de teste para verificar se o Open-WA está funcionando corretamente
"""

import os
import sys
from dotenv import load_dotenv

# Adiciona o diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_openwa():
    """Testa a funcionalidade do Open-WA"""
    print("🧪 Testando Open-WA...")
    
    try:
        from WhatsApp.wa_enviar_openwa import send_whatsapp_to_multiple_targets, OpenWAAPI
        
        # Testa healthcheck
        print("1. Testando healthcheck...")
        openwa = OpenWAAPI()
        health_status = openwa.healthcheck()
        print(f"   Healthcheck: {'✅ OK' if health_status else '❌ FALHOU'}")
        
        if not health_status:
            print("   ⚠️ Open-WA não está rodando. Execute 'node WhatsApp/start_openwa.js' primeiro.")
            return False
        
        # Testa envio de mensagem
        print("2. Testando envio de mensagem...")
        test_message = "🧪 Teste de integração Open-WA - " + os.getenv("TEST_MODE", "false")
        
        result = send_whatsapp_to_multiple_targets(test_message)
        print(f"   Resultado: {result}")
        
        if result and not isinstance(result, dict):
            print("   ✅ Envio de mensagem funcionou!")
            return True
        elif isinstance(result, dict) and result.get('error'):
            print(f"   ❌ Erro no envio: {result['error']}")
            return False
        else:
            print("   ⚠️ Envio parcial ou com problemas")
            return True
            
    except ImportError as e:
        print(f"❌ Erro ao importar módulos: {e}")
        print("   Verifique se todas as dependências estão instaladas:")
        print("   npm install @open-wa/wa-automate")
        return False
    except Exception as e:
        print(f"❌ Erro geral: {e}")
        return False

def test_telegram():
    """Testa a funcionalidade do Telegram"""
    print("\n📱 Testando Telegram...")
    
    try:
        from Telegram.tl_enviar import send_telegram_message
        
        load_dotenv()
        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID_TESTE") if os.getenv("TEST_MODE") == "true" else os.getenv("TELEGRAM_GROUP_ID")
        
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_GROUP_ID:
            print("   ❌ TELEGRAM_BOT_TOKEN ou TELEGRAM_GROUP_ID não configurados")
            return False
        
        test_message = "🧪 Teste de integração Telegram - " + os.getenv("TEST_MODE", "false")
        
        result = send_telegram_message(
            message=test_message,
            bot_token=TELEGRAM_BOT_TOKEN,
            chat_id=TELEGRAM_GROUP_ID
        )
        
        print(f"   Resultado: {'✅ OK' if result else '❌ FALHOU'}")
        return result
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False

def main():
    """Função principal"""
    print("🚀 Iniciando testes de integração...\n")
    
    load_dotenv()
    
    # Testa configurações
    print("📋 Verificando configurações...")
    required_vars = [
        "TELEGRAM_BOT_TOKEN",
        "WHATSAPP_GROUP_ID_TESTE" if os.getenv("TEST_MODE") == "true" else "WHATSAPP_GROUP_ID"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"   ❌ Variáveis faltando: {', '.join(missing_vars)}")
        print("   Configure essas variáveis no arquivo .env")
        return False
    else:
        print("   ✅ Todas as variáveis necessárias estão configuradas")
    
    # Executa testes
    telegram_ok = test_telegram()
    openwa_ok = test_openwa()
    
    print("\n📊 Resumo dos testes:")
    print(f"   Telegram: {'✅ OK' if telegram_ok else '❌ FALHOU'}")
    print(f"   Open-WA: {'✅ OK' if openwa_ok else '❌ FALHOU'}")
    
    if telegram_ok and openwa_ok:
        print("\n🎉 Todos os testes passaram! O sistema está pronto para uso.")
        return True
    else:
        print("\n⚠️ Alguns testes falharam. Verifique as configurações.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 