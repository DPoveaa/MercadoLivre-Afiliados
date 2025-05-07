import time
import os
import json
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import requests
import re
from datetime import datetime

load_dotenv()

cookies_env = os.getenv('AMAZON_COOKIES')
amazon_cookies = json.loads(cookies_env)

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

def send_telegram_message(products):
    """Envia os resultados formatados para o Telegram com imagem"""
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    CHAT_ID = os.getenv('TELEGRAM_CHAT_ID_TESTE')
    
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Variáveis de ambiente do Telegram não configuradas!")
        return

    for product in products:
        try:
            # Verifica campos mínimos obrigatórios
            if not product.get('nome') or not product.get('valor_desconto') or not product.get('link'):
                print(f"Produto inválido: {product.get('nome')}")
                continue

            # Constrói mensagem gradualmente
            message = "🔵 <b>Amazon</b>\n\n"
            message += f"🔥 {product['nome']}\n"

            # Adiciona desconto se disponível
            if product.get('desconto_percentual'):
                message += f"\n📉 Desconto de {product['desconto_percentual']}% OFF\n"

            # Adiciona avaliação se disponível
            if product.get('avaliacao'):
                avaliacao = product['avaliacao'].replace(',', '.')
                message += f"\n⭐ Avaliação: {avaliacao}\n"

            # Adiciona preços
            message += f"\n💸 De: {product.get('valor_original')}\n"
            message += f"\n💥 Por apenas: {product['valor_desconto']}\n"

            message += "\n💳 Parcelamentos:"
            if product.get('parcelamento'):
                try:
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
            else:
                message += "\n- Não disponível"
            # Link final
            message += "\n\n🛒 Garanta agora:"
            message += f"\n🔗 {product['link']}"

            # Envio com imagem ou sem
            if product.get('imagem'):
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
                payload = {
                    'chat_id': CHAT_ID,
                    'photo': product['imagem'],
                    'caption': message,
                    'parse_mode': 'HTML'
                }
            else:
                url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                payload = {
                    'chat_id': CHAT_ID,
                    'text': message,
                    'parse_mode': 'HTML'
                }
            
            response = requests.post(url, data=payload)
            response.raise_for_status()
            
            print(f"Mensagem enviada: {product['nome']}")
            time.sleep(3)

        except Exception as e:
            print(f"Falha ao enviar {product.get('nome')}: {str(e)}")

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
                product_info['avaliacao'] = driver.find_element(
                    By.CSS_SELECTOR, "#averageCustomerReviews .a-icon-alt"
                ).get_attribute("textContent").split()[0].replace(',', '.')
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
    try:
        # Carrega cookies do .env
        cookies_env = os.getenv('AMAZON_COOKIES')
        if not cookies_env:
            raise ValueError("Variável AMAZON_COOKIES não encontrada no .env")
            
        amazon_cookies = json.loads(cookies_env)

        driver.get("https://www.amazon.com.br")
        driver.delete_all_cookies()

        if not isinstance(amazon_cookies, list):
            raise ValueError("Formato inválido para cookies")

        for cookie in amazon_cookies:
            try:
                secure = cookie.get('secure', False)
                if isinstance(secure, str):
                    secure = secure.lower() == 'true'

                http_only = cookie.get('httpOnly', False)
                if isinstance(http_only, str):
                    http_only = http_only.lower() == 'true'

                # Converte expiry para formato numérico se necessário
                expiry = cookie.get('expiry')
                if expiry and isinstance(expiry, str):
                    expiry = int(datetime.fromisoformat(expiry[:-1]).timestamp())

                driver.add_cookie({
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'domain': cookie['domain'],
                    'path': cookie['path'],
                    'secure': secure,
                    'httpOnly': http_only,
                    'expiry': expiry
                })
            except Exception as e:
                print(f"Erro ao adicionar cookie {cookie.get('name')}: {str(e)}")

        driver.get("https://www.amazon.com.br/deals?ref_=nav_cs_gb")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "nav-link-accountList"))
        )

        deals = get_deals_with_discounts(driver)
        
        sorted_deals = sorted(deals, key=lambda x: x['discount'], reverse=True)
        top_5_links = [deal['link'] for deal in sorted_deals[:5]]
        
        return top_5_links

    except Exception as e:
        print(f"[Erro no scraper] {e}")
        return []

if __name__ == "__main__":
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")

    service = Service(executable_path="/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        deal_links = amazon_scraper(driver)
        print(f"Links coletados: {len(deal_links)}")
        
        if deal_links:
            products_data = generate_affiliate_links(driver, deal_links)
            print("Dados coletados:", products_data)
            
            # Envia para o Telegram
            send_telegram_message(products_data)

    finally:
        driver.quit()