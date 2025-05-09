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
import mimetypes
import subprocess

import schedule

load_dotenv()

TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

WHATSAPP_GROUP_NAME = os.getenv("WHATSAPP_GROUP_NAME_TESTE") if TEST_MODE else os.getenv("WHATSAPP_GROUP_NAME")

# Load cookies from environment variable
COOKIES_JSON = os.getenv('AMAZON_COOKIES')
if not COOKIES_JSON:
    raise ValueError("AMAZON_COOKIES environment variable not found in .env file")

try:
    COOKIES = json.loads(COOKIES_JSON)
except json.JSONDecodeError as e:
    raise ValueError(f"Invalid JSON in AMAZON_COOKIES: {e}")

def is_similar(a: str, b: str, thresh: float = 0.95) -> bool:
    """Compare two strings and return True if they are similar above the threshold."""
    score = SequenceMatcher(None, a, b).ratio()
    return score >= thresh

def load_sent_products():
    """Load the list of previously sent products from JSON file."""
    try:
        if os.path.exists('produtos_amazon.json'):
            with open('produtos_amazon.json', 'r', encoding='utf-8') as f:
                products = json.load(f)
                # Verifica se precisa limpar o arquivo
                if len(products) >= 30:
                    print("Limite de 30 produtos atingido. Limpando arquivo...")
                    return []
                return products
        return []
    except Exception as e:
        print(f"Erro ao carregar produtos enviados: {e}")
        return []

def save_sent_products(products):
    """Save the list of sent products to JSON file."""
    try:
        # Verifica se atingiu o limite antes de salvar
        if len(products) >= 30:
            print("Limite de 30 produtos atingido. Limpando arquivo...")
            products = []
            
        with open('produtos_amazon.json', 'w', encoding='utf-8') as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar produtos enviados: {e}")

def is_product_already_sent(product_name, sent_products):
    """Check if a product has already been sent by comparing names."""
    for sent_product in sent_products:
        if is_similar(product_name, sent_product):
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
            discount = int(discount_text.split('%')[0].strip())  # Extrai o valor numérico
            
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

def get_alternative_image(driver, product_name):
    """Tenta obter uma imagem alternativa do produto."""
    try:
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

def send_telegram_message(products, driver):
    """Envia os resultados formatados para o Telegram com imagem"""
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    CHAT_ID = os.getenv('TELEGRAM_CHAT_ID_TESTE')
    
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Variáveis de ambiente do Telegram não configuradas!")
        return []

    # Load previously sent products
    sent_products = load_sent_products()
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
            message += f"🔥 *{product['nome']}*\n"

            # Adiciona desconto se disponível
            if product.get('desconto_percentual'):
                message += f"\n📉 *Desconto de {product['desconto_percentual']}% OFF*\n"

            # Adiciona avaliação se disponível
            if product.get('avaliacao'):
                message += f"\n⭐ *{product['avaliacao']}*\n"

            # Adiciona preços
            message += f"\n💸 *De:* {product.get('valor_original')}\n"
            message += f"\n💥 *Por apenas:* {product['valor_desconto']}"

            if product.get('parcelamento'):
                try:
                    message += "\n💳 *Parcelamentos:*"
                    # Padrão 1: "12x de R$ 46,62 sem juros"
                    padrao1 = re.search(r'(\d+)x de R\$\s*([\d,]+)\s*(.*)', product['parcelamento'])
                    
                    # Padrão 2: "Em até 12x sem juros"
                    padrao2 = re.search(r'(\d+)x\s*(.*)', product['parcelamento'])
                    
                    # Padrão 3: Valor total + parcelamento
                    padrao3 = re.search(r'.*(\d+)x.*sem juros', product['parcelamento'])

                    if padrao1:
                        qtd_parcelas = padrao1.group(1)
                        valor_parcela = f"R$ {padrao1.group(2)}"
                        status_juros = padrao1.group(3)
                        message += f"\n- {qtd_parcelas}x de {valor_parcela} {status_juros}"
                    elif padrao2:
                        qtd_parcelas = padrao2.group(1)
                        status_juros = padrao2.group(2)
                        message += f"\n- Em até {qtd_parcelas}x {status_juros}"
                    elif padrao3:
                        qtd_parcelas = padrao3.group(1)
                        message += f"\n- Em até {qtd_parcelas}x sem juros"
                    else:
                        message += "\n- Parcelamento disponível (ver detalhes)"
                        
                except Exception as e:
                    print(f"Erro ao processar parcelamento: {str(e)}")
                    message += "\n- Condições de parcelamento no site"

            # Link final
            message += "\n\n🛒 *Garanta agora:*"
            message += f"\n🔗 {product['link']}"

            # Verifica e processa a imagem
            image_url = None
            if product.get('imagem'):
                if is_valid_image_url(product['imagem']):
                    image_url = product['imagem']
                else:
                    # Tenta obter uma imagem alternativa
                    image_url = get_alternative_image(driver, product['nome'])

            # Envio com imagem ou sem
            if image_url:
                try:
                    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
                    payload = {
                        'chat_id': CHAT_ID,
                        'photo': image_url,
                        'caption': message,
                        'parse_mode': 'Markdown'
                    }
                    response = requests.post(url, data=payload, timeout=10)
                    response.raise_for_status()
                except Exception as e:
                    print(f"Erro ao enviar com imagem, tentando sem imagem: {e}")
                    # Fallback para envio sem imagem
                    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                    payload = {
                        'chat_id': CHAT_ID,
                        'text': message,
                        'parse_mode': 'Markdown'
                    }
                    response = requests.post(url, data=payload)
                    response.raise_for_status()
            else:
                # Envio sem imagem
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                payload = {
                    'chat_id': CHAT_ID,
                    'text': message,
                    'parse_mode': 'Markdown'
                }
                response = requests.post(url, data=payload)
                response.raise_for_status()
            
            print(f"Mensagem enviada: {product['nome']}")
            # Add product to new sent products list
            new_sent_products.append(product['nome'])
            time.sleep(3)

        except Exception as e:
            print(f"Falha ao enviar {product.get('nome')}: {str(e)}")

    return new_sent_products

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
                price_block = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "corePriceDisplay_desktop_feature_div"))
                )
                whole = price_block.find_element(By.CSS_SELECTOR, "span.a-price-whole").text.strip().replace('.', '')
                fraction = price_block.find_element(By.CSS_SELECTOR, "span.a-price-fraction").text.strip()
                product_info['valor_desconto'] = f"R$ {whole},{fraction}"
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
                    By.CSS_SELECTOR, "span.a-price.a-text-price span.a-offscreen"
                ).get_attribute("textContent").strip()
                product_info['valor_original'] = original
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
        top_n_links = [deal['link'] for deal in sorted_deals[:1]]
        
        return top_n_links

    except Exception as e:
        print(f"[Erro no scraper] {e}")
        return []

def send_whatsapp_message(products, driver):
    """Envia os resultados formatados para o WhatsApp com imagem"""
    if not WHATSAPP_GROUP_NAME:
        print("Variável de ambiente WHATSAPP_GROUP_NAME não configurada!")
        return []

    # Load previously sent products
    sent_products = load_sent_products()
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
            message += f"🔥 *{product['nome']}*\n"

            # Adiciona desconto se disponível
            if product.get('desconto_percentual'):
                message += f"\n📉 *Desconto de {product['desconto_percentual']}% OFF*\n"

            # Adiciona avaliação se disponível
            if product.get('avaliacao'):
                message += f"\n⭐ *{product['avaliacao']}*\n"

            # Adiciona preços
            message += f"\n💸 *De:* {product.get('valor_original')}\n"
            message += f"\n💥 *Por apenas:* {product['valor_desconto']}\n"

            if product.get('parcelamento'):
                try:
                    message += "\n💳 *Parcelamentos:*"
                    # Padrão 1: "12x de R$ 46,62 sem juros"
                    padrao1 = re.search(r'(\d+)x de R\$\s*([\d,]+)\s*(.*)', product['parcelamento'])
                    
                    # Padrão 2: "Em até 12x sem juros"
                    padrao2 = re.search(r'(\d+)x\s*(.*)', product['parcelamento'])
                    
                    # Padrão 3: Valor total + parcelamento
                    padrao3 = re.search(r'.*(\d+)x.*sem juros', product['parcelamento'])

                    if padrao1:
                        qtd_parcelas = padrao1.group(1)
                        valor_parcela = f"R$ {padrao1.group(2)}"
                        status_juros = padrao1.group(3)
                        message += f"\n- {qtd_parcelas}x de {valor_parcela} {status_juros}"
                    elif padrao2:
                        qtd_parcelas = padrao2.group(1)
                        status_juros = padrao2.group(2)
                        message += f"\n- Em até {qtd_parcelas}x {status_juros}"
                    elif padrao3:
                        qtd_parcelas = padrao3.group(1)
                        message += f"\n- Em até {qtd_parcelas}x sem juros"
                    else:
                        message += "\n- Parcelamento disponível (ver detalhes)"
                        
                except Exception as e:
                    print(f"Erro ao processar parcelamento: {str(e)}")
                    message += "\n- Condições de parcelamento no site"

            # Link final
            message += "\n\n🛒 *Garanta agora:*"
            message += f"\n🔗 {product['link']}"

            # Verifica e processa a imagem
            image_url = None
            if product.get('imagem'):
                if is_valid_image_url(product['imagem']):
                    image_url = product['imagem']
                else:
                    # Tenta obter uma imagem alternativa
                    image_url = get_alternative_image(driver, product['nome'])

            # Envia para o WhatsApp
            try:
                grupo_nome = WHATSAPP_GROUP_NAME
                args = [
                    "node",
                    os.path.join("Whatsapp", "wpp_enviar.js"),
                    message,
                    grupo_nome,
                    image_url or ""
                ]
                subprocess.run(args)
                print(f"✅ Mensagem enviada para WhatsApp: {product['nome']}")
                new_sent_products.append(product['nome'])
                time.sleep(3)

            except subprocess.CalledProcessError as e:
                print(f"❌ Erro ao executar o script Node.js: {e}")

        except Exception as e:
            print(f"Falha ao enviar {product.get('nome')}: {str(e)}")

    return new_sent_products

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
    chrome_options.add_argument("--headless=new")  # Novo modo headless do Chrome

    # Configuração do ChromeDriver baseada no sistema operacional
    if platform.system() == 'Windows':
        service = Service(ChromeDriverManager().install())
    else:
        service = Service(executable_path="/usr/bin/chromedriver")

    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        deal_links = amazon_scraper(driver)
        print(f"Links coletados: {len(deal_links)}")
        
        if deal_links:
            products_data = generate_affiliate_links(driver, deal_links)
            
            # Envia para o WhatsApp e Telegram
            whatsapp_success = send_whatsapp_message(products_data, driver)
            telegram_success = send_telegram_message(products_data, driver)
            
            # Encontra produtos que foram enviados com sucesso para ambas as plataformas
            produtos_enviados = set(whatsapp_success) & set(telegram_success)
            
            # Salva apenas os produtos que foram enviados com sucesso para ambas as plataformas
            if produtos_enviados:
                sent_products = load_sent_products()
                sent_products.extend(list(produtos_enviados))
                save_sent_products(sent_products)

    except Exception as e:
        print(f"Erro durante a execução do scraper: {e}")
    finally:
        driver.quit()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Execução finalizada.")

def schedule_scraper():
    """Configura e inicia o agendamento do scraper."""
    print("Iniciando agendamento do scraper...")
    print("O scraper será executado a cada 1 hora.")
    
    # Executa imediatamente na primeira vez
    run_scraper()
    
    # Agenda para executar a cada hora
    schedule.every(1).hours.do(run_scraper)
    
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
