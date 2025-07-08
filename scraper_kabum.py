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
import subprocess
from collections import deque

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

# URL da Kabum - múltiplas URLs para rotação
KABUM_URLS = [
    "https://www.kabum.com.br/promocao/maisvendidos",
    "https://www.kabum.com.br/promocao/HARDWAREKABUM?page_number=1&page_size=40&facet_filters=&sort=&variant=catalog",
    "https://www.kabum.com.br/promocao/PCGAMER?page_number=1&page_size=40&facet_filters=&sort=&variant=catalog",
    "https://www.kabum.com.br/promocao/COMPUTADORKABUM?page_number=1&page_size=40&facet_filters=&sort=&variant=catalog",
    "https://www.kabum.com.br/promocao/perifericoskabum?page_number=1&page_size=40&facet_filters=&sort=&variant=catalog"
]

# Arquivo para armazenar os links já utilizados
USED_URLS_FILE = 'used_urls_kabum.json'

def load_used_urls():
    """Carrega a lista de URLs já utilizadas do arquivo"""
    try:
        with open(USED_URLS_FILE, 'r') as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_used_urls(used_urls):
    """Salva a lista de URLs já utilizadas no arquivo"""
    with open(USED_URLS_FILE, 'w') as f:
        json.dump(list(used_urls), f)

def get_rotated_urls():
    """Retorna 3 URLs aleatórias da lista de ofertas, evitando repetição"""
    used_urls = load_used_urls()
    
    # Se todos os links já foram usados, limpa o histórico
    if len(used_urls) >= len(KABUM_URLS):
        log("Todos os links foram utilizados. Reiniciando histórico...")
        used_urls.clear()
        save_used_urls(used_urls)
    
    # Filtra apenas os links não utilizados
    available_urls = [url for url in KABUM_URLS if url not in used_urls]
    
    # Se não houver links suficientes, usa todos os links disponíveis
    num_urls = min(2, len(available_urls))
    
    # Escolhe aleatoriamente os links
    selected_urls = random.sample(available_urls, num_urls)
    
    # Adiciona os links selecionados ao histórico
    used_urls.update(selected_urls)
    save_used_urls(used_urls)
    
    log(f"Links selecionados: {len(selected_urls)} de {len(available_urls)} disponíveis")
    return selected_urls

FORCE_RUN_ON_START = os.getenv("FORCE_RUN_ON_START", "false").lower() == "true"

WHATSAPP_HISTORY_FILE = 'promocoes_kabum_whatsapp.json'
MAX_HISTORY_SIZE_WPP = 200

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
    """Carrega o histórico de nomes de produtos já enviados"""
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_promo_history(history):
    """Salva o histórico de nomes de produtos"""
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)

def load_whatsapp_history():
    try:
        with open(WHATSAPP_HISTORY_FILE, 'r', encoding='utf-8') as f:
            nomes = json.load(f)
        return deque(nomes, maxlen=MAX_HISTORY_SIZE_WPP)
    except (FileNotFoundError, json.JSONDecodeError):
        return deque(maxlen=MAX_HISTORY_SIZE_WPP)

def save_whatsapp_history(history: deque):
    with open(WHATSAPP_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(history), f)

sent_promotions_whatsapp = load_whatsapp_history()

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
    """Coleta os links dos produtos de múltiplas URLs"""
    log("Coletando links dos produtos de múltiplas URLs...")
    
    all_product_links = []
    urls_to_process = get_rotated_urls()
    
    for url in urls_to_process:
        try:
            log(f"\nAcessando categoria: {url}")
            driver.get(url)
            
            # Espera inicial combinada com delay
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '#listing'))
            )
            time.sleep(random.uniform(2, 4))
            
            # Scroll dinâmico para carregar mais itens
            last_height = driver.execute_script("return document.body.scrollHeight")
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1.5, 2.5))
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            
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
                    links = driver.find_elements(By.CSS_SELECTOR, selector)
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
            log(f"Coletados {len(product_links)} links únicos de produtos da categoria")
            all_product_links.extend(product_links)
            
            # Intervalo aleatório entre categorias
            time.sleep(random.uniform(5, 10))
            
        except Exception as e:
            log(f"Falha na categoria {url}: {str(e)}")
            continue
    
    # Remove duplicatas e retorna os melhores
    all_product_links = list(set(all_product_links))
    log(f"Total de {len(all_product_links)} links únicos coletados de todas as categorias")
    return all_product_links[:TOP_N_OFFERS]

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
        
        # Nome do produto - captura primeiro para verificar se é gift card
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
        
        # Verifica se é gift card logo após capturar o nome
        if is_gift_card(product_name):
            log(f"Produto ignorado (gift card): {product_name}")
            return None
        
        # Preços - novos seletores baseados no HTML fornecido
        old_price = None
        discount_price = None
        pix_price = None
        pix_discount_percent = None
        
        # 1. Preço original (line-through)
        try:
            # Busca qualquer span com as classes do preço original
            old_price_elem = driver.find_element(By.CSS_SELECTOR, "span.text-black-600.text-xs.font-normal.line-through")
            old_price_text = old_price_elem.text.strip()
            old_price = clean_price(old_price_text)
            log(f"Preço original encontrado: {old_price}")
        except Exception as e:
            log(f"Preço original não encontrado pelo seletor direto: {str(e)}")
            # Fallback: busca todos os spans line-through e pega o maior valor válido
            try:
                old_price_elems = driver.find_elements(By.CSS_SELECTOR, "span.text-black-600.text-xs.font-normal.line-through")
                valores = []
                for elem in old_price_elems:
                    text = elem.text.strip()
                    valor = clean_price(text)
                    if valor:
                        valores.append(valor)
                if valores:
                    old_price = max(valores)
                    log(f"Preço original encontrado (fallback): {old_price}")
                else:
                    # Fallback ainda mais amplo: qualquer span com 'line-through'
                    try:
                        generic_line_throughs = driver.find_elements(By.CSS_SELECTOR, "span.line-through")
                        valores_genericos = []
                        for elem in generic_line_throughs:
                            text = elem.text.strip()
                            valor = clean_price(text)
                            if valor:
                                valores_genericos.append(valor)
                        if valores_genericos:
                            old_price = max(valores_genericos)
                            log(f"Preço original encontrado (fallback genérico): {old_price}")
                        else:
                            old_price = None
                    except Exception as e3:
                        log(f"Preço original não encontrado nem no fallback genérico: {str(e3)}")
                        old_price = None
            except Exception as e2:
                log(f"Preço original não encontrado nem no fallback: {str(e2)}")
                old_price = None

        # 2. Preço no cartão (primeiro <b> dentro de <span class='block my-12'>)
        try:
            card_span = driver.find_element(By.CSS_SELECTOR, "span.block.my-12")
            card_bolds = card_span.find_elements(By.CSS_SELECTOR, "b.text-xs.font-bold.text-black-700")
            if card_bolds:
                discount_price_text = card_bolds[0].text.strip()
                discount_price = clean_price(discount_price_text)
                log(f"Preço cartão encontrado: {discount_price}")
            else:
                discount_price = None
        except Exception as e:
            log(f"Preço cartão não encontrado: {str(e)}")
            discount_price = None

        # 3. Preço PIX (<h4 ...>)
        try:
            pix_elems = driver.find_elements(By.CSS_SELECTOR, "h4.text-4xl.text-secondary-500.font-bold")
            pix_valores = []
            for elem in pix_elems:
                pix_text = elem.text.strip()
                valor = clean_price(pix_text)
                if valor:
                    pix_valores.append(valor)
            if pix_valores:
                pix_price = min(pix_valores)
                log(f"Preço PIX encontrado (menor valor): {pix_price}")
            else:
                pix_price = None
        except Exception as e:
            log(f"Preço PIX não encontrado: {str(e)}")
            pix_price = None
        
        # 4. Informações de parcelamento (novo seletor)
        card_info = ""
        try:
            # Procura pelo container de parcelamento
            installment_container = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.w-full span.block.my-12")))
            installment_text = installment_container.text.strip()
            
            if installment_text:
                # Limpa e formata o texto de parcelamento
                lines = installment_text.split('\n')
                formatted_lines = []
                for line in lines:
                    line = line.strip()
                    if line and ('x' in line or 'cartão' in line.lower() or 'juros' in line.lower() or 'sem juros' in line.lower()):
                        formatted_lines.append(line)
                
                if formatted_lines:
                    card_info = "\n- ".join(formatted_lines)
                    if not card_info.startswith("-"):
                        card_info = "- " + card_info
                    log(f"Parcelamento encontrado: {card_info}")
        except:
            # Fallback para seletores antigos
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
    message = f"🥷 *Kabum*\n\n"
    
    # Nome do produto (escapa caracteres especiais)
    product_name = escape_markdown(product['name'])
    message += f"🏷️ {product_name}\n\n"
    
    # Avaliação
    if product['rating'] and product['rating_count']:
        message += f"⭐ {product['rating']} ({product['rating_count']} avaliações)\n\n"
    elif not product['rating'] and not product['rating_count']:
        message += f"⭐ (sem avaliações)\n\n"

    # Se não houver preço antigo, usa o preço do cartão como antigo
    old_price = product.get('old_price')
    discount_price = product.get('discount_price')
    pix_price = product.get('pix_price')
    desconto_cartao = None
    desconto_pix = None
    desconto_cartao_percent = None
    desconto_total = None

    # Tenta extrair desconto do texto de parcelamento (ex: 'ou 1x com 9% de desconto  no cartão')
    card_info = product.get('card_info')
    desconto_cartao_text = None
    if card_info:
        import re
        m = re.search(r'(\d+)% de desconto', card_info)
        if m:
            desconto_cartao_percent = int(m.group(1))
            desconto_cartao_text = m.group(0)

    # Se não houver preço antigo, usa o preço do cartão
    if not old_price and discount_price:
        old_price = discount_price

    # Calcula descontos
    if old_price and discount_price:
        desconto_cartao = int(round(((old_price - discount_price) / old_price) * 100))
    if old_price and pix_price:
        desconto_pix = int(round(((old_price - pix_price) / old_price) * 100))

    # Maior desconto
    if desconto_pix and desconto_cartao:
        desconto_total = max(desconto_pix, desconto_cartao)
    elif desconto_pix:
        desconto_total = desconto_pix
    elif desconto_cartao:
        desconto_total = desconto_cartao
    elif desconto_cartao_percent:
        desconto_total = desconto_cartao_percent

    if desconto_total:
        message += f"📉 Desconto de até {desconto_total}% OFF\n\n"

    # Preço antigo (sempre mostra)
    if old_price:
        message += f"💸 De: R$ {old_price:.2f}\n\n"
    # Preço no cartão
    if discount_price:
        message += f"💥 Por apenas: R$ {discount_price:.2f}\n"
    # Preço no PIX
    if pix_price and discount_price:
        message += f"💥 Ou: R$ {pix_price:.2f} (no PIX)\n"
    elif pix_price:
        message += f"💥 Por apenas: R$ {pix_price:.2f} (no PIX)\n"

    # Informações de cartão (formatadas)
    if card_info:
        message += f"\n💳 *Parcelamentos:*\n"
        card_lines = card_info.split('\n')
        for line in card_lines:
            line = line.strip()
            if line:
                line = escape_markdown(line)
                if not line.startswith('-'):
                    message += f"- {line}\n"
                else:
                    message += f"{line}\n"

    # Link do produto (afiliado)
    message += f"\n🛒 *Garanta agora:*\n"
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

def is_duplicate_product(product_name, sent_names):
    """Verifica se o nome do produto já foi enviado (case insensitive)"""
    if not isinstance(product_name, str):
        log(f"ATENÇÃO: product_name não é string: {product_name} ({type(product_name)})")
        return False
    name = product_name.strip().lower()
    return any(isinstance(sent, str) and name == sent.strip().lower() for sent in sent_names)

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
            
            # Extrai detalhes do produto com retry
            product = None
            max_retries = 3
            for retry in range(max_retries):
                try:
                    product = extract_product_details(driver, product_url)
                    if product:
                        # Verifica se já foi enviado antes de continuar
                        is_duplicate = is_duplicate_product(product['name'], sent_promotions)
                        if is_duplicate:
                            log(f"Produto já enviado: {product['name'][:50]}...")
                            product = None  # Marca como None para não processar
                            break
                        else:
                            break  # Produto válido e não duplicado
                    else:
                        log(f"Tentativa {retry + 1}/{max_retries} falhou - produto retornou None")
                except Exception as e:
                    log(f"Tentativa {retry + 1}/{max_retries} falhou com erro: {str(e)}")
                
                if retry < max_retries - 1:
                    log(f"Aguardando 3 segundos antes da próxima tentativa...")
                    time.sleep(3)
            
            # Validação dos dados obrigatórios
            dados_faltando = []
            if not product:
                log(f"Erro ao extrair detalhes do produto {i+1} após {max_retries} tentativas ou produto já enviado/gift card")
                continue
            if not product.get('name'):
                dados_faltando.append('nome')
            if not (product.get('old_price') or product.get('discount_price') or product.get('pix_price')):
                dados_faltando.append('valores')
            if not product.get('card_info'):
                dados_faltando.append('parcelamento')
            if not product.get('affiliate_url'):
                dados_faltando.append('link')
            if dados_faltando:
                log(f"Produto ignorado por falta de dados obrigatórios: {', '.join(dados_faltando)} - {product.get('name', 'Nome não encontrado')}")
                continue
            
            # Verifica se já foi enviado (verificação adicional)
            is_duplicate = is_duplicate_product(product['name'], sent_promotions)
            
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
                    sent_promotions.append(product['name'])
                    
                    # Mantém apenas os últimos MAX_HISTORY_SIZE
                    if len(sent_promotions) > MAX_HISTORY_SIZE:
                        sent_promotions = sent_promotions[-MAX_HISTORY_SIZE:]
                    
                    save_promo_history(sent_promotions)
                else:
                    log("Erro ao enviar mensagem")
                
                # Pausa entre envios
                time.sleep(random.uniform(3, 7))

                # Envia para WhatsApp
                whatsapp_success = send_whatsapp_message_kabum(message, product.get('image_url'))
                if whatsapp_success:
                    if not TEST_MODE:
                        sent_promotions_whatsapp.append(product['name'])
                        if len(sent_promotions_whatsapp) > MAX_HISTORY_SIZE_WPP:
                            sent_promotions_whatsapp = deque(list(sent_promotions_whatsapp)[-MAX_HISTORY_SIZE_WPP:], maxlen=MAX_HISTORY_SIZE_WPP)
                        save_whatsapp_history(sent_promotions_whatsapp)
                        log("Produto salvo no histórico do WhatsApp.")
                    else:
                        log("⚠️ Modo teste ativado - Produto não será salvo no histórico do WhatsApp")
                else:
                    log("Falha ao enviar para WhatsApp - Produto não será salvo no histórico do WhatsApp")
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

def send_whatsapp_message_kabum(message, image_url=None):
    group = "Grupo Teste" if TEST_MODE else "Central De Descontos"
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

def wait_for_whatsapp_auth(max_wait=120, interval=5):
    """Tenta autenticar o WhatsApp, esperando até max_wait segundos."""
    start = time.time()
    avisado = False
    while True:
        auth_proc = subprocess.run(['node', 'Wpp/wpp_auth.js'], check=False)
        if auth_proc.returncode == 0:
            log("WhatsApp autenticado! Prosseguindo com o scraper.")
            return True
        elif auth_proc.returncode == 1:
            if not avisado:
                aviso = "⚠️ O WhatsApp não está autenticado! Escaneie o QR code enviado para o Telegram para reautenticar."
                send_telegram_message(
                    message=aviso,
                    image_url=None,
                    bot_token=TELEGRAM_BOT_TOKEN,
                    chat_id=TELEGRAM_GROUP_ID
                )
                avisado = True
            log("Aguardando autenticação do WhatsApp...")
            if time.time() - start > max_wait:
                log("Tempo limite de autenticação do WhatsApp excedido. Encerrando o script.")
                sys.exit(1)
            time.sleep(interval)
        else:
            log(f"wpp_auth.js retornou código inesperado: {auth_proc.returncode}. Encerrando o script.")
            sys.exit(1)

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_GROUP_ID:
        log("Erro: TELEGRAM_BOT_TOKEN e TELEGRAM_GROUP_ID devem estar configurados no .env")
        sys.exit(1)
    
    log("Iniciando scraper da Kabum...")
    # --- Verificação de autenticação do WhatsApp no início ---
    wait_for_whatsapp_auth()
    # --- Fim da verificação de autenticação do WhatsApp ---

    schedule_scraper()
