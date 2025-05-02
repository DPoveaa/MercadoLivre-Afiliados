from datetime import datetime, timedelta
import re
from tempfile import mkdtemp
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

# Configurações
TELEGRAM_BOT_TOKEN = '7809229983:AAGBphj2suFOzCeQOjhNNEnqDeb7aihMYpE'
TELEGRAM_CHAT_ID = '-1002388728835'  # Substitua pelo seu chat ID
ML_AFFILIATE_LABEL = 'centraldedescontos - 61832902'
# Configurações
HISTORY_FILE = 'promocoes.json'
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

# Seus cookies (mantenha apenas os essenciais)
COOKIES = [
    {
        'name': 'ssid',
        'value': 'ghy-031520-CF5Vo8lWETRIi9hxUUMNcXwaXGlrEE-__-215094442-__-1836778381683--RRR_0-RRR_0',
        'domain': '.mercadolivre.com.br'
    },
    {
        'name': 'orguseridp',
        'value': '215094442',
        'domain': '.mercadolivre.com.br'
    },
    {
        'name': 'x-meli-session-id',
        'value': 'armor.46cf731c3b610b5a51103c97ababe935374a33fbdc5cbde14cccb2697c9c9916d5fc0da6c4ff1fee4dfb7625006a0c6694932ba025be9c9eb9ebaea324684dc58f1bac64cc4169032c9d745553c917376d5c5da5b73976f44389e6195cb08702.b00cb4ad04be08a8e92dc83f0253fcb0',
        'domain': '.mercadolivre.com.br'
    }
]

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
    # NÃO USE --headless AQUI!

    driver = uc.Chrome(
    options=options,
    headless=False,
    driver_executable_path=ChromeDriverManager().install(),
    browser_executable_path="/usr/bin/google-chrome"  # ou "/usr/bin/chromium-browser"
    )
    log("Navegador stealth iniciado")
    return driver

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
        
        top_offers = sorted(offers, key=lambda x: x['discount'], reverse=True)[:5]
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
            parts = [f"🔥 *{product_title[:150]}*"]
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

safe_check_promotions()
# Loop principal
schedule.every(3).hours.do(safe_check_promotions)
print("Agendado para verificar promoções a cada 3 hora.")
log("Bot iniciado. Pressione Ctrl+C para parar.")
try:
    while True:
        schedule.run_pending()
        time.sleep(10800)
except KeyboardInterrupt:
    log("Bot encerrado pelo usuário")