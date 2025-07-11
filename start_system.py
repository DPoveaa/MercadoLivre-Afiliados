#!/usr/bin/env python3
"""
Script de inicialização automática do sistema
Inicia o Open-WA e executa os scrapers
"""

import os
import sys
import time
import subprocess
import signal
from dotenv import load_dotenv

def log(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def check_dependencies():
    """Verifica se todas as dependências estão instaladas"""
    log("🔍 Verificando dependências...")
    
    # Verifica Node.js
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            log(f"✅ Node.js: {result.stdout.strip()}")
        else:
            log("❌ Node.js não encontrado")
            return False
    except FileNotFoundError:
        log("❌ Node.js não encontrado")
        return False
    
    # Verifica Python
    try:
        result = subprocess.run([sys.executable, '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            log(f"✅ Python: {result.stdout.strip()}")
        else:
            log("❌ Python não encontrado")
            return False
    except Exception as e:
        log(f"❌ Erro ao verificar Python: {e}")
        return False
    
    # Verifica dependências npm
    try:
        result = subprocess.run(['npm', 'list', '@open-wa/wa-automate'], capture_output=True, text=True)
        if result.returncode == 0:
            log("✅ @open-wa/wa-automate instalado")
        else:
            log("❌ @open-wa/wa-automate não instalado")
            return False
    except Exception as e:
        log(f"❌ Erro ao verificar dependências npm: {e}")
        return False
    
    return True

def start_openwa():
    """Inicia o Open-WA em background"""
    log("🚀 Iniciando Open-WA...")
    
    try:
        # Inicia o Open-WA em background
        process = subprocess.Popen(
            ['node', 'WhatsApp/start_openwa.js'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Aguarda um pouco para verificar se iniciou
        time.sleep(5)
        
        if process.poll() is None:
            log("✅ Open-WA iniciado com sucesso")
            return process
        else:
            stdout, stderr = process.communicate()
            log(f"❌ Erro ao iniciar Open-WA: {stderr}")
            return None
            
    except Exception as e:
        log(f"❌ Erro ao iniciar Open-WA: {e}")
        return None

def wait_for_whatsapp_auth():
    """Aguarda autenticação do WhatsApp"""
    log("⏳ Aguardando autenticação do WhatsApp...")
    
    from WhatsApp.wa_enviar_openwa import OpenWAAPI
    
    openwa = OpenWAAPI()
    max_attempts = 60  # 10 minutos
    attempt = 0
    
    while attempt < max_attempts:
        try:
            if openwa.healthcheck():
                log("✅ WhatsApp autenticado!")
                return True
            else:
                log(f"⏳ Tentativa {attempt + 1}/{max_attempts} - Aguardando QR Code...")
                time.sleep(10)
                attempt += 1
        except Exception as e:
            log(f"⚠️ Erro no healthcheck: {e}")
            time.sleep(10)
            attempt += 1
    
    log("❌ Timeout aguardando autenticação")
    return False

def run_scrapers():
    """Executa os scrapers"""
    log("🔄 Iniciando scrapers...")
    
    scrapers = [
        'scraper_kabum.py',
        'scraper_ml.py', 
        'scraper_amazon.py'
    ]
    
    processes = []
    
    for scraper in scrapers:
        if os.path.exists(scraper):
            log(f"📦 Iniciando {scraper}...")
            process = subprocess.Popen(
                [sys.executable, scraper],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            processes.append((scraper, process))
        else:
            log(f"⚠️ {scraper} não encontrado")
    
    return processes

def main():
    """Função principal"""
    log("🚀 Iniciando sistema de scrapers...")
    
    # Carrega variáveis de ambiente
    load_dotenv()
    
    # Verifica dependências
    if not check_dependencies():
        log("❌ Dependências não atendidas. Verifique a instalação.")
        return False
    
    # Inicia Open-WA
    openwa_process = start_openwa()
    if not openwa_process:
        log("❌ Falha ao iniciar Open-WA")
        return False
    
    # Aguarda autenticação
    if not wait_for_whatsapp_auth():
        log("❌ Falha na autenticação do WhatsApp")
        openwa_process.terminate()
        return False
    
    # Executa scrapers
    scraper_processes = run_scrapers()
    
    log("✅ Sistema iniciado com sucesso!")
    log(f"📊 Status:")
    log(f"   - Open-WA: ✅ Rodando (PID: {openwa_process.pid})")
    log(f"   - Scrapers ativos: {len(scraper_processes)}")
    
    # Mantém o processo rodando
    try:
        while True:
            time.sleep(60)
            
            # Verifica se Open-WA ainda está rodando
            if openwa_process.poll() is not None:
                log("❌ Open-WA parou inesperadamente")
                break
            
            # Verifica status dos scrapers
            for name, process in scraper_processes:
                if process.poll() is not None:
                    log(f"⚠️ {name} parou (código: {process.returncode})")
            
    except KeyboardInterrupt:
        log("🛑 Recebido sinal de parada...")
    
    # Limpeza
    log("🧹 Encerrando processos...")
    
    if openwa_process:
        openwa_process.terminate()
        openwa_process.wait()
        log("✅ Open-WA encerrado")
    
    for name, process in scraper_processes:
        if process.poll() is None:
            process.terminate()
            process.wait()
            log(f"✅ {name} encerrado")
    
    log("👋 Sistema encerrado")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 