from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timedelta
import os
import re
import shlex
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from difflib import SequenceMatcher
from collections import deque
from Telegram.tl_enviar import send_telegram_message
import json
import unicodedata
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
import requests
import schedule
import sys
import time

def log(message):
    """Função para logging com timestamp"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

from whatsapp.wpp_connect import (
    wpp_send_message,
    wpp_check_connection_state
)

sys.stdout.reconfigure(line_buffering=True)

# Verifica se está em modo de teste
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

print("Test Mode:", TEST_MODE)

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID_TESTE") if TEST_MODE else os.getenv("TELEGRAM_GROUP_ID")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_TESTE") if TEST_MODE else os.getenv("TELEGRAM_CHAT_ID")

# WhatsApp via WPPConnect
WHATSAPP_ENABLED = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
log(f"DEBUG: WHATSAPP_ENABLED está como {WHATSAPP_ENABLED}")
WPP_BASE_URL = os.getenv("WPP_BASE_URL", "http://localhost:21465")
log(f"DEBUG: WPP_BASE_URL está como {WPP_BASE_URL}")
WPP_SESSION = os.getenv("WPP_SESSION", "default")
WPP_TOKEN = os.getenv("WPP_TOKEN", "")
WPP_SECRET_KEY = os.getenv("WPP_SECRET_KEY", "THISISMYSECURETOKEN")
WPP_TOKEN_RUNTIME = WPP_TOKEN
WPP_NODE_CMD = os.getenv("WPP_NODE_CMD", "node wpp_server.js")
WPP_SERVER_PROCESS = None

# Admins para notificação de desconexão WhatsApp
ADMIN_CHAT_IDS = [a.strip() for a in os.getenv("ADMIN_CHAT_IDS", "").split(",")] if os.getenv("ADMIN_CHAT_IDS") else []

# Cookies do Mercado Livre
COOKIES = json.loads(os.getenv("ML_COOKIES"))

# Configurações gerais
if TEST_MODE:
    print("Modo de teste ativado, salvando em promocoes_teste.json")
    HISTORY_FILE = 'promocoes_teste.json'
else:
    HISTORY_FILE = 'promocoes_ml.json'
    print("Salvando em promocoes_ml.json")

TOP_N_OFFERS = int(os.getenv("TOP_N_OFFERS_TESTE") if TEST_MODE else os.getenv("TOP_N_OFFERS"))

MAX_HISTORY_SIZE = 200  # Mantém as últimas promoções
SIMILARITY_THRESHOLD = 0.95 # Limiar de similaridade mais restritivo

# Lista de URLs fornecida
OFFER_URLS = [
    "https://www.mercadolivre.com.br/ofertas?container_id=MLB779543-1&domain_id=MLB-PERFUMES#filter_applied=domain_id&filter_position=18&is_recommended_domain=false&origin=scut",
    "https://www.mercadolivre.com.br/ofertas?container_id=MLB779540-1&domain_id=MLB-WELDING_MACHINES$MLB-TOOLS$MLB-WELDING_BLOWTORCHES$MLB-WELDING_RODS$MLB-DRILLS_SCREWDRIVERS$MLB-ELECTRIC_DRILLS$MLB-DRILL_BITS$MLB-POWER_GRINDERS$MLB-COMBINED_TOOL_SETS$MLB-ELECTRIC_CIRCULAR_SAWS$MLB-TOOL_ACCESSORIES_AND_SPARES$MLB-WRENCHES$MLB-WRENCH_SETS#filter_applied=domain_id&filter_position=15&is_recommended_domain=false&origin=scut",
    "https://www.mercadolivre.com.br/ofertas?container_id=MLB779539-1&domain_id=MLB-TELEVISIONS#filter_applied=domain_id&filter_position=14&is_recommended_domain=false&origin=scut",
    "https://www.mercadolivre.com.br/ofertas?container_id=MLB773331-2#filter_applied=container_id&filter_position=13&is_recommended_domain=false&origin=scut",
    "https://www.mercadolivre.com.br/ofertas?container_id=MLB779538-1&domain_id=MLB-HEADPHONES#filter_applied=domain_id&filter_position=12&is_recommended_domain=false&origin=scut",
    "https://www.mercadolivre.com.br/ofertas?container_id=MLB779536-1&domain_id=MLB-NOTEBOOKS#filter_applied=domain_id&filter_position=11&is_recommended_domain=false&origin=scut",
    "https://www.mercadolivre.com.br/ofertas?container_id=MLB779535-1&domain_id=MLB-CELLPHONES#filter_applied=domain_id&filter_position=10&is_recommended_domain=false&origin=scut",
    "https://www.mercadolivre.com.br/ofertas?container_id=MLB779544-1&domain_id=MLB-SWEATSHIRTS_AND_HOODIES$MLB-PANTS$MLB-JACKETS_AND_COATS$MLB-T_SHIRTS$MLB-SOCKS$MLB-MALE_UNDERWEAR$MLB-SPORTSWEAR$MLB-LEGGINGS$MLB-DRESSES$MLB-LOAFERS_AND_OXFORDS$MLB-BLOUSES$MLB-SHIRTS$MLB-WRISTWATCHES$MLB-SUNGLASSES#filter_applied=domain_id&filter_position=8&is_recommended_domain=true&origin=scut",
    "https://www.mercadolivre.com.br/ofertas?container_id=MLB779537-1&domain_id=MLB-SNEAKERS#filter_applied=domain_id&filter_position=7&is_recommended_domain=true&origin=scut",
    "https://www.mercadolivre.com.br/mais-vendidos/MLB5726#origin=home", # Eletrodomésticos
    "https://www.mercadolivre.com.br/mais-vendidos/MLB1430#origin=home", # Calçados, Roupas e Bolsas
    "https://www.mercadolivre.com.br/mais-vendidos/MLB1000#origin=home", # Eletrônicos, Áudio e Vídeo
    "https://www.mercadolivre.com.br/mais-vendidos/MLB1246#origin=home", # Beleza e Cuidado Pessoal
    "https://www.mercadolivre.com.br/mais-vendidos/MLB1648#origin=home", # Informática
    "https://www.mercadolivre.com.br/ofertas?container_id=MLB779542-1&domain_id=MLB-SPEAKERS#filter_applied=domain_id&filter_position=15&is_recommended_domain=false&origin=scut",
    "https://www.mercadolivre.com.br/ofertas?container_id=MLB779362-1&price=0.0-100.0#filter_applied=price&filter_position=6&is_recommended_domain=false&origin=scut",
    "https://www.mercadolivre.com.br/ofertas?container_id=MLB783320-1&domain_id=MLB-SUPPLEMENTS#filter_applied=domain_id&filter_position=3&is_recommended_domain=true&origin=scut"
]

# Arquivo para armazenar os links já utilizados
USED_URLS_FILE = 'used_urls_ml.json'

FORCE_RUN_ON_START = os.getenv("FORCE_RUN_ON_START", "false").lower() == "true"

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
    if len(used_urls) >= len(OFFER_URLS):
        log("Todos os links foram utilizados. Reiniciando histórico...")
        used_urls.clear()
        save_used_urls(used_urls)
    
    # Filtra apenas os links não utilizados
    available_urls = [url for url in OFFER_URLS if url not in used_urls]
    
    # Se não houver links suficientes, usa todos os links disponíveis
    num_urls = min(3, len(available_urls))
    
    # Escolhe aleatoriamente os links
    selected_urls = random.sample(available_urls, num_urls)
    
    # Adiciona os links selecionados ao histórico
    used_urls.update(selected_urls)
    save_used_urls(used_urls)
    
    log(f"Links selecionados: {len(selected_urls)} de {len(available_urls)} disponíveis")
    return selected_urls

def is_similar(a: str, b: str, thresh: float = SIMILARITY_THRESHOLD) -> bool:
    score = SequenceMatcher(None, a, b).ratio()
    return score >= thresh
    
# Função para carregar o histórico de promoções
def load_promo_history() -> deque:
    if TEST_MODE:
        # Em modo de teste, não lê arquivo algum
        return deque(maxlen=MAX_HISTORY_SIZE)
    try:
        with open(HISTORY_FILE, 'r') as f:
            nomes = json.load(f)
        return deque(nomes, maxlen=MAX_HISTORY_SIZE)
    except (FileNotFoundError, json.JSONDecodeError):
        return deque(maxlen=MAX_HISTORY_SIZE)

# Função para salvar o histórico
def save_promo_history(history: deque):
    if TEST_MODE:
        # Em modo de teste, não salva nada
        return
    with open(HISTORY_FILE, 'w') as f:
        json.dump(list(history), f)

# Variável global para armazenar promoções já enviadas
sent_promotions = load_promo_history()



def _load_whatsapp_destinations():
    test = os.getenv("TEST_MODE", "false").lower() == "true"
    destinations = []
    if test:
        groups = os.getenv("WHATSAPP_GROUPS_TESTE", "")
        channels = os.getenv("WHATSAPP_CHANNELS_TESTE", "")
    else:
        groups = os.getenv("WHATSAPP_GROUPS", "")
        channels = os.getenv("WHATSAPP_CHANNELS", "")
    if groups:
        destinations.extend([g.strip() for g in groups.split(",") if g.strip()])
    if channels:
        destinations.extend([c.strip() for c in channels.split(",") if c.strip()])
    return destinations



def init_driver():
    log("Inicializando navegador com undetected-chromedriver...")

    def build_options():
        opts = uc.ChromeOptions()
        opts.add_argument("--headless=new")
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--disable-blink-features=AutomationControlled')
        opts.add_argument('--window-size=1920,1080')
        opts.add_argument('--lang=pt-BR')
        opts.add_argument(
            '--user-agent=Mozilla/5.0 (X11; Linux x86_64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )
        return opts

    # Detecta Chrome no Linux
    browser_executable_path = None
    if platform.system() == 'Linux':
        if os.path.exists('/usr/bin/google-chrome'):
            browser_executable_path = '/usr/bin/google-chrome'
        elif os.path.exists('/usr/bin/chromium-browser'):
            browser_executable_path = '/usr/bin/chromium-browser'

    try:
        options = build_options()
        driver = uc.Chrome(
            options=options,
            driver_executable_path=ChromeDriverManager().install(),
            browser_executable_path=browser_executable_path
        )
        log("Navegador stealth iniciado")
        return driver

    except Exception as e:
        log(f"Erro ao iniciar o navegador (tentativa 1): {e}")

        # ⚠️ Nova instância de options (NUNCA reutilizar)
        try:
            options = build_options()
            driver = uc.Chrome(
                options=options,
                headless=False,
                driver_executable_path=ChromeDriverManager().install()
            )
            log("Navegador stealth iniciado (fallback)")
            return driver

        except Exception as e2:
            log(f"Erro fatal ao iniciar navegador: {e2}")
            raise

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
    """Coleta top 5 ofertas de cada URL na lista"""
    all_offers = []
    
    # Usa apenas 3 URLs rotacionadas
    urls_to_process = get_rotated_urls()
    
    for url in urls_to_process:
        try:
            log(f"\nAcessando categoria: {url}")
            driver.get(url)
            
            # Espera inicial combinada com delay
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.andes-card.poly-card'))
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
            
            # Coleta de cards
            cards = driver.find_elements(By.CSS_SELECTOR, '.andes-card.poly-card')
            log(f"Encontrados {len(cards)} produtos na categoria")
            
            # Processamento dos cards
            category_offers = []
            for card in cards:
                try:
                    discount = card.find_element(By.CSS_SELECTOR, '.andes-money-amount__discount').text.replace('% OFF', '')
                    discount_value = float(discount)
                    
                    # Só adiciona se o desconto for maior que 10%
                    if discount_value > 5:
                        link = card.find_element(By.CSS_SELECTOR, 'a.poly-component__title').get_attribute('href')
                        title = card.find_element(By.CSS_SELECTOR, 'a.poly-component__title').text.strip()
                        
                        # Verifica se já existe um produto similar na lista atual
                        if not any(is_similar(title, offer['title']) for offer in category_offers):
                            category_offers.append({
                                'discount': discount_value,
                                'url': link,
                                'title': title,
                                'category': url.split('domain_id=')[1].split('&')[0] if 'domain_id=' in url else 'unknown'
                            })
                except Exception as e:
                    continue
            
            # Seleciona top 5 da categoria
            top_category = sorted(category_offers, key=lambda x: x['discount'], reverse=True)[:TOP_N_OFFERS]
            all_offers.extend(top_category)
            
            log(f"Top {TOP_N_OFFERS} coletados: {[item['discount'] for item in top_category]}")
            
            # Intervalo aleatório entre categorias
            time.sleep(random.uniform(5, 10))
            
        except Exception as e:
            log(f"Falha na categoria {url}: {str(e)}")
            continue
    
    # Ordena todos os resultados e pega os Top N globais (se necessário)
    final_top = sorted(all_offers, key=lambda x: x['discount'], reverse=True)
    
    # Filtra produtos similares da lista final
    filtered_offers = []
    for offer in final_top:
        if not any(is_similar(offer['title'], existing['title']) for existing in filtered_offers):
            filtered_offers.append(offer)
    
    return [item['url'] for item in filtered_offers]
    
def get_product_details(driver, url, max_retries=3):
    """Extrai detalhes do produto com tentativas em caso de erro, logando cada campo individualmente"""
    for attempt in range(1, max_retries + 1):
        try:
            log(f"Tentativa {attempt} para extrair produto: {url}")
            driver.get(url)
            time.sleep(random.uniform(3, 5))

            # Extrai link de afiliado
            affiliate_link = ""
            try:
                log("Extraindo link de afiliado...")
                generate_button = driver.find_element(By.CSS_SELECTOR, 'button[data-testid="generate_link_button"]')
                generate_button.click()
                time.sleep(random.uniform(1.5, 2.5))
                for _ in range(50):
                    textarea = driver.find_element(By.CSS_SELECTOR, 'textarea[data-testid="text-field__label_link"]')
                    if textarea.get_attribute("value"):
                        affiliate_link = textarea.get_attribute("value").strip()
                        break
                    time.sleep(random.uniform(0.5, 1.5))
                if not affiliate_link:
                    raise Exception("Link de afiliado não gerado")
                log(f"Link de afiliado extraído: {affiliate_link}")
            except Exception as e:
                log(f"Erro ao extrair link de afiliado: {e}")
                if attempt < max_retries:
                    log(f"Tentar novamente... (Tentativa {attempt + 1}/{max_retries})")
                    continue
                else:
                    log("Número máximo de tentativas atingido. Pulando produto.")
                    return None, None, None

            # Título do produto
            try:
                log("Extraindo título do produto...")
                product_title = driver.find_element(By.CSS_SELECTOR, "h1.ui-pdp-title").text
                log(f"Título extraído: {product_title}")
            except Exception as e:
                log(f"Erro ao extrair título: {e}")
                product_title = None

            # Tipo de promoção
            promotion_type = ""
            try:
                log("Extraindo tipo de promoção...")
                for tag in driver.find_elements(By.CLASS_NAME, "ui-pdp-promotions-pill-label"):
                    txt = tag.text.upper()
                    if "OFERTA DO DIA" in txt:
                        promotion_type = "🔥 *OFERTA DO DIA*"
                        break
                    if "OFERTA RELÂMPAGO" in txt:
                        promotion_type = "⚡ *OFERTA RELÂMPAGO*"
                        break
                log(f"Tipo de promoção extraído: {promotion_type}")
            except Exception as e:
                log(f"Erro ao extrair tipo de promoção: {e}")

            # Avaliações
            rating, rating_count = "Sem avaliações", ""
            try:
                log("Extraindo avaliações...")
                rev = driver.find_element(By.CLASS_NAME, "ui-pdp-review__label")
                rating = rev.find_element(By.CLASS_NAME, "ui-pdp-review__rating").text.strip()
                rating_count = rev.find_element(By.CLASS_NAME, "ui-pdp-review__amount").text.strip().strip('()')
                log(f"Avaliação: {rating}, Quantidade: {rating_count}")
            except Exception as e:
                log(f"Erro ao extrair avaliações: {e}")

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
                except Exception as e:
                    log(f"Erro ao extrair preço com selector {selector}: {e}")
                    return None

            try:
                log("Extraindo preço original...")
                original_price = parse_price(".ui-pdp-price__original-value")
                log(f"Preço original: {original_price}")
            except Exception as e:
                log(f"Erro ao extrair preço original: {e}")
                original_price = None
            try:
                log("Extraindo preço atual...")
                current_price = parse_price(".ui-pdp-price__second-line") or "Preço não encontrado"
                log(f"Preço atual: {current_price}")
            except Exception as e:
                log(f"Erro ao extrair preço atual: {e}")
                current_price = None

            # Desconto
            try:
                log("Extraindo desconto...")
                discount_text = driver.find_element(By.CSS_SELECTOR, ".andes-money-amount__discount").text
                log(f"Desconto: {discount_text}")
            except Exception as e:
                log(f"Erro ao extrair desconto: {e}")
                discount_text = ""

            # Cupom
            coupon_message = ""
            try:
                log("Extraindo cupom...")
                # Tenta pelo seletor antigo
                try:
                    cup = driver.find_element(By.CSS_SELECTOR, ".ui-pdp-promotions-label__text").text
                    m = re.search(r"(\d+%|R\$\d+)\s+OFF", cup)
                    if m:
                        coupon_message = f"🎟️ Cupom disponível: {m.group(0)}."
                except Exception:
                    # Tenta pelo novo seletor
                    try:
                        # Procura o label do cupom
                        coupon_label = driver.find_element(By.CSS_SELECTOR, ".ui-vpp-coupons-awareness__checkbox-label")
                        coupon_text = coupon_label.text.strip()
                        m = re.search(r"(\d+%|R\$\d+)\s*OFF", coupon_text)
                        if m:
                            valor = m.group(0)
                            coupon_message = f"🎟️ Cupom disponível: {valor}."
                        else:
                            # Se não encontrar padrão, apenas informa que há cupom
                            coupon_message = f"🎟️ Cupom disponível."
                        # Procura o valor economizado
                        try:
                            economiza = driver.find_element(By.CSS_SELECTOR, ".ui-vpp-coupons__text").text
                            if economiza:
                                coupon_message += f" {economiza}"
                        except Exception:
                            pass
                    except Exception:
                        pass
                log(f"Cupom extraído: {coupon_message}")
            except Exception as e:
                log(f"Erro ao extrair cupom: {e}")

            # Imagem
            try:
                log("Extraindo imagem...")
                image_url = driver.find_element(
                    By.CSS_SELECTOR, ".ui-pdp-image.ui-pdp-gallery__figure__image"
                ).get_attribute("src")
                if not image_url:
                    raise Exception("Imagem não encontrada")
                log(f"Imagem extraída: {image_url}")
            except Exception as e:
                log(f"Erro ao extrair imagem: {e}")
                image_url = None

            # Parcelamento
            installment_lines = []
            try:
                log("Extraindo parcelamento...")
                # Tenta encontrar o botão/link de parcelamento por diferentes textos
                pay_link_elem = None
                # 1. "Ver os meios de pagamento"
                try:
                    pay_link_elem = driver.find_element(By.XPATH, "//a[contains(text(), 'Ver os meios de pagamento')]")
                except Exception:
                    pass
                # 2. "Ver meios de pagamento e promoções"
                if not pay_link_elem:
                    try:
                        pay_link_elem = driver.find_element(By.XPATH, "//a[contains(text(), 'Ver meios de pagamento e promoções')]")
                    except Exception:
                        pass
                # 3. genérico pelo data-testid
                if not pay_link_elem:
                    try:
                        pay_link_elem = driver.find_element(By.CSS_SELECTOR, "a.ui-pdp-action-modal__link[data-testid='action-modal-link']")
                    except Exception:
                        pass
                if pay_link_elem:
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
                            if "sem juros" in lower:
                                found_others = True
                                captured_others = True
                            elif not found_others:
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
                            .replace("com acréscimo", "com juros")
                            .strip()
                        )

                        installment_lines.append(f"- {label}: {info}")

                    driver.back()
                    time.sleep(1)
                    log(f"Parcelamento extraído: {installment_lines}")
                else:
                    log("Nenhum botão de parcelamento encontrado.")
            except Exception as e:
                log(f"Erro ao coletar parcelamento diretamente: {e}")

            installment_text = (
                "💳 *Parcelamentos:*\n" + "\n".join(installment_lines)
                if installment_lines else ""
            )

            # Monta mensagem final
            parts = [f"🟡 *Mercado Livre*", f"🏷️ *{product_title[:150]}*"]
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

            parts.append(f"🛒 *Garanta agora:*\n🔗 {affiliate_link}")

            return product_title, "\n\n".join(parts), image_url

        except Exception as e:
            log(f"Erro inesperado ao extrair detalhes (tentativa {attempt}/{max_retries}): {e}")
            time.sleep(random.uniform(2, 4))

    log(f"Falha definitiva ao extrair dados do produto após {max_retries} tentativas: {url}")
    return None, None, None

def check_promotions():
    log("Iniciando verificação de promoções...")
    
    # Verifica status do WhatsApp se habilitado
    whatsapp_status = 'OFFLINE'
    if WHATSAPP_ENABLED:
        try:
            whatsapp_status = wpp_check_connection_state()
            if whatsapp_status == 'CONNECTED':
                log("✅ WhatsApp pronto para envio.")
            elif whatsapp_status == 'DISCONNECTED':
                log("⚠️ WhatsApp deslogado. Verifique o QR Code no Telegram.")
            else:
                log("❌ Servidor WhatsApp está offline.")
        except Exception as e:
            log(f"Erro ao verificar WhatsApp: {e}")
            whatsapp_status = 'OFFLINE'
    
    driver = None
    try:
        driver = init_driver()
        add_cookies(driver)

        product_urls = get_top_offers(driver)
        if not product_urls:
            log("Nenhuma oferta encontrada")
            return

        # Coleta nomes já enviados
        sent_names = set(sent_promotions)

        for url in product_urls:
            log(f"Processando promoção: {url}")
            try:
                product_title, message, image_url = get_product_details(driver, url)
                if not message:
                    continue

                if any(is_similar(product_title, sent) for sent in sent_names):
                    log(f"Produto muito parecido com um já enviado: {product_title}")
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

                # Envia para WhatsApp se habilitado e conectado
                whatsapp_success = False
                if WHATSAPP_ENABLED and whatsapp_status == 'CONNECTED':
                    try:
                        destinations = _load_whatsapp_destinations()
                        whatsapp_success = wpp_send_message(destinations=destinations, message=message, image_url=image_url)
                        if whatsapp_success:
                            log("Mensagem enviada com sucesso para WhatsApp")
                    except Exception as e:
                        log(f"Erro ao enviar para WhatsApp: {str(e)}")
                
                # Salva no histórico se pelo menos um dos envios foi bem-sucedido
                if telegram_success or (WHATSAPP_ENABLED and whatsapp_success):
                    if not TEST_MODE:
                        sent_promotions.append(product_title)
                        save_promo_history(sent_promotions)
                        log("Produto salvo no histórico.")
                    else:
                        log("⚠️ Modo teste ativado - Produto não será salvo no histórico")
                else:
                    log("Falha ao enviar para Telegram e WhatsApp - Produto não será salvo")

            except Exception as e:
                log(f"Erro no processamento da promoção: {str(e)}")

    except Exception as e:
        log(f"ERRO durante a verificação: {str(e)}")
    finally:
        if driver:
            log("Fechando o navegador...")
            driver.quit()



def schedule_scraper():
    """Configura e inicia o agendamento do scraper."""
    print("Iniciando agendamento do scraper...")
    
    if TEST_MODE:
        print("Modo de teste ativado - Executando imediatamente e a cada hora")
        check_promotions()
        schedule.every(1).hours.do(check_promotions)
    else:
        print("Modo normal - Agendando para horarios com final 30")
        # Executa imediatamente se forçado
        if FORCE_RUN_ON_START:
            print("Execução imediata forçada pelo .env")
            check_promotions()
        # Agenda para executar a cada hora, começando às 12:30
        schedule.every().day.at("12:30").do(check_promotions)
        schedule.every().day.at("13:30").do(check_promotions)
        schedule.every().day.at("14:30").do(check_promotions)
        schedule.every().day.at("15:30").do(check_promotions)
        schedule.every().day.at("16:30").do(check_promotions)
        schedule.every().day.at("17:30").do(check_promotions)
        schedule.every().day.at("18:30").do(check_promotions)
        schedule.every().day.at("19:30").do(check_promotions)
        schedule.every().day.at("20:30").do(check_promotions)
        schedule.every().day.at("21:30").do(check_promotions)
        schedule.every().day.at("22:30").do(check_promotions)
        schedule.every().day.at("23:30").do(check_promotions)
        schedule.every().day.at("00:30").do(check_promotions)
        schedule.every().day.at("01:30").do(check_promotions)
        schedule.every().day.at("02:30").do(check_promotions)
        schedule.every().day.at("03:30").do(check_promotions)
        schedule.every().day.at("04:30").do(check_promotions)
        schedule.every().day.at("05:30").do(check_promotions)
        schedule.every().day.at("06:30").do(check_promotions)
        schedule.every().day.at("07:30").do(check_promotions)
        schedule.every().day.at("08:30").do(check_promotions)
        schedule.every().day.at("09:30").do(check_promotions)
        schedule.every().day.at("10:30").do(check_promotions)
        schedule.every().day.at("11:30").do(check_promotions)
    
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
