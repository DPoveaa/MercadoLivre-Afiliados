from datetime import datetime, timedelta
import os
import re
import time
import json
import random
import schedule
import sys
import urllib.parse
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import undetected_chromedriver as uc
from webdriver_manager.chrome import ChromeDriverManager
from Telegram.tl_enviar import send_telegram_message
import platform
import requests

sys.stdout.reconfigure(line_buffering=True)

load_dotenv()

# Verifica se está em modo de teste
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

print("Test Mode:", TEST_MODE)

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID_TESTE") if TEST_MODE else os.getenv("TELEGRAM_GROUP_ID")

# Configurações gerais
if TEST_MODE:
    print("Modo de teste ativado, salvando em promocoes_kabum_teste.json")
    HISTORY_FILE = 'promocoes_kabum_teste.json'
else:
    HISTORY_FILE = 'promocoes_kabum.json'
    print("Salvando em promocoes_kabum.json")

TOP_N_OFFERS = 10  # Top 10 produtos
MAX_HISTORY_SIZE = 200
SIMILARITY_THRESHOLD = 0.95

# URL da Kabum
KABUM_URL = "https://www.kabum.com.br/promocao/maisvendidos"

FORCE_RUN_ON_START = os.getenv("FORCE_RUN_ON_START", "false").lower() == "true"

def log(message):
    """Função para logging com timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def init_driver():
    """Inicializa o driver do Chrome com configurações stealth"""
    log("Inicializando navegador com undetected-chromedriver...")

    options = uc.ChromeOptions()
    
    # Opções essenciais para servidor Linux headless
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--headless=new')
    
    # Opções adicionais para estabilidade
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-images')
    options.add_argument('--disable-javascript')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--disable-features=TranslateUI')
    options.add_argument('--disable-ipc-flooding-protection')
    options.add_argument('--disable-default-apps')
    options.add_argument('--disable-sync')
    options.add_argument('--no-first-run')
    options.add_argument('--no-default-browser-check')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-web-security')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--disable-features=VizDisplayCompositor')
    
    # User agent para Linux
    options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Configurações de memória e performance
    options.add_argument('--memory-pressure-off')
    options.add_argument('--max_old_space_size=4096')
    options.add_argument('--disable-background-networking')
    
    try:
        driver = uc.Chrome(
            options=options,
            headless=True,
            driver_executable_path=ChromeDriverManager().install(),
            version_main=None  # Deixa o undetected-chromedriver detectar automaticamente
        )
        log("Navegador stealth iniciado")
        return driver
    except Exception as e:
        log(f"Erro ao iniciar o navegador: {str(e)}")
        raise

def load_promo_history():
    """Carrega o histórico de promoções já enviadas"""
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_promo_history(history):
    """Salva o histórico de promoções"""
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)

def clean_price(price_text):
    """Limpa o texto do preço e extrai apenas o valor numérico"""
    if not price_text:
        return None
    
    # Remove R$, espaços e converte vírgula para ponto
    price = re.sub(r'[R$\s]', '', price_text)
    price = price.replace(',', '.')
    
    # Extrai apenas números e ponto
    price = re.sub(r'[^\d.]', '', price)
    
    try:
        return float(price)
    except ValueError:
        return None

def gerar_link_afiliado(url_kabum):
    """Gera link de afiliado para a Kabum"""
    afiliado_id = "1939699"  # ID do afiliado
    url_base = "https://www.awin1.com/cread.php"
    parametros = {
        "awinmid": "17729",
        "awinaffid": afiliado_id,
        "ued": url_kabum
    }
    url_afiliado = f"{url_base}?{urllib.parse.urlencode(parametros)}"
    return url_afiliado

def get_product_links(driver):
    """Coleta os links dos produtos da página principal"""
    log("Coletando links dos produtos...")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            driver.get(KABUM_URL)
            # Remover sleep e usar apenas WebDriverWait
            wait = WebDriverWait(driver, 20)
            products_container = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#listing"))
            )
            # Encontra todos os links de produtos
            product_links = []
            link_selectors = [
                "a[href*='/produto/']",
                "div[data-testid='product-card'] a",
                "div.sc-tYqdw a",
                "div[class*='sc-'] a[href*='/produto/']"
            ]
            for selector in link_selectors:
                try:
                    links = products_container.find_elements(By.CSS_SELECTOR, selector)
                    if links:
                        log(f"Encontrados {len(links)} links com selector: {selector}")
                        for link in links[:TOP_N_OFFERS]:
                            href = link.get_attribute('href')
                            if href and '/produto/' in href:
                                product_links.append(href)
                        break
                except Exception as e:
                    log(f"Erro com selector {selector}: {str(e)}")
                    continue
            product_links = list(set(product_links))
            log(f"Coletados {len(product_links)} links únicos de produtos")
            return product_links[:TOP_N_OFFERS]
            
        except Exception as e:
            log(f"Tentativa {attempt + 1}/{max_retries} falhou: {str(e)}")
            if attempt < max_retries - 1:
                log("Aguardando 5 segundos antes de tentar novamente...")
                time.sleep(5)
                # Tenta reinicializar o driver se necessário
                try:
                    driver.quit()
                except:
                    pass
                try:
                    driver = init_driver()
                except Exception as init_error:
                    log(f"Erro ao reinicializar driver: {str(init_error)}")
            else:
                log("Todas as tentativas falharam")
                return []
    
    return []

def is_gift_card(product_name):
    """Verifica se o produto é um gift card"""
    gift_card_keywords = [
        'gift card', 'gift-card', 'giftcard', 'cartão presente', 'cartao presente',
        'vale presente', 'vale-presente', 'presente digital', 'digital gift',
        'steam card', 'playstation card', 'xbox card', 'nintendo card', 
        'google play card', 'app store card', 'itunes card', 'netflix card', 
        'spotify card', 'amazon card', 'uber card', 'ifood card', 'rappi card',
        'vale steam', 'vale playstation', 'vale xbox', 'vale nintendo',
        'código steam', 'código playstation', 'código xbox', 'código nintendo'
    ]
    
    product_lower = product_name.lower()
    return any(keyword in product_lower for keyword in gift_card_keywords)

def encurtar_url(url):
    """Encurta uma URL usando a API do TinyURL"""
    try:
        api_url = f'https://tinyurl.com/api-create.php?url={url}'
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            return response.text.strip()
        else:
            log(f"Erro ao encurtar URL: {response.status_code}")
            return url
    except Exception as e:
        log(f"Erro ao encurtar URL: {str(e)}")
        return url

def extract_product_details(driver, product_url):
    """Extrai informações detalhadas de um produto individual"""
    log(f"Acessando página do produto: {product_url}")
    
    try:
        # Verifica se a sessão ainda é válida
        try:
            driver.current_url
        except:
            log("Sessão do driver inválida, tentando reinicializar...")
            driver = init_driver()
        
        driver.get(product_url)
        wait = WebDriverWait(driver, 15)
        
        # Nome do produto
        product_name = "Nome não encontrado"
        name_selectors = [
            "h1[data-testid='product-name']",
            "h1.sc-ff8a9791-6",
            "h1",
            "h2[data-testid='product-name']",
            "h2"
        ]
        
        for selector in name_selectors:
            try:
                name_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                product_name = name_element.text.strip()
                break
            except:
                continue
        
        if is_gift_card(product_name):
            log(f"Produto ignorado (gift card): {product_name}")
            return None
        
        # Preços
        old_price = None
        discount_price = None
        pix_price = None
        pix_discount_percent = None
        
        # 1. Tenta pegar o preço antigo pelo seletor mais importante
        try:
            old_price_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "span.sc-5492faee-1.ibyzkU.oldPrice")))
            old_price_text = old_price_elem.text.strip()
            old_price = clean_price(old_price_text)
        except:
            old_price = None
        
        # 2. Se não achou o old_price, tenta pegar pelo regularPrice
        if not old_price:
            try:
                regular_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "b.regularPrice")))
                regular_text = regular_elem.text.strip()
                old_price = clean_price(regular_text)
            except:
                old_price = None
        
        # 3. Se achou o old_price pelo seletor principal, tenta pegar o regularPrice como preço com desconto
        if old_price:
            try:
                discount_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "b.regularPrice")))
                discount_text = discount_elem.text.strip()
                discount_price = clean_price(discount_text)
                if discount_price == old_price:
                    discount_price = None
            except:
                discount_price = None
        
        # PIX
        pix_price = None
        try:
            pix_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h4.sc-5492faee-2.ipHrwP.finalPrice")))
            pix_text = pix_elem.text.strip()
            pix_price = clean_price(pix_text)
        except:
            pix_selectors = [
                "div.sc-5492faee-0 h4.sc-5492faee-2.finalPrice",
                "h4[class*='finalPrice']",
                "span[class*='pix']",
                "h4[class*='final']"
            ]
            for selector in pix_selectors:
                try:
                    pix_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    pix_text = pix_elem.text.strip()
                    price = clean_price(pix_text)
                    if price:
                        pix_price = price
                        break
                except:
                    continue
        
        # Desconto PIX
        pix_discount_percent = None
        try:
            discount_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "span.sc-5492faee-3.igKOYC b.discountPercentage")))
            discount_text = discount_elem.text.strip()
            discount_match = re.search(r'(\d+)', discount_text)
            if discount_match:
                pix_discount_percent = int(discount_match.group(1))
        except:
            pix_discount_selectors = [
                "span.sc-5492faee-3 b.discountPercentage",
                "b.discountPercentage",
                "span[class*='discountPercentage']",
                "span[class*='pix'] b",
                "span[class*='final'] b"
            ]
            for selector in pix_discount_selectors:
                try:
                    discount_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    discount_text = discount_elem.text.strip()
                    discount_match = re.search(r'(\d+)', discount_text)
                    if discount_match:
                        pix_discount_percent = int(discount_match.group(1))
                        break
                except:
                    continue
        
        # Informações de parcelamento (melhorado)
        card_info = ""
        installment_info = []
        card_selectors = [
            "div.sc-4f698d6c-0.hkfkrb",
            "div[class*='installment']",
            "div[class*='parcel']",
            "span[class*='installment']",
            "div[class*='payment']"
        ]
        
        for selector in card_selectors:
            try:
                card_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in card_elements:
                    text = elem.text.strip()
                    if 'x' in text and ('R$' in text or 'reais' in text.lower()):
                        # Separa as informações de parcelamento
                        lines = text.split('\n')
                        for line in lines:
                            line = line.strip()
                            if line and ('x' in line or 'cartão' in line.lower() or 'juros' in line.lower()):
                                installment_info.append(line)
                        break
                if installment_info:
                    break
            except:
                continue
        
        # Formata as informações de parcelamento
        if installment_info:
            card_info = "\n- ".join(installment_info)
            if not card_info.startswith("-"):
                card_info = "- " + card_info
        
        # Avaliações
        rating = None
        rating_count = None
        rating_selectors = [
            "div.sc-781b7e7f-3 span.sc-781b7e7f-1",  # Nota específica
            "span.sc-781b7e7f-1.hdvIZL",  # Nota com classe específica
            "span[class*='hdvIZL']",  # Nota com classe parcial
            "div.sc-781b7e7f-5 span",  # Número de avaliações
            "span.sc-781b7e7f-5.cQKdQd",  # Número de avaliações com classe específica
            "span[class*='cQKdQd']",  # Número de avaliações com classe parcial
            "span.sc-5492faee-4",
            "span[class*='rating']",
            "div[class*='rating']",
            "span[data-testid='rating']"
        ]
        
        # Primeiro tenta encontrar o container de avaliações
        rating_container_selectors = [
            "div.sc-781b7e7f-3",
            "div[class*='jSiwRS']",
            "div[class*='rating']"
        ]
        
        rating_container = None
        for selector in rating_container_selectors:
            try:
                rating_container = driver.find_element(By.CSS_SELECTOR, selector)
                if rating_container:
                    log(f"Container de avaliações encontrado com: {selector}")
                    break
            except:
                continue
        
        if rating_container:
            # Extrai a nota
            try:
                rating_element = rating_container.find_element(By.CSS_SELECTOR, "span.sc-781b7e7f-1.hdvIZL")
                rating_text = rating_element.text.strip()
                rating = float(rating_text)
                log(f"Nota encontrada: {rating}")
            except:
                try:
                    rating_element = rating_container.find_element(By.CSS_SELECTOR, "span[class*='hdvIZL']")
                    rating_text = rating_element.text.strip()
                    rating = float(rating_text)
                    log(f"Nota encontrada: {rating}")
                except:
                    pass
            
            # Extrai o número de avaliações
            try:
                count_element = rating_container.find_element(By.CSS_SELECTOR, "span.sc-781b7e7f-5.cQKdQd")
                count_text = count_element.text.strip()
                # Extrai apenas os números
                count_match = re.search(r'\((\d+)\s*avaliações?\)', count_text)
                if count_match:
                    rating_count = int(count_match.group(1))
                    log(f"Número de avaliações encontrado: {rating_count}")
            except:
                try:
                    count_element = rating_container.find_element(By.CSS_SELECTOR, "span[class*='cQKdQd']")
                    count_text = count_element.text.strip()
                    # Extrai apenas os números
                    count_match = re.search(r'\((\d+)\s*avaliações?\)', count_text)
                    if count_match:
                        rating_count = int(count_match.group(1))
                        log(f"Número de avaliações encontrado: {rating_count}")
                except:
                    pass
        else:
            # Fallback para seletores antigos
            for selector in rating_selectors:
                try:
                    rating_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in rating_elements:
                        rating_text = elem.text.strip()
                        # Extrai rating e número de avaliações
                        rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                        if rating_match:
                            rating = float(rating_match.group(1))
                        
                        count_match = re.search(r'\((\d+)\)', rating_text)
                        if count_match:
                            rating_count = int(count_match.group(1))
                        
                        if rating or rating_count:
                            break
                    if rating or rating_count:
                        break
                except:
                    continue
        
        # Imagem do produto
        image_url = None
        img_selectors = [
            "img[data-nimg='1']",  # Seletor específico para a imagem principal
            "img[data-testid='product-image']",
            "img.sc-ff8a9791-4",
            "img[class*='product']",
            "img[loading='lazy']",  # Imagens com loading lazy
            "img"
        ]
        
        for selector in img_selectors:
            try:
                img_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for img in img_elements:
                    src = img.get_attribute('src')
                    # Verifica se é uma imagem válida da Kabum
                    if src and ('kabum.com.br/produtos/fotos' in src or 'images' in src):
                        # Verifica se tem dimensões adequadas (não é um ícone pequeno)
                        width = img.get_attribute('width')
                        height = img.get_attribute('height')
                        
                        # Se tem dimensões definidas, verifica se é uma imagem grande
                        if width and height:
                            try:
                                w = int(width)
                                h = int(height)
                                if w >= 200 and h >= 200:  # Imagem com tamanho adequado
                                    image_url = src
                                    log(f"Imagem encontrada: {src}")
                                    break
                            except ValueError:
                                # Se não consegue converter, assume que é válida
                                image_url = src
                                log(f"Imagem encontrada: {src}")
                                break
                        else:
                            # Se não tem dimensões definidas, assume que é válida
                            image_url = src
                            log(f"Imagem encontrada: {src}")
                            break
                if image_url:
                    break
            except Exception as e:
                log(f"Erro ao buscar imagem com selector {selector}: {str(e)}")
                continue
        
        # Gera link de afiliado
        affiliate_url = gerar_link_afiliado(product_url)
        # Encurta o link de afiliado
        affiliate_url_short = encurtar_url(affiliate_url)
        
        return {
            'name': product_name,
            'url': product_url,
            'affiliate_url': affiliate_url_short,
            'old_price': old_price,
            'discount_price': discount_price,
            'pix_price': pix_price,
            'pix_discount_percent': pix_discount_percent,
            'card_info': card_info,
            'rating': rating,
            'rating_count': rating_count,
            'image_url': image_url
        }
        
    except Exception as e:
        log(f"Erro ao extrair detalhes do produto: {str(e)}")
        return None

def escape_markdown(text):
    """Escapa apenas caracteres especiais do Markdown que realmente precisam ser escapados"""
    if not text:
        return text
    
    # Apenas caracteres que realmente precisam ser escapados no Markdown
    # Não escapa parênteses, hífens, exclamações que são usados normalmente
    chars_to_escape = ['*', '_', '[', ']', '`', '>', '#', '+', '=', '|', '{', '}', '~']
    
    for char in chars_to_escape:
        text = text.replace(char, f'\\{char}')
    
    return text

def format_telegram_message(product):
    """Formata a mensagem para o Telegram"""
    message = f"🥷 **Kabum**\n\n"
    
    # Nome do produto (escapa caracteres especiais)
    product_name = escape_markdown(product['name'])
    message += f"🏷️ {product_name}\n\n"
    
    # Avaliação
    if product['rating'] and product['rating_count']:
        message += f"⭐ {product['rating']} ({product['rating_count']} avaliações)\n\n"
    elif not product['rating'] and not product['rating_count']:
        message += f"⭐ (sem avaliações)\n\n"
    
    # Calcula descontos
    desconto_cartao = None
    desconto_pix = None
    if product['old_price'] and product['discount_price']:
        desconto_cartao = int(round(((product['old_price'] - product['discount_price']) / product['old_price']) * 100))
    if product['old_price'] and product['pix_price']:
        desconto_pix = int(round(((product['old_price'] - product['pix_price']) / product['old_price']) * 100))
    
    # Maior desconto
    maior_desconto = None
    if desconto_cartao and desconto_pix:
        maior_desconto = desconto_cartao + desconto_pix
        if desconto_pix > desconto_cartao:
            maior_desconto = desconto_pix
        elif desconto_cartao > desconto_pix:
            maior_desconto = desconto_cartao
    elif desconto_cartao:
        maior_desconto = desconto_cartao
    elif desconto_pix:
        maior_desconto = desconto_pix
    
    if maior_desconto:
        message += f"📉 Desconto de até {maior_desconto}% OFF\n\n"
    
    # Preço antigo
    if product['old_price']:
        message += f"💸 De: R$ {product['old_price']:.2f}\n\n"
    # Preço no cartão
    if product['discount_price']:
        message += f"💥 Por apenas: R$ {product['discount_price']:.2f}\n"
    # Preço no PIX
    if product['pix_price'] and product['discount_price']:
        message += f"💥 Ou: R$ {product['pix_price']:.2f} (à vista no PIX)\n"
    elif product['pix_price']:
        message += f"💥 Por apenas: R$ {product['pix_price']:.2f} (à vista no PIX)\n"
    
    # Informações de cartão (formatadas)
    if product['card_info']:
        message += f"\n💳 **Parcelamentos:**\n"
        card_lines = product['card_info'].split('\n')
        for line in card_lines:
            line = line.strip()
            if line:
                line = escape_markdown(line)
                if not line.startswith('-'):
                    message += f"- {line}\n"
                else:
                    message += f"{line}\n"
    
    # Link do produto (afiliado)
    message += f"\n🛒 **Garanta agora:**\n"
    message += f"🔗 {product['affiliate_url']}"
    
    return message

def is_similar_product(product1, product2):
    """Verifica se dois produtos são similares"""
    name1 = product1['name'].lower()
    name2 = product2['name'].lower()
    
    # Calcula similaridade simples
    words1 = set(name1.split())
    words2 = set(name2.split())
    
    if len(words1) == 0 or len(words2) == 0:
        return False
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    similarity = len(intersection) / len(union)
    return similarity >= SIMILARITY_THRESHOLD

def check_promotions():
    """Função principal que verifica e envia promoções"""
    log("Iniciando verificação de promoções da Kabum...")
    
    driver = None
    try:
        driver = init_driver()
        
        # Carrega histórico
        sent_promotions = load_promo_history()
        
        # Coleta links dos produtos
        product_links = get_product_links(driver)
        
        if not product_links:
            log("Nenhum link de produto encontrado")
            return
        
        log(f"Encontrados {len(product_links)} links para processar")
        
        # Processa cada produto individualmente
        for i, product_url in enumerate(product_links):
            log(f"Processando produto {i+1}/{len(product_links)}")
            
            # Verifica se o driver ainda está válido
            try:
                driver.current_url
            except:
                log("Driver inválido, reinicializando...")
                try:
                    driver.quit()
                except:
                    pass
                driver = init_driver()
            
            # Extrai detalhes do produto
            product = extract_product_details(driver, product_url)
            
            if not product:
                log(f"Erro ao extrair detalhes do produto {i+1}")
                continue
            
            # Verifica se já foi enviado
            is_duplicate = any(is_similar_product(product, sent) for sent in sent_promotions)
            
            if not is_duplicate:
                log(f"Enviando produto: {product['name'][:50]}...")
                
                # Verifica se tem imagem
                if product.get('image_url'):
                    log(f"Imagem encontrada para envio: {product['image_url']}")
                else:
                    log("Nenhuma imagem encontrada para o produto")
                
                # Formata mensagem
                message = format_telegram_message(product)
                
                # Envia para o Telegram
                success = send_telegram_message(
                    message=message,
                    image_url=product.get('image_url'),
                    bot_token=TELEGRAM_BOT_TOKEN,
                    chat_id=TELEGRAM_GROUP_ID
                )
                
                if success:
                    log("Mensagem enviada com sucesso")
                    # Adiciona ao histórico
                    sent_promotions.append(product)
                    
                    # Mantém apenas os últimos MAX_HISTORY_SIZE
                    if len(sent_promotions) > MAX_HISTORY_SIZE:
                        sent_promotions = sent_promotions[-MAX_HISTORY_SIZE:]
                    
                    save_promo_history(sent_promotions)
                else:
                    log("Erro ao enviar mensagem")
                
                # Pausa entre envios
                time.sleep(random.uniform(3, 7))
            else:
                log(f"Produto já enviado: {product['name'][:50]}...")
        
        log("Verificação de promoções concluída")
        
    except Exception as e:
        log(f"Erro durante verificação: {str(e)}")
    finally:
        if driver:
            try:
                driver.quit()
                log("Navegador fechado")
            except:
                log("Erro ao fechar navegador")

def schedule_scraper():
    """Agenda a execução do scraper"""
    log("Agendando execução do scraper da Kabum...")

    # Agenda para executar a cada hora, nos minutos 15
    for h in range(24):
        hora = f"{h:02d}:15"
        schedule.every().day.at(hora).do(check_promotions)

    # Executa imediatamente se FORCE_RUN_ON_START estiver ativado
    if FORCE_RUN_ON_START:
        log("Execução imediata forçada pelo .env")
        check_promotions()

    log("Scraper da Kabum agendado para executar todo dia nos minutos 15 de cada hora")

    # Loop infinito para garantir que o agendamento continue rodando
    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_GROUP_ID:
        log("Erro: TELEGRAM_BOT_TOKEN e TELEGRAM_GROUP_ID devem estar configurados no .env")
        sys.exit(1)
    
    log("Iniciando scraper da Kabum...")
    schedule_scraper()
