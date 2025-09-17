import time
import os
import json
import platform
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import requests
import re
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import urlparse
import unicodedata

import schedule
import subprocess
from collections import deque
import sys
from WhatsApp.wa_green_api import send_whatsapp_message
import tempfile

load_dotenv()

TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

print("Test Mode:", TEST_MODE)

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID_TESTE") if TEST_MODE else os.getenv("TELEGRAM_GROUP_ID")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_TESTE") if TEST_MODE else os.getenv("TELEGRAM_CHAT_ID")

# WhatsApp Green-API
WHATSAPP_ENABLED = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
GREEN_API_INSTANCE_ID = os.getenv("GREEN_API_INSTANCE_ID")
GREEN_API_TOKEN = os.getenv("GREEN_API_TOKEN")

# Admins para notificação de desconexão WhatsApp
ADMIN_CHAT_IDS = os.getenv("ADMIN_CHAT_IDS", "").split(",") if os.getenv("ADMIN_CHAT_IDS") else []



products_per_category = int(os.getenv("TOP_N_OFFERS_TESTE"))if TEST_MODE else int(os.getenv("TOP_N_OFFERS_AMAZON"))

# Load cookies from environment variable
COOKIES_JSON = os.getenv('AMAZON_COOKIES')
if not COOKIES_JSON:
    raise ValueError("AMAZON_COOKIES environment variable not found in .env file")

try:
    COOKIES = json.loads(COOKIES_JSON)
except json.JSONDecodeError as e:
    raise ValueError(f"Invalid JSON in AMAZON_COOKIES: {e}")

FORCE_RUN_ON_START = os.getenv("FORCE_RUN_ON_START", "false").lower() == "true"

# Configurações gerais
SIMILARITY_THRESHOLD = 0.95  # Limiar de similaridade mais restritivo
MAX_HISTORY_SIZE = 150  # Mantém as últimas promoções

# Lista de categorias para capturar ofertas
AMAZON_CATEGORIES = [
    {
        "name": "Geral",
        "url": "https://www.amazon.com.br/deals?ref_=nav_cs_gb"
    },
    {
        "name": "Alimentos e Bebidas",
        "url": "https://www.amazon.com.br/deals?ref_=nav_cs_gb&bubble-id=deals-collection-grocery"
    },
    {
        "name": "Automotivo",
        "url": "https://www.amazon.com.br/deals?ref_=nav_cs_gb&bubble-id=deals-collection-automotive"
    },
    {
        "name": "Beleza",
        "url": "https://www.amazon.com.br/deals?ref_=nav_cs_gb&bubble-id=deals-collection-beauty"
    },
    {
        "name": "Brinquedos e Jogos",
        "url": "https://www.amazon.com.br/deals?ref_=nav_cs_gb&bubble-id=deals-collection-toys-and-games"
    },
    {
        "name": "Casa",
        "url": "https://www.amazon.com.br/deals?ref_=nav_cs_gb&bubble-id=deals-collection-home"
    },
    {
        "name": "Cozinha",
        "url": "https://www.amazon.com.br/deals?ref_=nav_cs_gb&bubble-id=deals-collection-kitchen"
    },
    {
        "name": "Eletrodomésticos",
        "url": "https://www.amazon.com.br/deals?ref_=nav_cs_gb&bubble-id=deals-collection-eletro"
    },
    {
        "name": "Eletrônicos",
        "url": "https://www.amazon.com.br/deals?ref_=nav_cs_gb&bubble-id=deals-collection-electronics"
    },
    {
        "name": "Ferramentas",
        "url": "https://www.amazon.com.br/deals?ref_=nav_cs_gb&bubble-id=deals-collection-tools"
    },
    {
        "name": "Computadores",
        "url": "https://www.amazon.com.br/deals?ref_=nav_cs_gb&bubble-id=deals-collection-computers"
    },
    {
        "name": "Video Games",
        "url": "https://www.amazon.com.br/deals?ref_=nav_cs_gb&bubble-id=deals-collection-video-games"
    }
]

USED_URLS_FILE = 'used_urls_amazon.json'

def load_used_urls():
    try:
        with open(USED_URLS_FILE, 'r') as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_used_urls(used_urls):
    with open(USED_URLS_FILE, 'w') as f:
        json.dump(list(used_urls), f)

def get_rotated_category_urls():
    used_urls = load_used_urls()
    all_urls = [cat['url'] for cat in AMAZON_CATEGORIES]
    if len(used_urls) >= len(all_urls):
        log("Todas as categorias já foram usadas. Reiniciando histórico...")
        used_urls.clear()
        save_used_urls(used_urls)
    available_urls = [url for url in all_urls if url not in used_urls]
    num_urls = min(2, len(available_urls))
    import random
    selected_urls = random.sample(available_urls, num_urls)
    used_urls.update(selected_urls)
    save_used_urls(used_urls)
    log(f"Categorias selecionadas: {len(selected_urls)} de {len(available_urls)} disponíveis")
    return selected_urls

def log(message):
    """Função para logging com timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def normalize_name(name):
    """Normaliza o nome removendo acentos, caixa e espaços extras."""
    if not isinstance(name, str):
        return ''
    name = name.lower().strip()
    name = unicodedata.normalize('NFKD', name)
    name = ''.join([c for c in name if not unicodedata.combining(c)])
    name = ' '.join(name.split())
    return name

def is_similar(a: str, b: str, thresh: float = SIMILARITY_THRESHOLD) -> bool:
    """Compare two strings and return True if they are similar above the threshold."""
    a_norm = normalize_name(a)
    b_norm = normalize_name(b)
    score = SequenceMatcher(None, a_norm, b_norm).ratio()
    return score >= thresh

def load_sent_products():
    if TEST_MODE:
        # Em modo de teste, não lê arquivo algum
        return []
    try:
        if os.path.exists('promocoes_amazon.json'):
            with open('promocoes_amazon.json', 'r', encoding='utf-8') as f:
                products = json.load(f)
                # Se atingiu o limite, remove os mais antigos
                if len(products) >= MAX_HISTORY_SIZE:
                    print(f"Limite de {MAX_HISTORY_SIZE} produtos atingido. Removendo os mais antigos...")
                    # Remove os produtos mais antigos mantendo apenas os MAX_HISTORY_SIZE mais recentes
                    products = products[-MAX_HISTORY_SIZE:]
                return products
        return []
    except Exception as e:
        print(f"Erro ao carregar produtos enviados: {e}")
        return []

def save_sent_products(products):
    if TEST_MODE:
        # Em modo de teste, não salva nada
        return
    try:
        # Se atingiu o limite, remove os mais antigos
        if len(products) > MAX_HISTORY_SIZE:
            print(f"Limite de {MAX_HISTORY_SIZE} produtos atingido. Removendo os mais antigos...")
            # Remove os produtos mais antigos mantendo apenas os MAX_HISTORY_SIZE mais recentes
            products = products[-MAX_HISTORY_SIZE:]
            
        with open('promocoes_amazon.json', 'w', encoding='utf-8') as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar produtos enviados: {e}")

def is_product_already_sent(product_name, sent_products):
    """Check if a product has already been sent by comparing names."""
    for sent_product in sent_products:
        if is_similar(product_name, sent_product):
            print(f"Produto '{product_name}' já está na lista, não será enviado novamente.")
            return True
    return False

def validate_product_data(product):
    """Valida se o produto tem todos os campos obrigatórios para envio."""
    required_fields = {
        'nome': 'Nome do produto',
        'valor_desconto': 'Valor com desconto',
        'link': 'Link do produto'
    }
    
    missing_fields = []
    
    # Verifica campos obrigatórios
    for field, description in required_fields.items():
        if not product.get(field) or str(product.get(field)).strip() == '':
            missing_fields.append(description)
    
    # Validações específicas
    if product.get('nome') and len(product.get('nome').strip()) < 3:
        missing_fields.append('Nome muito curto')
    
    if product.get('valor_desconto') and not re.search(r'R\$\s*\d+', product.get('valor_desconto')):
        missing_fields.append('Valor com desconto inválido')
    
    if product.get('link') and not product.get('link').startswith(('http://', 'https://')):
        missing_fields.append('Link inválido')
    
    # Verifica se tem imagem válida
    if not product.get('imagem') or not is_valid_image_url(product.get('imagem')):
        missing_fields.append('Imagem válida')
    
    if missing_fields:
        print(f"❌ Produto rejeitado - Campos obrigatórios ausentes: {', '.join(missing_fields)}")
        print(f"   Produto: {product.get('nome', 'Sem nome')[:50]}...")
        return False
    
    print(f"✅ Produto validado com sucesso: {product.get('nome', 'Sem nome')[:50]}...")
    return True

def get_deals_with_discounts(driver, category_name):
    """Coleta descontos e links dos produtos de uma categoria específica."""
    log(f"Coletando ofertas da categoria: {category_name}")
    
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="product-card"]'))
        )
        product_cards = driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="product-card"]')
        
        log(f"Encontrados {len(product_cards)} produtos na categoria {category_name}")
        
        deals = []
        for card in product_cards:
            try:
                # Extrai o desconto
                discount_element = card.find_element(
                    By.CSS_SELECTOR, 
                    'div.style_filledRoundedBadgeLabel__Vo-4g span.a-size-mini'
                )
                discount_text = discount_element.text.strip()
                
                # Tenta extrair o valor numérico do desconto
                try:
                    # Remove caracteres não numéricos e converte para inteiro
                    discount = int(''.join(filter(str.isdigit, discount_text)))
                except ValueError:
                    # Se não conseguir converter, verifica se é "Oferta" ou similar
                    if "Oferta" in discount_text or "Promoção" in discount_text:
                        discount = 5  # Define um desconto padrão para ofertas
                    else:
                        continue  # Pula este produto se não conseguir determinar o desconto
                
                # Só adiciona se o desconto for maior que 5%
                if discount > 5:
                    # Extrai o link
                    link_element = card.find_element(
                        By.CSS_SELECTOR, 
                        'a[data-testid="product-card-link"]'
                    )
                    link = link_element.get_attribute('href')
                    
                    deals.append({
                        'discount': discount, 
                        'link': link,
                        'category': category_name
                    })
                
            except Exception as e:
                print(f"[Erro] Não foi possível extrair dados do produto na categoria {category_name}: {e}")
        
        log(f"Coletados {len(deals)} produtos com desconto > 5% na categoria {category_name}")
        return deals
        
    except Exception as e:
        log(f"Erro ao coletar ofertas da categoria {category_name}: {e}")
        return []

def get_alternative_image(driver, product_name, product_url):
    """Tenta obter uma imagem alternativa do produto."""
    try:
        # Navega para a URL do produto
        driver.get(product_url)
        time.sleep(3)  # Aumenta o tempo de espera para garantir carregamento

        # Lista de seletores CSS para tentar encontrar a imagem (ordenados por prioridade)
        selectors = [
            "#landingImage[data-old-hires]",  # Imagem principal com alta resolução
            "img[data-old-hires]",  # Qualquer imagem com alta resolução
            "#landingImage",  # Imagem principal
            "#imgTagWrapperId img",  # Imagem dentro do wrapper
            "#main-image-container img",  # Qualquer imagem no container principal
            ".imgTagWrapper img",  # Imagens nos wrappers
            "#imageBlock img",  # Imagens no bloco de imagens
            ".a-dynamic-image",  # Imagens dinâmicas
            ".a-stretch-vertical",  # Imagens esticadas verticalmente
            ".a-stretch-horizontal",  # Imagens esticadas horizontalmente
            "img[data-a-dynamic-image]"  # Imagens com dados dinâmicos
        ]

        # Tenta cada seletor
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    # Tenta obter a URL da imagem de diferentes atributos
                    src = element.get_attribute('src')
                    data_old_hires = element.get_attribute('data-old-hires')
                    data_dynamic_image = element.get_attribute('data-a-dynamic-image')
                    
                    # Prioriza imagens de alta resolução (data-old-hires)
                    if data_old_hires and is_valid_image_url(data_old_hires):
                        print(f"✅ Imagem encontrada via data-old-hires: {data_old_hires}")
                        return data_old_hires
                    
                    # Tenta a URL normal se for válida
                    if src and is_valid_image_url(src):
                        print(f"✅ Imagem encontrada via src: {src}")
                        return src
                    
                    # Tenta extrair do atributo data-a-dynamic-image
                    if data_dynamic_image:
                        try:
                            # O atributo data-a-dynamic-image é um JSON com URLs e dimensões
                            dynamic_images = json.loads(data_dynamic_image)
                            if dynamic_images:
                                # Pega a URL com a maior resolução
                                largest_url = max(dynamic_images.items(), key=lambda x: x[1][0])[0]
                                if is_valid_image_url(largest_url):
                                    print(f"✅ Imagem encontrada via data-a-dynamic-image: {largest_url}")
                                    return largest_url
                        except Exception as e:
                            print(f"Erro ao processar data-a-dynamic-image: {e}")
                            continue

            except Exception as e:
                print(f"Erro ao tentar seletor {selector}: {e}")
                continue

        # Se não encontrou nenhuma imagem válida, tenta extrair do HTML com regex mais específico
        try:
            html = driver.page_source
            # Procura por URLs de imagem no HTML com padrões mais específicos
            img_patterns = [
                r'https://m\.media-amazon\.com/images/I/[^"\']+\._AC_SL\d+_\.jpg',  # Padrão SL (high-res)
                r'https://m\.media-amazon\.com/images/I/[^"\']+\._AC_SX\d+_\.jpg',  # Padrão SX
                r'https://m\.media-amazon\.com/images/I/[^"\']+\._AC_SY\d+_\.jpg',  # Padrão SY
                r'https://m\.media-amazon\.com/images/I/[^"\']+\.jpg'  # Padrão geral
            ]
            
            for pattern in img_patterns:
                img_urls = re.findall(pattern, html)
                for url in img_urls:
                    if is_valid_image_url(url):
                        print(f"✅ Imagem encontrada via regex: {url}")
                        return url
        except Exception as e:
            print(f"Erro ao extrair URLs do HTML: {e}")

        print(f"❌ Nenhuma imagem válida encontrada para {product_name}")
        return None
    except Exception as e:
        print(f"Erro ao buscar imagem alternativa para {product_name}: {e}")
        return None

def is_valid_image_url(url):
    """Verifica se a URL da imagem é válida e acessível."""
    try:
        # Verifica se é uma URL válida
        parsed = urlparse(url)
        if not all([parsed.scheme, parsed.netloc]):
            return False

        # Verifica se é uma URL da Amazon
        if 'media-amazon.com' not in parsed.netloc:
            return False

        # Faz uma requisição HEAD para verificar o tipo de conteúdo
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.head(url, headers=headers, timeout=5)
        content_type = response.headers.get('content-type', '')
        
        # Verifica se é uma imagem
        if not content_type.startswith('image/'):
            return False

        # Verifica o tamanho da imagem
        content_length = int(response.headers.get('content-length', 0))
        if content_length > 10 * 1024 * 1024:  # 10MB limite do Telegram
            return False

        return True
    except Exception as e:
        print(f"Erro ao validar imagem {url}: {e}")
        return False

def send_telegram_message(products, driver, sent_products):
    """Envia os resultados formatados para o Telegram com imagem. Não manipula mais a lista de enviados."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_GROUP_ID:
        print("Variáveis de ambiente do Telegram não configuradas!")
        return []

    # Verifica conexão do WhatsApp se habilitado
    whatsapp_connected = True
    if WHATSAPP_ENABLED:
        try:
            from WhatsApp.wa_green_api import GreenAPI
            whatsapp_api = GreenAPI(GREEN_API_INSTANCE_ID, GREEN_API_TOKEN)
            whatsapp_connected = whatsapp_api.verify_and_notify_connection(ADMIN_CHAT_IDS)
            
            if whatsapp_connected:
                print("✅ WhatsApp conectado e funcionando")
            else:
                print("⚠️ WhatsApp desconectado - apenas Telegram será usado")
        except Exception as e:
            print(f"Erro ao verificar WhatsApp: {str(e)}")
            whatsapp_connected = False

    new_sent_products = []

    for product in products:
        try:
            # Validação rigorosa de todos os campos obrigatórios
            if not validate_product_data(product):
                print(f"❌ Produto rejeitado por validação: {product.get('nome', 'Sem nome')[:50]}...")
                continue

            # Check if product was already sent
            if is_product_already_sent(product['nome'], sent_products):
                print(f"⏭️ Produto já enviado anteriormente: {product['nome'][:50]}...")
                continue

            # Monta mensagem no padrão solicitado, com uma linha em branco entre cada campo
            message_lines = []
            message_lines.append("🔵 Amazon")
            message_lines.append("")
            message_lines.append(f"🏷️ {product['nome']}")
            message_lines.append("")

            if product.get('desconto_percentual'):
                message_lines.append(f"📉 Desconto de {product['desconto_percentual']}% OFF")
                message_lines.append("")

            if product.get('avaliacao'):
                message_lines.append(f"⭐ {product['avaliacao']}")
                message_lines.append("")

            if product.get('valor_original'):
                message_lines.append(f"💸 De: {product['valor_original']}")
                message_lines.append("")

            message_lines.append(f"💥 Por apenas: {product['valor_desconto']}")
            message_lines.append("")

            # Parcelamento
            if product.get('parcelamento'):
                try:
                    message_lines.append("💳 Parcelamentos:")
                    padrao1 = re.search(r'(\d+)x de R\$\s*([\d,]+)\s*(.*)', product['parcelamento'])
                    padrao2 = re.search(r'(\d+)x\s*(.*)', product['parcelamento'])
                    padrao3 = re.search(r'.*(\d+)x.*sem juros', product['parcelamento'])
                    if padrao1:
                        qtd_parcelas = padrao1.group(1)
                        valor_parcela = f"R$ {padrao1.group(2)}"
                        status_juros = padrao1.group(3).replace("com acréscimo", "com juros")
                        message_lines.append(f"- Em até {qtd_parcelas}x {valor_parcela} {status_juros}".strip())
                    elif padrao2:
                        qtd_parcelas = padrao2.group(1)
                        status_juros = padrao2.group(2).replace("com acréscimo", "com juros")
                        message_lines.append(f"- Em até {qtd_parcelas}x {status_juros}".strip())
                    elif padrao3:
                        qtd_parcelas = padrao3.group(1)
                        message_lines.append(f"- Em até {qtd_parcelas}x sem juros")
                    else:
                        message_lines.append("- Parcelamento disponível (ver detalhes)")
                    message_lines.append("")
                except Exception as e:
                    print(f"Erro ao processar parcelamento: {str(e)}")
                    message_lines.append("- Condições de parcelamento no site")
                    message_lines.append("")

            message_lines.append("🛒 Garanta agora:")
            message_lines.append(f"🔗 {product['link']}")

            # Junta tudo, removendo quebras de linha duplicadas
            message = "\n".join(message_lines)
            message = re.sub(r'\n{3,}', '\n\n', message).strip()

            # Tenta enviar com imagem primeiro
            image_url = None
            if product.get('imagem'):
                if is_valid_image_url(product['imagem']):
                    image_url = product['imagem']
                else:
                    image_url = get_alternative_image(driver, product['nome'], product['link'])
            
            telegram_success = False
            whatsapp_success = False
            
            # Envia para Telegram
            if image_url:
                try:
                    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
                    payload = {
                        'chat_id': TELEGRAM_GROUP_ID,
                        'photo': image_url,
                        'caption': message,
                        'parse_mode': 'Markdown'
                    }
                    response = requests.post(url, data=payload, timeout=10)
                    response.raise_for_status()
                    telegram_success = True
                    print(f"✅ Mensagem enviada para Telegram com imagem: {product['nome'][:50]}...")
                except Exception as e:
                    print(f"❌ Erro ao enviar para Telegram com imagem, tentando sem imagem: {e}")
            
            # Se não conseguiu com imagem ou não tem imagem, tenta sem
            if not telegram_success:
                try:
                    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                    payload = {
                        'chat_id': TELEGRAM_GROUP_ID,
                        'text': message,
                        'parse_mode': 'Markdown'
                    }
                    response = requests.post(url, data=payload)
                    response.raise_for_status()
                    telegram_success = True
                    print(f"✅ Mensagem enviada para Telegram sem imagem: {product['nome'][:50]}...")
                except Exception as e:
                    print(f"❌ Falha ao enviar mensagem para Telegram: {e}")
            
            # Envia para WhatsApp se habilitado e conectado
            if WHATSAPP_ENABLED and whatsapp_connected:
                try:
                    whatsapp_success = send_whatsapp_message(
                        message=message,
                        image_url=image_url,
                        instance_id=GREEN_API_INSTANCE_ID,
                        api_token=GREEN_API_TOKEN
                    )
                    if whatsapp_success:
                        print(f"✅ Mensagem enviada para WhatsApp: {product['nome'][:50]}...")
                    else:
                        print(f"❌ Falha ao enviar para WhatsApp: {product['nome'][:50]}...")
                except Exception as e:
                    print(f"❌ Erro ao enviar para WhatsApp: {str(e)}")
                    whatsapp_success = False
            elif WHATSAPP_ENABLED and not whatsapp_connected:
                print("WhatsApp desabilitado - apenas Telegram será usado")
                whatsapp_success = False
            
            # Salva no histórico se pelo menos um dos envios foi bem-sucedido
            if telegram_success or (WHATSAPP_ENABLED and whatsapp_success):
                new_sent_products.append(product['nome'])
            else:
                print(f"❌ Falha total ao enviar produto: {product['nome']}")
            
            time.sleep(3)  # Delay entre mensagens
            
        except Exception as e:
            print(f"❌ Erro crítico ao processar produto {product.get('nome', 'Sem nome')}: {str(e)}")

    print(f"📤 Total de produtos enviados nesta execução: {len(new_sent_products)}")
    return new_sent_products



# Função para montar mensagem no formato do Telegram
def format_amazon_message(product):
    message_lines = []
    message_lines.append("🔵 Amazon")
    message_lines.append("")
    message_lines.append(f"🏷️ {product['nome']}")
    message_lines.append("")
    if product.get('desconto_percentual'):
        message_lines.append(f"📉 Desconto de {product['desconto_percentual']}% OFF")
        message_lines.append("")
    if product.get('avaliacao'):
        message_lines.append(f"⭐ {product['avaliacao']}")
        message_lines.append("")
    if product.get('valor_original'):
        message_lines.append(f"💸 De: {product['valor_original']}")
        message_lines.append("")
    message_lines.append(f"💥 Por apenas: {product['valor_desconto']}")
    message_lines.append("")
    if product.get('parcelamento'):
        try:
            message_lines.append("💳 Parcelamentos:")
            padrao1 = re.search(r'(\d+)x de R\$\s*([\d,]+)\s*(.*)', product['parcelamento'])
            padrao2 = re.search(r'(\d+)x\s*(.*)', product['parcelamento'])
            padrao3 = re.search(r'.*(\d+)x.*sem juros', product['parcelamento'])
            if padrao1:
                qtd_parcelas = padrao1.group(1)
                valor_parcela = f"R$ {padrao1.group(2)}"
                status_juros = padrao1.group(3).replace("com acréscimo", "com juros")
                message_lines.append(f"- Em até {qtd_parcelas}x {valor_parcela} {status_juros}".strip())
            elif padrao2:
                qtd_parcelas = padrao2.group(1)
                status_juros = padrao2.group(2).replace("com acréscimo", "com juros")
                message_lines.append(f"- Em até {qtd_parcelas}x {status_juros}".strip())
            elif padrao3:
                qtd_parcelas = padrao3.group(1)
                message_lines.append(f"- Em até {qtd_parcelas}x sem juros")
            else:
                message_lines.append("- Parcelamento disponível (ver detalhes)")
            message_lines.append("")
        except Exception as e:
            message_lines.append("- Condições de parcelamento no site")
            message_lines.append("")
    message_lines.append("🛒 Garanta agora:")
    message_lines.append(f"🔗 {product['link']}")
    message = "\n".join(message_lines)
    message = re.sub(r'\n{3,}', '\n\n', message).strip()
    return message

def format_price(price_str):
    """Formata o preço adicionando pontos para separar milhares e removendo espaços extras."""
    try:
        # Remove R$, espaços e converte vírgula para ponto
        price_str = price_str.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
        # Converte para float
        price_float = float(price_str)
        # Formata com 2 casas decimais e adiciona pontos para milhares
        formatted = f"R${price_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return formatted
    except Exception as e:
        print(f"Erro ao formatar preço {price_str}: {e}")
        return price_str

def generate_affiliate_links(driver, product_links):
    """Gera links de afiliados e coleta dados do produto"""
    product_data = []

    for url_info in product_links:
        url = url_info['link']
        category = url_info.get('category', 'Geral')
        
        product_info = {
            'link': None,
            'nome': None,
            'valor_desconto': None,
            'valor_original': None,
            'desconto_percentual': None,
            'avaliacao': None,
            'parcelamento': None,
            'imagem': None,
            'categoria': category
        }

        try:
            if not url.startswith(("http://", "https://")):
                print(f"URL inválida: {url}")
                continue

            # Navega para a página
            driver.get(url)
            
            # 1. COLETA NOME (OBRIGATÓRIO)
            try:
                product_info['nome'] = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.ID, "productTitle"))
                ).text.strip()
            except Exception as e:
                print(f"Erro no nome: {str(e)}")
                continue  # Aborta se não encontrar nome

            # 2. COLETA PREÇO COM DESCONTO (OBRIGATÓRIO)
            try:
                # Primeiro tenta o formato padrão
                try:
                    price_block = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "corePriceDisplay_desktop_feature_div"))
                    )
                    whole = price_block.find_element(By.CSS_SELECTOR, "span.a-price-whole").text.strip()
                    fraction = price_block.find_element(By.CSS_SELECTOR, "span.a-price-fraction").text.strip()
                    price_str = f"R${whole},{fraction}"
                    product_info['valor_desconto'] = format_price(price_str)
                except:
                    # Se falhar, tenta o formato de assinatura
                    try:
                        price_block = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.ID, "subscriptionPrice"))
                        )
                        whole = price_block.find_element(By.CSS_SELECTOR, "span.a-price-whole").text.strip()
                        fraction = price_block.find_element(By.CSS_SELECTOR, "span.a-price-fraction").text.strip()
                        price_str = f"R${whole},{fraction}"
                        product_info['valor_desconto'] = format_price(price_str)
                    except:
                        # Se ambos falharem, tenta pegar o preço do elemento aok-offscreen
                        try:
                            price_text = driver.find_element(By.CSS_SELECTOR, "span.aok-offscreen").text
                            price_match = re.search(r'R\$\s*(\d+),(\d+)', price_text)
                            if price_match:
                                whole = price_match.group(1)
                                fraction = price_match.group(2)
                                price_str = f"R${whole},{fraction}"
                                product_info['valor_desconto'] = format_price(price_str)
                            else:
                                raise Exception("Formato de preço não reconhecido")
                        except:
                            raise Exception("Não foi possível encontrar o preço do produto")
            except Exception as e:
                print(f"Erro no preço: {str(e)}")
                continue  # Aborta se não encontrar preço

            # 3. COLETA LINK AFILIADO (OBRIGATÓRIO)
            try:
                driver.execute_script("window.scrollTo(0, 0);")
                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button#amzn-ss-get-link-button"))
                ).click()

                textarea = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "#amzn-ss-text-shortlink-textarea"))
                )
                
                WebDriverWait(driver, 5).until(
                    lambda d: "amzn.to/" in textarea.get_attribute("value"))
                
                product_info['link'] = textarea.get_attribute("value").strip()
            except Exception as e:
                print(f"Erro no link afiliado: {str(e)}")
                continue  # Aborta se não gerar link

            # 4. COLETA DEMAIS INFORMAÇÕES (OPCIONAIS)
            try:
                # Preço original
                original = price_block.find_element(
                    By.CSS_SELECTOR, "span.basisPrice span.a-price span.a-offscreen"
                ).get_attribute("textContent").strip()
                product_info['valor_original'] = format_price(original)
            except:
                try:
                    # Tenta outro seletor alternativo para o preço original
                    original = price_block.find_element(
                        By.CSS_SELECTOR, "span.a-size-small.a-color-secondary span.a-price span.a-offscreen"
                    ).get_attribute("textContent").strip()
                    product_info['valor_original'] = format_price(original)
                except:
                    product_info['valor_original'] = product_info['valor_desconto']

            try:
                # Percentual de desconto
                discount = price_block.find_element(
                    By.CSS_SELECTOR, ".savingPriceOverride"
                ).text.strip()
                product_info['desconto_percentual'] = discount.replace('-', '').replace('%', '')
            except:
                try:
                    # Cálculo manual do desconto
                    if product_info['valor_original'] and product_info['valor_desconto']:
                        # Remove R$ e converte para float
                        original = float(product_info['valor_original'].replace('R$', '')
                                                                    .replace('.', '')
                                                                    .replace(',', '.').strip())
                        desconto = float(product_info['valor_desconto'].replace('R$', '')
                                                                    .replace('.', '')
                                                                    .replace(',', '.').strip())
                        
                        # Calcula porcentagem
                        percentual = ((original - desconto) / original) * 100
                        product_info['desconto_percentual'] = str(round(percentual, 1))
                        
                except Exception as e:
                    print(f"Erro ao calcular desconto: {str(e)}")
                    product_info['desconto_percentual'] = None
            try:
                # Avaliação
                rating_element = driver.find_element(
                    By.CSS_SELECTOR, "#averageCustomerReviews .a-icon-alt"
                )
                rating = rating_element.get_attribute("textContent").split()[0].replace(',', '.')
                
                # Quantidade de avaliações
                review_count_element = driver.find_element(
                    By.CSS_SELECTOR, "#acrCustomerReviewText"
                )
                review_count = review_count_element.text.strip('()').replace('.', '')
                
                # Formata a avaliação sem pontos
                product_info['avaliacao'] = f"{rating} ({review_count} avaliações)"
            except:
                pass
            try:
                parcelamento_element = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#installmentCalculator_feature_div span.best-offer-name"))
                )
                raw_text = parcelamento_element.text.strip()
                
                # Nova limpeza do texto
                clean_text = raw_text.split('Ver')[0]  # Remove tudo após 'Ver'
                clean_text = clean_text.replace('R$&nbsp;', '').replace('  ', ' ').strip()
                
                product_info['parcelamento'] = clean_text
            except:
                product_info['parcelamento'] = None
            try:
                # Imagem - tenta múltiplos seletores para garantir captura
                image_selectors = [
                    "#landingImage[data-old-hires]",  # Prioriza alta resolução
                    "img[data-old-hires]",
                    "#landingImage",
                    "#main-image-container img",
                    "#imgTagWrapperId img",
                    ".imgTagWrapper img",
                    "#imageBlock img"
                ]
                
                image_found = False
                for selector in image_selectors:
                    try:
                        image_element = WebDriverWait(driver, 3).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                        
                        # Tenta obter a melhor URL da imagem
                        data_old_hires = image_element.get_attribute('data-old-hires')
                        src = image_element.get_attribute('src')
                        
                        if data_old_hires and is_valid_image_url(data_old_hires):
                            product_info['imagem'] = data_old_hires
                            print(f"✅ Imagem capturada (alta res): {data_old_hires}")
                            image_found = True
                            break
                        elif src and is_valid_image_url(src):
                            product_info['imagem'] = src
                            print(f"✅ Imagem capturada (normal): {src}")
                            image_found = True
                            break
                    except:
                        continue
                
                # Se não encontrou imagem válida, tenta busca alternativa
                if not image_found:
                    print(f"⚠️ Imagem não encontrada com seletores padrão, tentando busca alternativa...")
                    alternative_image = get_alternative_image(driver, product_info['nome'], url)
                    if alternative_image:
                        product_info['imagem'] = alternative_image
                        print(f"✅ Imagem alternativa encontrada: {alternative_image}")
                    else:
                        print(f"❌ Nenhuma imagem válida encontrada para {product_info['nome']}")
                        # Se não tem imagem válida, rejeita o produto
                        continue
                        
            except Exception as e:
                print(f"❌ Erro ao capturar imagem: {e}")
                # Se não conseguiu capturar imagem, rejeita o produto
                continue

            product_data.append(product_info)
            time.sleep(2)

        except Exception as e:
            print(f"Erro crítico: {str(e)}")
            driver.save_screenshot(f"erro_critico_{url.split('/')[-1]}.png")

    return product_data

def amazon_scraper(driver):
    """Scraper principal que coleta ofertas de todas as categorias"""
    try:
        driver.get("https://www.amazon.com.br")
        driver.delete_all_cookies()  # Limpar cookies existentes

        for cookie in COOKIES:
            try:
                # Converte valores booleanos de string para bool
                secure = cookie.get('secure', False)
                if isinstance(secure, str):
                    secure = secure.lower() == 'true'

                http_only = cookie.get('httpOnly', False)
                if isinstance(http_only, str):
                    http_only = http_only.lower() == 'true'

                driver.add_cookie({
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'domain': cookie['domain'],
                    'path': cookie['path'],
                    'secure': secure,
                    'httpOnly': http_only
                })
            except Exception as e:
                print(f"Erro ao adicionar cookie {cookie.get('name')}: {str(e)}")

        all_deals = []
        deals_by_category = {}
        
        # --- USAR APENAS 2 CATEGORIAS ROTACIONADAS POR VEZ ---
        selected_category_urls = get_rotated_category_urls()
        selected_categories = [cat for cat in AMAZON_CATEGORIES if cat['url'] in selected_category_urls]
        for category in selected_categories:
            try:
                log(f"Processando categoria: {category['name']}")
                driver.get(category['url'])
                
                # Aguarda a página carregar
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.ID, "nav-link-accountList"))
                )
                
                # Coleta ofertas desta categoria
                category_deals = get_deals_with_discounts(driver, category['name'])
                
                # Armazena ofertas por categoria
                deals_by_category[category['name']] = category_deals
                all_deals.extend(category_deals)
                
                # Delay entre categorias para evitar sobrecarga
                time.sleep(3)
                
            except Exception as e:
                log(f"Erro ao processar categoria {category['name']}: {e}")
                continue
        
        log(f"Pegando até {products_per_category} produtos por categoria")
        
        selected_deals = []
        
        # Seleciona os melhores produtos de cada categoria
        for category_name, category_deals in deals_by_category.items():
            if not category_deals:
                continue
                
            # Ordena ofertas desta categoria por desconto
            sorted_category_deals = sorted(category_deals, key=lambda x: x['discount'], reverse=True)
            
            # Pega os melhores produtos desta categoria
            best_from_category = sorted_category_deals[:products_per_category]
            selected_deals.extend(best_from_category)
            
            log(f"Categoria '{category_name}': {len(best_from_category)} produtos selecionados (descontos: {[d['discount'] for d in best_from_category]})")
        
        log(f"Total de ofertas coletadas de todas as categorias: {len(all_deals)}")
        log(f"Total de produtos selecionados para envio: {len(selected_deals)}")
        
        # Log detalhado por categoria
        category_counts = {}
        for deal in selected_deals:
            cat = deal['category']
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        log("Distribuição final por categoria:")
        for cat, count in category_counts.items():
            log(f"  - {cat}: {count} produtos")
        
        return selected_deals

    except Exception as e:
        print(f"[Erro no scraper] {e}")
        return []

from time import sleep



def run_scraper():
    """Função principal que executa o scraper."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando execução do scraper...")

    # Definir diretório temporário customizado para Chrome/Chromedriver
    custom_tmp = tempfile.mkdtemp(prefix='chrome_tmp_')
    os.environ['TMPDIR'] = custom_tmp
    os.environ['TEMP'] = custom_tmp
    os.environ['TMP'] = custom_tmp

    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--enable-unsafe-swiftshader")
    # Adicionar diretórios temporários customizados
    chrome_options.add_argument(f'--user-data-dir={custom_tmp}/user_data')
    chrome_options.add_argument(f'--disk-cache-dir={custom_tmp}/cache')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)



    try:
        print("🔄 Iniciando coleta de links de ofertas de todas as categorias...")
        deal_links = amazon_scraper(driver)
        print(f"✅ Links coletados: {len(deal_links)}")

        if not deal_links:
            print("❌ Nenhum link de oferta encontrado")
            return

        print("🔄 Gerando links de afiliados e coletando dados dos produtos...")
        products_data = generate_affiliate_links(driver, deal_links)
        print(f"✅ Dados de {len(products_data)} produtos coletados com sucesso")

        if not products_data:
            print("❌ Nenhum produto foi processado com sucesso")
            return

        sent_products = load_sent_products()
        novos_enviados = []
        produtos_nao_enviados = []

        print(f"📊 Processando {len(products_data)} produtos para envio...")
        
        for i, produto in enumerate(products_data, 1):
            print(f"📦 Processando produto {i}/{len(products_data)}: {produto.get('nome', 'Sem nome')[:50]}...")
            
            # Validação rigorosa antes de processar
            if not validate_product_data(produto):
                print(f"❌ Produto rejeitado por validação: {produto.get('nome', 'Sem nome')[:50]}...")
                produtos_nao_enviados.append(produto.get('nome', 'Sem nome'))
                continue
            
            # Checa se já foi enviado
            if is_product_already_sent(produto['nome'], sent_products):
                print(f"⏭️ Produto já enviado anteriormente: {produto['nome'][:50]}...")
                continue

            try:
                # Tenta enviar o produto
                enviado_telegram = send_telegram_message([produto], driver, sent_products)
                
                if enviado_telegram:
                    for nome_produto in enviado_telegram:
                        sent_products.append(nome_produto)
                        novos_enviados.append(nome_produto)
                        print(f"✅ Produto enviado com sucesso: {nome_produto[:50]}...")
                    
                    # Remove o mais antigo se passar do limite
                    if len(sent_products) > MAX_HISTORY_SIZE:
                        sent_products = sent_products[-MAX_HISTORY_SIZE:]
                else:
                    produtos_nao_enviados.append(produto['nome'])
                    print(f"❌ Falha ao enviar produto: {produto['nome'][:50]}...")
                    


            except Exception as e:
                produtos_nao_enviados.append(produto['nome'])
                print(f"❌ Erro ao processar produto {produto.get('nome', 'Sem nome')}: {str(e)}")
            
            sleep(1)  # Delay entre produtos

        # Resumo final
        print(f"\n📈 RESUMO DA EXECUÇÃO:")
        print(f"   • Total de produtos processados: {len(products_data)}")
        print(f"   • Produtos enviados com sucesso: {len(novos_enviados)}")
        print(f"   • Produtos não enviados: {len(produtos_nao_enviados)}")
        
        if novos_enviados:
            print(f"   • Produtos enviados: {[nome[:30] + '...' if len(nome) > 30 else nome for nome in novos_enviados]}")
        
        if produtos_nao_enviados:
            print(f"   • Produtos não enviados: {[nome[:30] + '...' if len(nome) > 30 else nome for nome in produtos_nao_enviados]}")

        if not TEST_MODE and novos_enviados:
            save_sent_products(sent_products)
            print(f"✅ Produtos salvos no histórico: {len(novos_enviados)}")

        if TEST_MODE:
            print("⚠️ Modo teste ativado - Produtos não foram realmente salvos")

    except Exception as e:
        print(f"❌ Erro durante a execução do scraper: {e}")
    finally:
        driver.quit()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Execução finalizada.")

def schedule_scraper():
    """Configura e inicia o agendamento do scraper."""
    print("Iniciando agendamento do scraper...")
    
    if TEST_MODE:
        print("Modo de teste ativado - Executando imediatamente e a cada hora")
        run_scraper()
        schedule.every(1).hours.do(run_scraper)
    else:
                # Executa imediatamente se forçado
        if FORCE_RUN_ON_START:
            print("Execução imediata forçada pelo .env")
            run_scraper()
        print("Modo normal - Agendando para horarios com final 00")
        # Agenda para executar a cada hora, começando às 12:00
        schedule.every().day.at("12:00").do(run_scraper)
        schedule.every().day.at("13:00").do(run_scraper)
        schedule.every().day.at("14:00").do(run_scraper)
        schedule.every().day.at("15:00").do(run_scraper)
        schedule.every().day.at("16:00").do(run_scraper)
        schedule.every().day.at("17:00").do(run_scraper)
        schedule.every().day.at("18:00").do(run_scraper)
        schedule.every().day.at("19:00").do(run_scraper)
        schedule.every().day.at("20:00").do(run_scraper)
        schedule.every().day.at("21:00").do(run_scraper)
        schedule.every().day.at("22:00").do(run_scraper)
        schedule.every().day.at("23:00").do(run_scraper)
        schedule.every().day.at("00:00").do(run_scraper)
        schedule.every().day.at("01:00").do(run_scraper)
        schedule.every().day.at("02:00").do(run_scraper)
        schedule.every().day.at("03:00").do(run_scraper)
        schedule.every().day.at("04:00").do(run_scraper)
        schedule.every().day.at("05:00").do(run_scraper)
        schedule.every().day.at("06:00").do(run_scraper)
        schedule.every().day.at("07:00").do(run_scraper)
        schedule.every().day.at("08:00").do(run_scraper)
        schedule.every().day.at("09:00").do(run_scraper)
        schedule.every().day.at("10:00").do(run_scraper)
        schedule.every().day.at("11:00").do(run_scraper)
    
    # Mantém o script rodando
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Verifica a cada minuto se há tarefas pendentes
        except KeyboardInterrupt:
            print("\nEncerrando o scraper...")
            break
        except Exception as e:
            print(f"Erro no agendamento: {e}")
            time.sleep(60)  # Espera 1 minuto antes de tentar novamente

if __name__ == "__main__":
    schedule_scraper()  
