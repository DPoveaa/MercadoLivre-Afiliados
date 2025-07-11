#!/usr/bin/env python3
"""
Script para verificar se a configuração atual do .env está correta
"""

import os
from dotenv import load_dotenv

def verificar_configuracao():
    """Verifica se a configuração atual está correta"""
    load_dotenv()
    
    print("🔍 Verificando configuração atual do .env...")
    print("=" * 60)
    
    # Configurações básicas
    whatsapp_enabled = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
    instance_id = os.getenv("GREEN_API_INSTANCE_ID")
    api_token = os.getenv("GREEN_API_TOKEN")
    test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
    
    print(f"✅ WHATSAPP_ENABLED: {whatsapp_enabled}")
    print(f"✅ GREEN_API_INSTANCE_ID: {'✅ Configurado' if instance_id else '❌ Não configurado'}")
    print(f"✅ GREEN_API_TOKEN: {'✅ Configurado' if api_token else '❌ Não configurado'}")
    print(f"✅ TEST_MODE: {test_mode}")
    
    # Destinos de produção
    whatsapp_groups = os.getenv("WHATSAPP_GROUPS", "")
    whatsapp_channels = os.getenv("WHATSAPP_CHANNELS", "")
    
    print(f"\n🚀 DESTINOS DE PRODUÇÃO:")
    print(f"   Grupos: {'✅ Configurado' if whatsapp_groups else '❌ Não configurado'}")
    if whatsapp_groups:
        grupos = whatsapp_groups.split(",")
        for i, grupo in enumerate(grupos, 1):
            print(f"   Grupo {i}: {grupo.strip()}")
    
    print(f"   Canais: {'✅ Configurado' if whatsapp_channels else '❌ Não configurado'}")
    if whatsapp_channels:
        canais = whatsapp_channels.split(",")
        for i, canal in enumerate(canais, 1):
            print(f"   Canal {i}: {canal.strip()}")
    
    # Destinos de teste
    whatsapp_groups_teste = os.getenv("WHATSAPP_GROUPS_TESTE", "")
    whatsapp_channels_teste = os.getenv("WHATSAPP_CHANNELS_TESTE", "")
    
    print(f"\n🔬 DESTINOS DE TESTE:")
    print(f"   Grupos: {'✅ Configurado' if whatsapp_groups_teste else '❌ Não configurado'}")
    if whatsapp_groups_teste:
        grupos_teste = whatsapp_groups_teste.split(",")
        for i, grupo in enumerate(grupos_teste, 1):
            print(f"   Grupo {i}: {grupo.strip()}")
    
    print(f"   Canais: {'✅ Configurado' if whatsapp_channels_teste else '❌ Não configurado'}")
    if whatsapp_channels_teste:
        canais_teste = whatsapp_channels_teste.split(",")
        for i, canal in enumerate(canais_teste, 1):
            print(f"   Canal {i}: {canal.strip()}")
    
    # Admins
    admin_chat_ids = os.getenv("ADMIN_CHAT_IDS", "")
    print(f"\n👥 ADMINS:")
    print(f"   IDs: {'✅ Configurado' if admin_chat_ids else '❌ Não configurado'}")
    if admin_chat_ids:
        admins = admin_chat_ids.split(",")
        for i, admin in enumerate(admins, 1):
            print(f"   Admin {i}: {admin.strip()}")
    
    # Análise
    print(f"\n📊 ANÁLISE:")
    print("=" * 60)
    
    problemas = []
    
    if not whatsapp_enabled:
        problemas.append("❌ WHATSAPP_ENABLED está false")
    
    if not instance_id:
        problemas.append("❌ GREEN_API_INSTANCE_ID não configurado")
    
    if not api_token:
        problemas.append("❌ GREEN_API_TOKEN não configurado")
    
    if not whatsapp_groups and not whatsapp_channels:
        problemas.append("❌ Nenhum destino de produção configurado")
    
    if not whatsapp_groups_teste and not whatsapp_channels_teste:
        problemas.append("❌ Nenhum destino de teste configurado")
    
    if not admin_chat_ids:
        problemas.append("⚠️ ADMIN_CHAT_IDS não configurado (notificações de desconexão não funcionarão)")
    
    if problemas:
        print("❌ PROBLEMAS ENCONTRADOS:")
        for problema in problemas:
            print(f"   {problema}")
    else:
        print("✅ CONFIGURAÇÃO CORRETA!")
        print(f"   Modo atual: {'TESTE' if test_mode else 'PRODUÇÃO'}")
        
        if test_mode:
            destinos = []
            if whatsapp_groups_teste:
                destinos.extend(whatsapp_groups_teste.split(","))
            if whatsapp_channels_teste:
                destinos.extend(whatsapp_channels_teste.split(","))
            print(f"   Destinos de teste: {len(destinos)}")
        else:
            destinos = []
            if whatsapp_groups:
                destinos.extend(whatsapp_groups.split(","))
            if whatsapp_channels:
                destinos.extend(whatsapp_channels.split(","))
            print(f"   Destinos de produção: {len(destinos)}")
    
    print(f"\n💡 PRÓXIMOS PASSOS:")
    if problemas:
        print("1. Configure as variáveis que estão faltando")
        print("2. Execute 'python get_whatsapp_ids.py' para obter IDs se necessário")
        print("3. Execute 'python test_whatsapp.py' para testar")
    else:
        print("1. Execute 'python test_whatsapp.py' para testar")
        print("2. Execute os scrapers normalmente")

if __name__ == "__main__":
    verificar_configuracao() 