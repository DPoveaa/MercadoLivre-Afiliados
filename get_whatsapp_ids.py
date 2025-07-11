#!/usr/bin/env python3
"""
Script para obter IDs de grupos e canais do WhatsApp usando Green-API
"""

import os
import requests
from dotenv import load_dotenv

def get_chat_list(instance_id, api_token):
    """
    Obtém a lista de chats (grupos e canais) do WhatsApp
    
    Args:
        instance_id: ID da instância Green-API
        api_token: Token da API Green-API
        
    Returns:
        list: Lista de chats
    """
    try:
        url = f"https://api.green-api.com/waInstance{instance_id}/GetChats/{api_token}"
        
        response = requests.get(url)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erro ao obter lista de chats: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Erro ao obter lista de chats: {str(e)}")
        return []

def get_chat_history(instance_id, api_token, chat_id):
    """
    Obtém o histórico de um chat específico
    
    Args:
        instance_id: ID da instância Green-API
        api_token: Token da API Green-API
        chat_id: ID do chat
        
    Returns:
        dict: Informações do chat
    """
    try:
        url = f"https://api.green-api.com/waInstance{instance_id}/GetChatHistory/{api_token}"
        
        payload = {
            "chatId": chat_id,
            "count": 1
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erro ao obter histórico do chat {chat_id}: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"Erro ao obter histórico do chat {chat_id}: {str(e)}")
        return []

def main():
    """Função principal"""
    load_dotenv()
    
    print("🔍 Obtendo IDs de grupos e canais do WhatsApp...")
    
    # Verifica configuração
    instance_id = os.getenv("GREEN_API_INSTANCE_ID")
    api_token = os.getenv("GREEN_API_TOKEN")
    test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
    
    if not instance_id or not api_token:
        print("❌ Configure GREEN_API_INSTANCE_ID e GREEN_API_TOKEN no .env")
        return
    
    print(f"🔬 Modo atual: {'TESTE' if test_mode else 'PRODUÇÃO'}")
    
    # Obtém lista de chats
    print("\n📋 Obtendo lista de chats...")
    chats = get_chat_list(instance_id, api_token)
    
    if not chats:
        print("❌ Nenhum chat encontrado ou erro na API")
        return
    
    print(f"\n✅ Encontrados {len(chats)} chats:")
    print("=" * 80)
    
    groups = []
    channels = []
    others = []
    
    for chat in chats:
        chat_id = chat.get("id")
        chat_name = chat.get("name", "Sem nome")
        chat_type = chat.get("type", "desconhecido")
        
        print(f"📱 ID: {chat_id}")
        print(f"   Nome: {chat_name}")
        print(f"   Tipo: {chat_type}")
        print("-" * 40)
        
        # Classifica por tipo
        if "@g.us" in chat_id:
            groups.append({"id": chat_id, "name": chat_name})
        elif "@c.us" in chat_id and "120363025" in chat_id:
            channels.append({"id": chat_id, "name": chat_name})
        else:
            others.append({"id": chat_id, "name": chat_name})
    
    # Mostra resumo
    print("\n📊 RESUMO:")
    print("=" * 80)
    
    if groups:
        print("\n👥 GRUPOS:")
        for group in groups:
            print(f"   {group['name']}: {group['id']}")
    
    if channels:
        print("\n📢 CANAIS:")
        for channel in channels:
            print(f"   {channel['name']}: {channel['id']}")
    
    if others:
        print("\n📱 OUTROS CHATS:")
        for other in others:
            print(f"   {other['name']}: {other['id']}")
    
    # Gera configuração para .env
    print("\n📝 CONFIGURAÇÃO PARA .env:")
    print("=" * 80)
    
    if test_mode:
        print("🔬 CONFIGURAÇÃO PARA MODO TESTE:")
        if groups:
            group_ids = ",".join([group['id'] for group in groups])
            print(f"WHATSAPP_GROUPS_TESTE={group_ids}")
        
        if channels:
            channel_ids = ",".join([channel['id'] for channel in channels])
            print(f"WHATSAPP_CHANNELS_TESTE={channel_ids}")
    else:
        print("🚀 CONFIGURAÇÃO PARA MODO PRODUÇÃO:")
        if groups:
            group_ids = ",".join([group['id'] for group in groups])
            print(f"WHATSAPP_GROUPS={group_ids}")
        
        if channels:
            channel_ids = ",".join([channel['id'] for channel in channels])
            print(f"WHATSAPP_CHANNELS={channel_ids}")
    
    if not groups and not channels:
        print("⚠️ Nenhum grupo ou canal encontrado")
        print("Certifique-se de que o WhatsApp está conectado e tem grupos/canais")

if __name__ == "__main__":
    main() 