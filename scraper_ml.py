from datetime import datetime, timedelta
import os
import re
import shlex
from tempfile import mkdtemp
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from Telegram.tl_enviar import send_telegram_message
import json
from collections import deque
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from urllib.parse import urlparse, urlunparse
from selenium.common.exceptions import NoSuchElementException
import platform
from selenium.common.exceptions import WebDriverException
import undetected_chromedriver as uc
from webdriver_manager.chrome import ChromeDriverManager
import subprocess
import random
import time
import requests
import schedule
import sys

sys.stdout.reconfigure(line_buffering=True)

load_dotenv()

# Verifica se está em modo de teste
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID_TESTE") if TEST_MODE else os.getenv("TELEGRAM_GROUP_ID")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_TESTE") if TEST_MODE else os.getenv("TELEGRAM_CHAT_ID")

# WhatsApp
WHATSAPP_GROUP_NAME = os.getenv("WHATSAPP_GROUP_NAME_TESTE") if TEST_MODE else os.getenv("WHATSAPP_GROUP_NAME")

# Cookies do Mercado Livre
COOKIES = json.loads(os.getenv("ML_COOKIES"))

# Configurações gerais
HISTORY_FILE = 'promocoes_ml.json'
MAX_HISTORY_SIZE = 30  # Mantém as últimas promoções
TOP_N_OFFERS = int(os.getenv("TOP_N_OFFERS_TESTE") if TEST_MODE else os.getenv("TOP_N_OFFERS"))

def normalize_url(url):
    try:
        parsed = urlparse(url)
        clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        return clean_url
    except:
        return url
    
# Função para carregar o histórico de promoções
def load_promo_history():
    try:
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
            # Normaliza tudo na leitura
            history = [normalize_url(url) for url in history]
            return deque(history, maxlen=MAX_HISTORY_SIZE)
    except (FileNotFoundError, json.JSONDecodeError):
        return deque(maxlen=MAX_HISTORY_SIZE)

# Função para salvar o histórico
def save_promo_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(list(history), f)

# Variável global para armazenar promoções já enviadas
sent_promotions = load_promo_history()

def log(message):
    """Função para logging com timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def init_driver():
    log("Inicializando navegador com undetected-chromedriver...")

    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--window-size=1920,1080')
    options.add_argument("--start-minimized")
    options.add_argument('--disable-blink-features=AutomationControlled')
    
    # Configurações específicas por sistema operacional
    if platform.system() == 'Linux':
        # Caminhos padrão para Linux
        browser_executable_path = '/usr/bin/google-chrome'  # ou '/usr/bin/chromium-browser'
        if not os.path.exists(browser_executable_path):
            # Tenta encontrar o Chrome em outros locais comuns no Linux
            browser_executable_path = '/usr/bin/chromium-browser' if os.path.exists('/usr/bin/chromium-browser') else None
    else:
        # Windows - geralmente o Chrome está no PATH
        browser_executable_path = None
    
    try:
        driver = uc.Chrome(
            options=options,
            headless=False,
            driver_executable_path=ChromeDriverManager().install(),
            browser_executable_path=browser_executable_path
        )
        log("Navegador stealth iniciado")
        return driver
    except Exception as e:
        log(f"Erro ao iniciar o navegador: {str(e)}")
        # Tentativa alternativa sem especificar o caminho do navegador
        try:
            driver = uc.Chrome(
                options=options,
                headless=False,
                driver_executable_path=ChromeDriverManager().install()
            )
            log("Navegador stealth iniciado (sem browser_executable_path)")
            return driver
        except Exception as e2:
            log(f"Erro na tentativa alternativa: {str(e2)}")
            raise

def send_to_whatsapp(message, group_name, image_url=""):
    """Envia mensagem com retentativas e autenticação se necessário"""
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            args = [
                "node",
                os.path.join("Whatsapp", "wpp_enviar.js"),
                message,
                group_name,
                image_url
            ]
            
            subprocess.run(args, check=True)
            log("Mensagem enviada via WhatsApp com sucesso")
            return True
            
        except subprocess.CalledProcessError as e:
            log(f"Erro ao enviar (tentativa {attempt}/{max_attempts}): {str(e)}")
            
            if attempt < max_attempts:
                # Tenta autenticar antes de nova tentativa
                try:
                    run_whatsapp_auth()
                except Exception as auth_error:
                    log(f"Falha na reautenticação: {str(auth_error)}")
                    break
                    
    return False

def run_whatsapp_auth():
    """Executa o processo de autenticação do WhatsApp"""
    log("Iniciando autenticação do WhatsApp...")
    auth_args = [
        "node",
        os.path.join("Whatsapp", "wpp_auth.js")
    ]
    
    try:
        # Executa o auth e aguarda conclusão
        subprocess.run(auth_args, check=True, timeout=300)  # 10 minutos para autenticar
        log("Autenticação do WhatsApp concluída com sucesso!")
        
    except subprocess.CalledProcessError as e:
        log(f"Falha na autenticação: {str(e)}")
        raise Exception("Erro crítico na autenticação do WhatsApp")
        
    except subprocess.TimeoutExpired:
        log("Tempo excedido para autenticação do WhatsApp")
        raise Exception("Timeout na autenticação")

def add_cookies(driver):
    """Adiciona cookies com verificação"""
    try:
        driver.get('https://www.mercadolivre.com.br')
        time.sleep(random.uniform(2, 4))
        
        # Limpa cookies antigos
        driver.delete_all_cookies()
        
        for cookie in COOKIES:
            try:
                # Verifica se o domínio está correto
                if 'mercadolivre.com.br' in cookie['domain']:
                    driver.add_cookie(cookie)
                    log(f"Cookie {cookie['name']} adicionado")
                    time.sleep(0.5)
            except Exception as e:
                log(f"Erro ao adicionar cookie {cookie['name']}: {str(e)}")
        
        # Verifica login
        driver.refresh()
        time.sleep(random.uniform(2, 4))
        if "Login" in driver.title:
            raise Exception("Falha no login - cookies inválidos")
            
    except Exception as e:
        log(f"ERRO crítico nos cookies: {str(e)}")
        raise

def get_top_offers(driver):
    """Busca ofertas com delays aleatórios"""
    try:
        log("Acessando página de ofertas...")
        driver.get('https://www.mercadolivre.com.br/ofertas')
        time.sleep(random.uniform(3, 6))  # Delay aleatório
        
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.andes-card.poly-card'))
        )
        
        # Scroll gradual para simular comportamento humano
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, 5000)")
            time.sleep(random.uniform(0.5, 1.5))
        
        cards = driver.find_elements(By.CSS_SELECTOR, '.andes-card.poly-card')
        offers = []
        
        for card in cards[:20]:
            try:
                time.sleep(random.uniform(0.2, 0.7))  # Delay entre cards
                discount_element = card.find_element(By.CSS_SELECTOR, '.andes-money-amount__discount')
                discount = float(discount_element.text.replace('% OFF', ''))
                link = card.find_element(By.CSS_SELECTOR, 'a.poly-component__title').get_attribute('href')
                offers.append({'discount': discount, 'url': link})
            except Exception:
                continue
        
        top_offers = sorted(offers, key=lambda x: x['discount'], reverse=True)[:TOP_N_OFFERS]
        return [offer['url'] for offer in top_offers]
    
    except Exception as e:
        log(f"ERRO ao buscar ofertas: {str(e)}")
        return []
    
def get_product_details(driver, url, max_retries=3):
    """Extrai detalhes do produto com tentativas em caso de erro"""
    for attempt in range(1, max_retries + 1):
        try:
            log(f"Tentativa {attempt} para extrair produto: {url}")
            driver.get(url)
            time.sleep(random.uniform(3, 5))

            # Extrai link de afiliado
            affiliate_link = ""
            try:
                generate_button = driver.find_element(By.CSS_SELECTOR, 'button[data-testid="generate_link_button"]')
                generate_button.click()
                time.sleep(random.uniform(1.5, 2.5))
                for _ in range(50):
                    textarea = driver.find_element(By.CSS_SELECTOR, 'textarea[data-testid="text-field__label_link"]')
                    if textarea.get_attribute("value"):
                        affiliate_link = textarea.get_attribute("value").strip()
                        break
                    time.sleep(random.uniform(0.5, 1.5))
            except Exception as e:
                log(f"Não foi possível extrair link de afiliado: {e}")

            # Título do produto
            product_title = driver.find_element(By.CSS_SELECTOR, "h1.ui-pdp-title").text

            # Tipo de promoção
            promotion_type = ""
            for tag in driver.find_elements(By.CLASS_NAME, "ui-pdp-promotions-pill-label"):
                txt = tag.text.upper()
                if "OFERTA DO DIA" in txt:
                    promotion_type = "🔥 *OFERTA DO DIA*"
                    break
                if "OFERTA RELÂMPAGO" in txt:
                    promotion_type = "⚡ *OFERTA RELÂMPAGO*"
                    break

            # Avaliações
            rating, rating_count = "Sem avaliações", ""
            try:
                rev = driver.find_element(By.CLASS_NAME, "ui-pdp-review__label")
                rating = rev.find_element(By.CLASS_NAME, "ui-pdp-review__rating").text.strip()
                rating_count = rev.find_element(By.CLASS_NAME, "ui-pdp-review__amount").text.strip().strip('()')
            except:
                pass

            # Preços
            def parse_price(selector):
                try:
                    block = driver.find_element(By.CSS_SELECTOR, selector)
                    frac = block.find_element(By.CLASS_NAME, "andes-money-amount__fraction").text
                    cents = block.find_elements(By.CLASS_NAME, "andes-money-amount__cents")
                    cents_text = cents[0].text if cents else "00"
                    return f"{frac},{cents_text}"
                except NoSuchElementException:
                    return None

            original_price = parse_price(".ui-pdp-price__original-value")
            current_price = parse_price(".ui-pdp-price__second-line") or "Preço não encontrado"

            # Desconto
            try:
                discount_text = driver.find_element(By.CSS_SELECTOR, ".andes-money-amount__discount").text
            except:
                discount_text = ""

            # Cupom
            coupon_message = ""
            try:
                cup = driver.find_element(By.CSS_SELECTOR, ".ui-pdp-promotions-label__text").text
                m = re.search(r"(\d+%|R\$\d+)\s+OFF", cup)
                if m:
                    coupon_message = f"🎟️ Cupom de {m.group(0)} disponível nesta compra!"
            except:
                pass

            # Imagem — força retry se vazio
            image_url = driver.find_element(
                By.CSS_SELECTOR, ".ui-pdp-image.ui-pdp-gallery__figure__image"
            ).get_attribute("src")
            if not image_url:
                raise Exception("Imagem não encontrada")
            
            # Parcelamento — tenta sempre coletar Mercado Pago e o 1º bloco de "Outros cartões"
            installment_lines = []
            try:
                pay_link_elem = driver.find_element(
                    By.XPATH, "//a[contains(text(), 'Ver os meios de pagamento')]"
                )
                pay_link = pay_link_elem.get_attribute("href")
                driver.get(pay_link)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".ui-pdp-container__row--credit-card"))
                )
                container = driver.find_element(By.CSS_SELECTOR, ".ui-pdp-container__row--credit-card")
                titles = container.find_elements(By.CSS_SELECTOR, "p.ui-vip-payment_methods__title")

                found_others = False
                captured_others = False

                for title in titles:
                    full_text = title.text.strip()
                    lower = full_text.lower()

                    if "mercado pago" in lower:
                        label = "*Com Mercado Pago*"
                    elif not captured_others:
                        label = "*Outros cartões*"
                        # Se for "sem juros", marcar prioridade
                        if "sem juros" in lower:
                            found_others = True
                            captured_others = True
                        elif not found_others:
                            # salva com juros, mas só se ainda não temos "sem juros"
                            captured_others = True
                        else:
                            continue
                    else:
                        continue

                    info = (
                        full_text
                        .replace("Até ", "")
                        .replace("com cartão Mercado Pago", "")
                        .replace("com estes cartões", "")
                        .replace("Ou até ", "")
                        .strip()
                    )

                    installment_lines.append(f"- {label}: {info}")

                driver.back()
                time.sleep(1)
            except Exception as e:
                log(f"Erro ao coletar parcelamento diretamente: {e}")
                raise

            installment_text = (
                "💳 *Parcelamentos:*\n" + "\n".join(installment_lines)
                if installment_lines else ""
            )

            # Monta mensagem final
            parts = [f"🟡 *Mercado Livre*", f"🔥 *{product_title[:150]}*"]
            if promotion_type:
                parts.append(
                    f"{promotion_type} - *{discount_text.upper()}!* 📉"
                    if discount_text else promotion_type
                )
            elif discount_text:
                parts.append(f"📉 *Desconto de {discount_text}*")
            if rating:
                parts.append(
                    f"⭐ *{rating}* ({rating_count} avaliações)"
                    if rating_count else f"⭐ *{rating}*"
                )
            if original_price:
                parts.append(f"💸 *De:* R$ {original_price}")
            if current_price and "não encontrado" not in current_price.lower():
                parts.append(f"💥 *Por apenas:* R$ {current_price}")
            if installment_text:
                parts.append(installment_text)
            if coupon_message:
                parts.append(coupon_message)

            final_url = affiliate_link or url
            parts.append(f"🛒 *Garanta agora:*\n🔗 {final_url}")

            return "\n\n".join(parts), image_url

        except Exception as e:
            log(f"Erro ao extrair detalhes (tentativa {attempt}/{max_retries}): {e}")
            time.sleep(random.uniform(2, 4))

    log(f"Falha definitiva ao extrair dados do produto após {max_retries} tentativas: {url}")
    return None, None

def check_promotions():
    """Função principal que verifica as promoções"""
    log("Iniciando verificação de promoções...")
    driver = None
    try:
        driver = init_driver()
        add_cookies(driver)

        product_urls = get_top_offers(driver)
        if not product_urls:
            log("Nenhuma oferta encontrada")
            return

        new_urls = [url for url in product_urls if normalize_url(url) not in [normalize_url(u) for u in sent_promotions]]
        if not new_urls:
            log("Nenhuma nova promoção encontrada")
            return
        
        log(f"{len(new_urls)} novas promoções encontradas")

        run_whatsapp_auth()
        for url in new_urls:
            log(f"Processando promoção: {url}")
            try:
                message, image_url = get_product_details(driver, url)
                if not message:
                    continue

                # Envia para Telegram
                telegram_success = True
                if image_url:
                    try:
                        telegram_success = send_telegram_message(
                            message=message,
                            image_url=image_url,
                            bot_token=TELEGRAM_BOT_TOKEN,
                            chat_id=TELEGRAM_GROUP_ID
                        )
                    except Exception as e:
                        log(f"Erro ao enviar com foto para Telegram: {str(e)}")

                # Envia para WhatsApp se o Telegram foi bem sucedido
                if telegram_success:
                    print("✅ Mensagem enviada com sucesso para Telegram!")
                    grupo_nome = "Grupo Teste"  # Substitua se necessário
                    args = [
                        "node",
                        os.path.join("Whatsapp", "wpp_enviar.js"),
                        message,
                        grupo_nome,
                        image_url or ""
                    ]
                    subprocess.run(args, check=True)
                    print("✅ Mensagem enviada com sucesso para WhatsApp!")
                    save_promo_history(sent_promotions)
                else:
                    log("Falha ao enviar para Telegram - Pulando WhatsApp")

            except Exception as e:
                log(f"Erro no processamento da promoção: {str(e)}")

    except Exception as e:
        log(f"ERRO durante a verificação: {str(e)}")
    finally:
        if driver:
            log("Fechando o navegador...")
            driver.quit()

# Loop principal
print("Bot iniciado.")
check_promotions()
schedule.every(1).hours.do(check_promotions)
print("Agendado para verificar promoções a cada 1 hora.")
log("Bot iniciado. Pressione Ctrl+C para parar.")
try:
    while True:
        schedule.run_pending()
        time.sleep(3600)
except KeyboardInterrupt:
    log("Bot encerrado pelo usuário")