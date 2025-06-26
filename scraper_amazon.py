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

load_dotenv()

TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

print("Test Mode:", TEST_MODE)

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID_TESTE") if TEST_MODE else os.getenv("TELEGRAM_GROUP_ID")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_TESTE") if TEST_MODE else os.getenv("TELEGRAM_CHAT_ID")

# WhatsApp
# WHATSAPP_GROUP_NAME = os.getenv("WHATSAPP_GROUP_NAME_TESTE") if TEST_MODE else os.getenv("WHATSAPP_GROUP_NAME")
TOP_N_OFFERS = int(os.getenv("TOP_N_OFFERS_TESTE") if TEST_MODE else os.getenv("TOP_N_OFFERS_AMAZON"))

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
MAX_HISTORY_SIZE = 100  # Mantém as últimas promoções

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

def get_deals_with_discounts(driver):
    """Coleta descontos e links dos produtos."""
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="product-card"]'))
    )
    product_cards = driver.find_elements(By.CSS_SELECTOR, 'div[data-testid="product-card"]')
    
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
            
            # Só adiciona se o desconto for maior que 15%
            if discount > 5:
                # Extrai o link
                link_element = card.find_element(
                    By.CSS_SELECTOR, 
                    'a[data-testid="product-card-link"]'
                )
                link = link_element.get_attribute('href')
                
                deals.append({'discount': discount, 'link': link})
            
        except Exception as e:
            print(f"[Erro] Não foi possível extrair dados do produto: {e}")
    
    return deals

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

            # Constrói mensagem gradualmente
            message = "🔵 *Amazon*\n\n"
            message += f"🏷️ *{product['nome']}*\n"
            if product.get('desconto_percentual'):
                message += f"\n📉 *Desconto de {product['desconto_percentual']}% OFF*\n"
            if product.get('avaliacao'):
                message += f"\n⭐ *{product['avaliacao']}*\n"
            message += f"\n💸 *De:* {product.get('valor_original')}\n"
            message += f"\n💥 *Por apenas:* {product['valor_desconto']}"
            if product.get('parcelamento'):
                try:
                    message += "\n\n💳 *Parcelamentos:*"
                    padrao1 = re.search(r'(\d+)x de R\$\s*([\d,]+)\s*(.*)', product['parcelamento'])
                    padrao2 = re.search(r'(\d+)x\s*(.*)', product['parcelamento'])
                    padrao3 = re.search(r'.*(\d+)x.*sem juros', product['parcelamento'])
                    if padrao1:
                        qtd_parcelas = padrao1.group(1)
                        valor_parcela = f"R$ {padrao1.group(2)}"
                        status_juros = padrao1.group(3).replace("com acréscimo", "com juros")
                        message += f"\n- {qtd_parcelas}x de {valor_parcela} {status_juros}"
                    elif padrao2:
                        qtd_parcelas = padrao2.group(1)
                        status_juros = padrao2.group(2).replace("com acréscimo", "com juros")
                        message += f"\n- Em até {qtd_parcelas}x {status_juros}"
                    elif padrao3:
                        qtd_parcelas = padrao3.group(1)
                        message += f"\n- Em até {qtd_parcelas}x sem juros"
                    else:
                        message += "\n- Parcelamento disponível (ver detalhes)"
                except Exception as e:
                    print(f"Erro ao processar parcelamento: {str(e)}")
                    message += "\n- Condições de parcelamento no site"
            message += "\n\n🛒 *Garanta agora:*"
            message += f"\n🔗 {product['link']}"
            image_url = None
            if product.get('imagem'):
                if is_valid_image_url(product['imagem']):
                    image_url = product['imagem']
                else:
                    image_url = get_alternative_image(driver, product['nome'], product['link'])
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
                except Exception as e:
                    print(f"Erro ao enviar com imagem, tentando sem imagem: {e}")
                    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                    payload = {
                        'chat_id': TELEGRAM_GROUP_ID,
                        'text': message,
                        'parse_mode': 'Markdown'
                    }
                    response = requests.post(url, data=payload)
                    response.raise_for_status()
            else:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                payload = {
                    'chat_id': TELEGRAM_GROUP_ID,
                    'text': message,
                    'parse_mode': 'Markdown'
                }
                response = requests.post(url, data=payload)
                response.raise_for_status()
            print(f"Mensagem enviada: {product['nome']}")
            new_sent_products.append(product['nome'])
            time.sleep(3)
        except Exception as e:
            print(f"Falha ao enviar {product.get('nome')}: {str(e)}")

    return new_sent_products

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

    for url in product_links:
        product_info = {
            'link': None,
            'nome': None,
            'valor_desconto': None,
            'valor_original': None,
            'desconto_percentual': None,
            'avaliacao': None,
            'parcelamento': None,
            'imagem': None
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

def amazon_scraper(driver):  # Modificado para receber o driver como parâmetro
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

        driver.get("https://www.amazon.com.br/deals?ref_=nav_cs_gb")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "nav-link-accountList"))
        )

        deals = get_deals_with_discounts(driver)
        
        sorted_deals = sorted(deals, key=lambda x: x['discount'], reverse=True)
        top_n_links = [deal['link'] for deal in sorted_deals[:TOP_N_OFFERS]]
        
        return top_n_links

    except Exception as e:
        print(f"[Erro no scraper] {e}")
        return []

from time import sleep

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

    if platform.system() == 'Windows':
        service = Service(ChromeDriverManager().install())
    else:
        service = Service(executable_path="/usr/bin/chromedriver")

    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        print("🔄 Iniciando coleta de links de ofertas...")
        deal_links = amazon_scraper(driver)
        print(f"✅ Links coletados: {len(deal_links)}")

        if deal_links:
            print("🔄 Gerando links de afiliados e coletando dados dos produtos...")
            products_data = generate_affiliate_links(driver, deal_links)
            print(f"✅ Dados de {len(products_data)} produtos coletados com sucesso")

            sent_products = load_sent_products()
            novos_enviados = []

            for produto in products_data:
                # Checa e envia só se não foi enviado
                if not is_product_already_sent(produto['nome'], sent_products):
                    enviado_telegram = send_telegram_message([produto], driver, sent_products)
                    for nome_produto in enviado_telegram:
                        sent_products.append(nome_produto)
                        novos_enviados.append(nome_produto)
                        # Remove o mais antigo se passar do limite
                        if len(sent_products) > MAX_HISTORY_SIZE:
                            sent_products = sent_products[-MAX_HISTORY_SIZE:]
                    sleep(1)

            if not TEST_MODE and novos_enviados:
                save_sent_products(sent_products)
                print(f"✅ Produtos salvos: {novos_enviados}")

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
