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

load_dotenv()

TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

print("Test Mode:", TEST_MODE)

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID_TESTE") if TEST_MODE else os.getenv("TELEGRAM_GROUP_ID")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_TESTE") if TEST_MODE else os.getenv("TELEGRAM_CHAT_ID")

# WhatsApp
WHATSAPP_GROUP_NAME = os.getenv("WHATSAPP_GROUP_NAME_TESTE") if TEST_MODE else os.getenv("WHATSAPP_GROUP_NAME")
WHATSAPP_HISTORY_FILE = 'promocoes_amazon_whatsapp.json'
MAX_HISTORY_SIZE_WPP = 150

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
    """Load the list of previously sent products from JSON file."""
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
    """Save the list of sent products to JSON file."""
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
        time.sleep(2)  # Pequena pausa para garantir que a página carregue

        # Lista de seletores CSS para tentar encontrar a imagem
        selectors = [
            "#landingImage",  # Imagem principal
            "#imgTagWrapperId img",  # Imagem dentro do wrapper
            "#main-image-container img",  # Qualquer imagem no container principal
            ".imgTagWrapper img",  # Imagens nos wrappers
            "img[data-old-hires]",  # Imagens com versão de alta resolução
            "#imageBlock img",  # Imagens no bloco de imagens
            ".a-dynamic-image",  # Imagens dinâmicas
            ".a-stretch-vertical",  # Imagens esticadas verticalmente
            ".a-stretch-horizontal"  # Imagens esticadas horizontalmente
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
                    
                    # Prioriza imagens de alta resolução
                    if data_old_hires and is_valid_image_url(data_old_hires):
                        return data_old_hires
                    
                    # Tenta a URL normal
                    if src and is_valid_image_url(src):
                        return src
                    
                    # Tenta extrair do atributo data-a-dynamic-image
                    if data_dynamic_image:
                        try:
                            # O atributo data-a-dynamic-image é um JSON com URLs e dimensões
                            dynamic_images = json.loads(data_dynamic_image)
                            # Pega a URL com a maior resolução
                            largest_url = max(dynamic_images.items(), key=lambda x: x[1][0])[0]
                            if is_valid_image_url(largest_url):
                                return largest_url
                        except:
                            pass

            except Exception as e:
                print(f"Erro ao tentar seletor {selector}: {e}")
                continue

        # Se não encontrou nenhuma imagem válida, tenta extrair do HTML
        try:
            html = driver.page_source
            # Procura por URLs de imagem no HTML
            img_urls = re.findall(r'https://m\.media-amazon\.com/images/I/[^"\']+\.(?:jpg|jpeg|png)', html)
            for url in img_urls:
                if is_valid_image_url(url):
                    return url
        except Exception as e:
            print(f"Erro ao extrair URLs do HTML: {e}")

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

    new_sent_products = []

    for product in products:
        try:
            # Verifica campos mínimos obrigatórios
            if not product.get('nome') or not product.get('valor_desconto') or not product.get('link'):
                print(f"Produto inválido: {product.get('nome')}")
                continue

            # Check if product was already sent
            if is_product_already_sent(product['nome'], sent_products):
                print(f"Produto já enviado anteriormente: {product['nome']}")
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
            
            success = False
            
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
                    success = True
                    print(f"✅ Mensagem enviada com imagem: {product['nome'][:50]}...")
                except Exception as e:
                    print(f"❌ Erro ao enviar com imagem, tentando sem imagem: {e}")
            
            # Se não conseguiu com imagem ou não tem imagem, tenta sem
            if not success:
                try:
                    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                    payload = {
                        'chat_id': TELEGRAM_GROUP_ID,
                        'text': message,
                        'parse_mode': 'Markdown'
                    }
                    response = requests.post(url, data=payload)
                    response.raise_for_status()
                    success = True
                    print(f"✅ Mensagem enviada sem imagem: {product['nome'][:50]}...")
                except Exception as e:
                    print(f"❌ Falha ao enviar mensagem: {e}")
            
            if success:
                new_sent_products.append(product['nome'])
            else:
                print(f"❌ Falha total ao enviar produto: {product['nome']}")
            
            time.sleep(3)  # Delay entre mensagens
            
        except Exception as e:
            print(f"❌ Erro crítico ao processar produto {product.get('nome', 'Sem nome')}: {str(e)}")

    print(f"📤 Total de produtos enviados nesta execução: {len(new_sent_products)}")
    return new_sent_products

def load_whatsapp_history():
    try:
        if os.path.exists(WHATSAPP_HISTORY_FILE):
            with open(WHATSAPP_HISTORY_FILE, 'r', encoding='utf-8') as f:
                nomes = json.load(f)
                return deque(nomes, maxlen=MAX_HISTORY_SIZE_WPP)
        return deque(maxlen=MAX_HISTORY_SIZE_WPP)
    except Exception as e:
        print(f"Erro ao carregar histórico do WhatsApp: {e}")
        return deque(maxlen=MAX_HISTORY_SIZE_WPP)

def save_whatsapp_history(history: deque):
    try:
        with open(WHATSAPP_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(history), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar histórico do WhatsApp: {e}")

def clear_whatsapp_auth():
    """Força a limpeza do diretório de autenticação do WhatsApp"""
    try:
        log("Forçando limpeza do diretório de autenticação do WhatsApp...")
        import shutil
        import os
        
        # Remove o diretório .wwebjs_auth se existir
        auth_dir = os.path.join(os.getcwd(), '.wwebjs_auth')
        if os.path.exists(auth_dir):
            shutil.rmtree(auth_dir)
            log("Diretório de autenticação removido.")
        else:
            log("Diretório de autenticação não encontrado.")
        
        # Também remove outros arquivos que podem estar relacionados
        possible_files = ['.wwebjs_auth', 'session.data', 'session.data.json']
        for file in possible_files:
            file_path = os.path.join(os.getcwd(), file)
            if os.path.exists(file_path):
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                else:
                    os.remove(file_path)
                log(f"Arquivo/diretório removido: {file}")
        
        log("Limpeza do diretório de autenticação concluída.")
        return True
    except Exception as e:
        log(f"Erro ao limpar diretório de autenticação: {e}")
        return False

def send_whatsapp_message(message, image_url=None):
    group = WHATSAPP_GROUP_NAME or "Central De Descontos"
    # Primeiro, verifica autenticação do WhatsApp
    try:
        auth_proc = subprocess.run(['node', 'Wpp/wpp_auth.js'], check=False)
        if auth_proc.returncode == 0:
            # Logado, pode enviar
            cmd = ['node', 'Wpp/wpp_envio.js', group, message]
            if image_url:
                cmd.append(image_url)
            try:
                subprocess.run(cmd, check=True)
                return True
            except subprocess.CalledProcessError as e:
                log(f"Erro ao enviar mensagem para WhatsApp: {e}")
                return False
            except Exception as e:
                log(f"Erro inesperado ao enviar mensagem para WhatsApp: {e}")
                return False
        elif auth_proc.returncode == 1:
            # Não logado, QR code foi gerado, avisa no Telegram
            aviso = "⚠️ O WhatsApp não está autenticado! Escaneie o QR code enviado para o Telegram para reautenticar."
            from Telegram.tl_enviar import send_telegram_message
            send_telegram_message(
                message=aviso,
                image_url=None,
                bot_token=TELEGRAM_BOT_TOKEN,
                chat_id=TELEGRAM_GROUP_ID
            )
            log("WhatsApp não autenticado. QR code enviado para o Telegram.")
            return False
        else:
            log(f"wpp_auth.js retornou código inesperado: {auth_proc.returncode}")
            return False
    except Exception as e:
        log(f"Erro ao rodar wpp_auth.js: {e}")
        return False

# Função para montar mensagem no formato do Telegram (pode ser usada para WhatsApp)
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
                # Imagem
                image_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#main-image-container img")))
                product_info['imagem'] = image_element.get_attribute('src')
            except:
                pass

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

def wait_for_whatsapp_auth(max_wait=120, interval=5):
    """Tenta autenticar o WhatsApp, esperando até max_wait segundos."""
    start = time.time()
    avisado = False
    tentativas = 0
    max_tentativas = 3
    
    while True:
        auth_proc = subprocess.run(['node', 'Wpp/wpp_auth.js'], check=False)
        if auth_proc.returncode == 0:
            print("WhatsApp autenticado! Prosseguindo com o scraper.")
            if avisado:
                from Telegram.tl_enviar import send_telegram_message
                send_telegram_message(
                    message='✅ WhatsApp autenticado com sucesso!',
                    image_url=None,
                    bot_token=TELEGRAM_BOT_TOKEN,
                    chat_id=TELEGRAM_GROUP_ID
                )
            return True
        elif auth_proc.returncode == 1:
            tentativas += 1
            if not avisado:
                aviso = "⚠️ O WhatsApp não está autenticado! Escaneie o QR code enviado para o Telegram para reautenticar."
                from Telegram.tl_enviar import send_telegram_message
                send_telegram_message(
                    message=aviso,
                    image_url=None,
                    bot_token=TELEGRAM_BOT_TOKEN,
                    chat_id=TELEGRAM_GROUP_ID
                )
                avisado = True
            
            print(f"Aguardando autenticação do WhatsApp... (tentativa {tentativas}/{max_tentativas})")
            
            # Se já tentou várias vezes, força limpeza do diretório
            if tentativas >= max_tentativas:
                print("Múltiplas tentativas falharam. Forçando limpeza do diretório de autenticação...")
                if clear_whatsapp_auth():
                    tentativas = 0  # Reset contador
                    avisado = False  # Reset aviso
                    print("Limpeza concluída. Tentando autenticação novamente...")
                else:
                    print("Falha na limpeza do diretório. Encerrando o script.")
                    sys.exit(1)
            
            if time.time() - start > max_wait:
                print("Tempo limite de autenticação do WhatsApp excedido. Encerrando o script.")
                sys.exit(1)
            time.sleep(interval)
        else:
            print(f"wpp_auth.js retornou código inesperado: {auth_proc.returncode}. Encerrando o script.")
            sys.exit(1)

def run_scraper():
    """Função principal que executa o scraper."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando execução do scraper...")

    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--enable-unsafe-swiftshader")

    if platform.system() == 'Windows':
        service = Service(ChromeDriverManager().install())
    else:
        service = Service(executable_path="/usr/bin/chromedriver")

    driver = webdriver.Chrome(service=service, options=chrome_options)

    # --- Verificação de autenticação do WhatsApp no início ---
    wait_for_whatsapp_auth()

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
        sent_promotions_whatsapp = load_whatsapp_history()
        novos_enviados = []
        produtos_nao_enviados = []

        print(f"📊 Processando {len(products_data)} produtos para envio...")
        
        for i, produto in enumerate(products_data, 1):
            print(f"📦 Processando produto {i}/{len(products_data)}: {produto.get('nome', 'Sem nome')[:50]}...")
            
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
                    
                # Envio para WhatsApp
                message = format_amazon_message(produto)
                image_url = None
                # Tenta usar a imagem principal
                if produto.get('imagem'):
                    print(f"[DEBUG] URL da imagem principal encontrada: {produto['imagem']}")
                    image_url = produto['imagem']
                # Se não tem imagem principal ou é um pixel/gif, tenta buscar alternativa
                if (not image_url or 'grey-pixel.gif' in image_url or image_url.strip() == '') and produto.get('link'):
                    print("[DEBUG] Tentando buscar imagem alternativa...")
                    alt_img = get_alternative_image(driver, produto['nome'], produto['link'])
                    if alt_img:
                        print(f"[DEBUG] Imagem alternativa encontrada: {alt_img}")
                        image_url = alt_img
                    else:
                        print("[DEBUG] Nenhuma imagem alternativa encontrada.")
                # Se não tem imagem, não envia para WhatsApp
                if not image_url or image_url.strip() == '' or 'grey-pixel.gif' in image_url:
                    print(f"[DEBUG] Produto NÃO enviado para WhatsApp pois não há imagem válida: {produto.get('nome','Sem nome')}")
                    continue
                print(f"[DEBUG] Enviando para WhatsApp: mensagem='{message[:60]}...' imagem='{image_url}'")
                whatsapp_success = False
                if not any(is_similar(produto['nome'], sent) for sent in sent_promotions_whatsapp):
                    whatsapp_success = send_whatsapp_message(message, image_url)
                    if whatsapp_success:
                        if not TEST_MODE:
                            sent_promotions_whatsapp.append(produto['nome'])
                            if len(sent_promotions_whatsapp) > MAX_HISTORY_SIZE_WPP:
                                sent_promotions_whatsapp = deque(list(sent_promotions_whatsapp)[-MAX_HISTORY_SIZE_WPP:], maxlen=MAX_HISTORY_SIZE_WPP)
                            save_whatsapp_history(sent_promotions_whatsapp)
                            print(f"✅ Produto enviado para WhatsApp: {produto['nome'][:50]}...")
                        else:
                            print("⚠️ Modo teste ativado - Produto não será salvo no histórico do WhatsApp")
                    else:
                        print(f"❌ Falha ao enviar para WhatsApp: {produto['nome'][:50]}...")
                else:
                    print(f"⏭️ Produto já enviado para WhatsApp: {produto['nome'][:50]}...")

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
