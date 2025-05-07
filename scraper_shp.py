from datetime import datetime, timedelta
import os
import re
from tempfile import mkdtemp
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import json
from collections import deque
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from urllib.parse import urlparse, urlunparse
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import WebDriverException
import undetected_chromedriver as uc
from webdriver_manager.chrome import ChromeDriverManager
import random
import time
import requests
import schedule
import sys

sys.stdout.reconfigure(line_buffering=True)

load_dotenv()

# Verifica se está em modo de teste
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

print("Test Mode:", TEST_MODE)

# Configurações Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID_TESTE") if TEST_MODE else os.getenv("TELEGRAM_GROUP_ID")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_TESTE") if TEST_MODE else os.getenv("TELEGRAM_CHAT_ID")

# Cookies da Shopee
COOKIES = json.loads(os.getenv("SHOPEE_COOKIES", "[]"))

# Configurações
HISTORY_FILE = 'promocoes_shp.json'
MAX_HISTORY_SIZE = 30  # Mantém as últimas promoções

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
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-minimized')
    options.add_argument('--disable-blink-features=AutomationControlled')

    driver = uc.Chrome(
        options=options,
        headless=False,
        driver_executable_path=ChromeDriverManager().install()
    )

    log("Navegador stealth iniciado")
    return driver


def add_cookies(driver):
    """Adiciona cookies da Shopee"""
    try:
        log("Abrindo domínio principal para preparar os cookies...")
        driver.get("https://shopee.com.br/")
        time.sleep(random.uniform(3, 5))
        driver.delete_all_cookies()

        for cookie in COOKIES:
            try:
                driver.add_cookie(cookie)
                log(f"Cookie adicionado: {cookie['name']}")
            except Exception as e:
                log(f"Erro ao adicionar cookie {cookie['name']}: {e}")
        
        log("Recarregando página com cookies aplicados...")
        driver.get("https://shopee.com.br/")
        time.sleep(random.uniform(50, 70))

        # Verifica se o login funcionou
        if "login" in driver.current_url or "signin" in driver.current_url:
            raise Exception("Cookies inválidos ou expirados. Redirecionado para login.")
        
        log("Login via cookies bem-sucedido!")
    except Exception as e:
        log(f"ERRO ao aplicar cookies: {str(e)}")
        raise

def get_top_offers(driver):
    """Busca ofertas da Shopee priorizando: COMISSÃO > DESCONTO > VENDAS"""
    try:
        log("Acessando página de ofertas da Shopee...")
        driver.get('https://affiliate.shopee.com.br/offer/product_offer')
        time.sleep(random.uniform(5, 8))  # Delay maior para carregamento
        
        # Clica no filtro de Comissão da Marca
        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'rc-tabs-tab-btn') and contains(., 'Comissão da marca')]"))
            ).click()
            log("Filtro 'Comissão da marca' aplicado com sucesso")
            time.sleep(3)  # Espera carregar os resultados
        except Exception as e:
            log(f"Erro ao aplicar filtro de comissão: {str(e)}")

        # Scroll gradual para carregar todos os itens
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, 1000)")
            time.sleep(random.uniform(1, 2))
        
        # Coleta todos os cards de oferta
        cards = driver.find_elements(By.CSS_SELECTOR, '.product-offer-item')
        offers = []
        
        for card in cards:
            try:
                # Extrai os dados de cada card
                discount = 0
                try:
                    discount_text = card.find_element(By.CSS_SELECTOR, '.DiscountBadge__discount').text
                    discount = float(discount_text.replace('%', '').replace(',', '.'))
                except:
                    pass
                
                try:
                    sales_text = card.find_element(By.CSS_SELECTOR, '.ItemCardSold__wrap span').text
                    # Trata diferentes formatos de vendas (mil, milhões, etc.)
                    if 'mil' in sales_text:
                        sales = float(sales_text.replace('mil', '').replace('vendidos', '').replace('vendas', '').strip().replace(',', '.')) * 1000
                    elif 'mi' in sales_text:
                        sales = float(sales_text.replace('mi', '').replace('vendidos', '').replace('vendas', '').strip().replace(',', '.')) * 1000000
                    else:
                        sales = float(sales_text.replace('vendidos', '').replace('vendas', '').strip().replace(',', '.'))
                except Exception as e:
                    log(f"Erro ao converter vendas: {str(e)}")
                    sales = 0
                
                try:
                    commission_text = card.find_element(By.CSS_SELECTOR, '.commRate').text
                    commission = float(commission_text.replace('Taxa de comissão', '').replace('%', '').strip().replace(',', '.'))
                except Exception as e:
                    log(f"Erro ao converter comissão: {str(e)}")
                    commission = 0
                
                try:
                    price = card.find_element(By.CSS_SELECTOR, '.ItemCardPrice__wrap .price').text
                    title = card.find_element(By.CSS_SELECTOR, '.ItemCard__name').text
                    url = card.find_element(By.CSS_SELECTOR, 'a').get_attribute('href')
                    image_url = card.find_element(By.CSS_SELECTOR, '.ItemCard__image img').get_attribute('src')
                except Exception as e:
                    log(f"Erro ao extrair dados básicos: {str(e)}")
                    continue
                
                offers.append({
                    'title': title,
                    'url': url,
                    'discount': discount,
                    'sales': sales,
                    'commission': commission,
                    'price': price,
                    'image_url': image_url
                })
                
            except Exception as e:
                log(f"Erro ao processar card: {str(e)}")
                continue
        
        # Ordena por: COMISSÃO (maior primeiro) > DESCONTO > VENDAS
        top_offers = sorted(offers, 
                           key=lambda x: (x['commission'], x['discount'], x['sales']), 
                           reverse=True)[:5]  # Pega as top 5
        
        return top_offers
        
    except Exception as e:
        log(f"ERRO ao buscar ofertas: {str(e)}")
        return []
    
def get_product_details(driver, offer):
    """Extrai detalhes do produto da Shopee"""
    try:
        log(f"Processando produto: {offer['title']}")
        
        # Monta a mensagem com os dados já coletados
        parts = [
            f"🔥 *{offer['title']}*",
            f"📉 *Desconto:* {offer['discount']}% OFF",
            f"⭐ *Vendas:* {offer['sales']:,.0f}".replace(',', '.'),
            f"💰 *Preço:* R$ {offer['price']}",
            f"🛒 *Garanta agora:* {offer['url']}"
        ]
        
        return "\n\n".join(parts), offer['image_url']
        
    except Exception as e:
        log(f"ERRO ao processar detalhes: {str(e)}")
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
        for url in new_urls:
            log(f"Processando promoção: {url}")
            try:
                message, image_url = get_product_details(driver, url)
                if not message:
                    continue
                
                # Tenta enviar com foto se existir
                if image_url:
                    try:
                        response = requests.post(
                            f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto',
                            data={
                                'chat_id': TELEGRAM_CHAT_ID,
                                'caption': message,
                                'parse_mode': 'Markdown'
                            },
                            files={'photo': requests.get(image_url).content}
                        )
                        if response.status_code == 200:
                            sent_promotions.append(normalize_url(url))
                            save_promo_history(sent_promotions)
                            continue
                    except Exception as e:
                        log(f"Erro ao enviar com foto: {str(e)}")
                
                # Se falhar ou não tiver foto, envia apenas o texto
                response = requests.post(
                    f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
                    data={
                        'chat_id': TELEGRAM_CHAT_ID,
                        'text': message,
                        'parse_mode': 'Markdown',
                        'disable_web_page_preview': False
                    }
                )
                
                if response.status_code == 200:
                    sent_promotions.append(normalize_url(url))
                else:
                    log(f"Erro ao enviar mensagem: {response.text}")
            
            except Exception as e:
                log(f"Erro no processamento da promoção: {str(e)}")
        
    except Exception as e:
        log(f"ERRO durante a verificação: {str(e)}")
    finally:
        if driver:
            log("Fechando o navegador...")
            driver.quit()

def get_last_message_time():
    """Obtém o timestamp da última mensagem enviada pelo bot no chat/canal"""
    try:
        response = requests.get(
            f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates',
            params={'limit': 20}  # Pega as últimas 20 atualizações
        )

        if response.status_code == 200:
            data = response.json()
            for update in reversed(data.get('result', [])):
                message = update.get('channel_post') or update.get('message')
                if not message:
                    continue

                chat_id = message.get("chat", {}).get("id")
                if chat_id != int(TELEGRAM_CHAT_ID):
                    continue

                # Para canais, a mensagem vem de "channel_post" e não tem 'from'
                if 'channel_post' in update or (message.get("from", {}).get("id") == 7809229983):
                    timestamp = message.get("date")
                    if timestamp:
                        log(f"Última mensagem do bot encontrada em {datetime.fromtimestamp(timestamp)}")
                        return timestamp

        log("Nenhuma mensagem anterior encontrada neste chat")
        return None

    except Exception as e:
        log(f"Erro ao buscar última mensagem: {str(e)}")
        return None

def safe_check_promotions():
    """Verifica o intervalo de 3 horas desde a última mensagem"""
    last_sent_timestamp = get_last_message_time()

    if last_sent_timestamp:
        last_sent_time = datetime.fromtimestamp(last_sent_timestamp)
        now = datetime.now()
        time_diff = now - last_sent_time
        remaining = timedelta(hours=3) - time_diff

        # Formatação legível para tempo decorrido
        elapsed_parts = []
        if time_diff.days > 0:
            elapsed_parts.append(f"{time_diff.days}d")
        if time_diff.seconds >= 3600:
            elapsed_parts.append(f"{time_diff.seconds // 3600}h")
        if (time_diff.seconds % 3600) >= 60:
            elapsed_parts.append(f"{(time_diff.seconds % 3600) // 60}min")
        if (time_diff.seconds % 60) > 0:
            elapsed_parts.append(f"{time_diff.seconds % 60}s")
        elapsed_str = " ".join(elapsed_parts)

        # Formatação legível para tempo restante
        remaining_parts = []
        if remaining.total_seconds() > 0:
            if remaining.days > 0:
                remaining_parts.append(f"{remaining.days}d")
            if remaining.seconds >= 3600:
                remaining_parts.append(f"{remaining.seconds // 3600}h")
            if (remaining.seconds % 3600) >= 60:
                remaining_parts.append(f"{(remaining.seconds % 3600) // 60}min")
            if (remaining.seconds % 60) > 0:
                remaining_parts.append(f"{remaining.seconds % 60}s")
            remaining_str = " ".join(remaining_parts)
        else:
            remaining_str = "0s"

        log(f"Última mensagem foi há {elapsed_str}. Aguardando mais {remaining_str} para completar 3h.")
        if remaining.total_seconds() > 0:
            return

    check_promotions()
    save_promo_history(sent_promotions)

def should_run_bot(min_interval_hours=1):
    """Verifica se já passou o tempo mínimo desde a última execução"""
    last_time = get_last_message_time()
    
    if not last_time:  # Se não encontrou mensagens anteriores
        print("Nenhuma mensagem encontrada. Executando imediatamente...")
        return True
    
    current_time = int(time.time())
    time_diff = current_time - last_time  # Diferença em segundos
    min_interval_seconds = min_interval_hours * 3600
    
    if time_diff >= min_interval_seconds:
        return True
    
    # Calcula quanto tempo falta para a próxima execução
    print("Tempo restante para próxima verificação:", time_diff, "segundos")
    remaining_time = min_interval_seconds - time_diff
    log(f"Aguardando {remaining_time//60} minutos para próxima verificação (intervalo mínimo: {min_interval_hours}h)")
    return False

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