from datetime import datetime, timedelta
import os
import re
import shlex
from tempfile import mkdtemp
from dotenv import load_dotenv
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
import time
import requests
import schedule
import sys

sys.stdout.reconfigure(line_buffering=True)

load_dotenv()

# Verifica se está em modo de teste
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

print("Test Mode:", TEST_MODE)

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID_TESTE") if TEST_MODE else os.getenv("TELEGRAM_GROUP_ID")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_TESTE") if TEST_MODE else os.getenv("TELEGRAM_CHAT_ID")

# WhatsApp
WHATSAPP_GROUP_NAME = os.getenv("WHATSAPP_GROUP_NAME_TESTE") if TEST_MODE else os.getenv("WHATSAPP_GROUP_NAME")

# Cookies do Mercado Livre
COOKIES = json.loads(os.getenv("ML_COOKIES"))

# Configurações gerais
if TEST_MODE:
    print("Modo de teste ativado, salvando em promocoes_teste.json")
    HISTORY_FILE = 'promocoes_teste.json'
else:
    HISTORY_FILE = 'promocoes_ml.json'
    print("Salvando em promocoes_ml.json")

MAX_HISTORY_SIZE = 200  # Mantém as últimas promoções
TOP_N_OFFERS = int(os.getenv("TOP_N_OFFERS_TESTE") if TEST_MODE else os.getenv("TOP_N_OFFERS"))
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
    "https://www.mercadolivre.com.br/ofertas?container_id=MLB779362-1&price=0.0-100.0#filter_applied=price&filter_position=6&is_recommended_domain=false&origin=scut",
    "https://www.mercadolivre.com.br/ofertas?container_id=MLB783320-1&domain_id=MLB-SUPPLEMENTS#filter_applied=domain_id&filter_position=3&is_recommended_domain=true&origin=scut"
]

# Arquivo para armazenar os links já utilizados
USED_URLS_FILE = 'used_urls_ml.json'

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
    """Retorna 2 URLs aleatórias da lista de ofertas, evitando repetição"""
    used_urls = load_used_urls()
    
    # Se todos os links já foram usados, limpa o histórico
    if len(used_urls) >= len(OFFER_URLS):
        log("Todos os links foram utilizados. Reiniciando histórico...")
        used_urls.clear()
        save_used_urls(used_urls)
    
    # Filtra apenas os links não utilizados
    available_urls = [url for url in OFFER_URLS if url not in used_urls]
    
    # Se não houver links suficientes, usa todos os links disponíveis
    num_urls = min(2, len(available_urls))
    
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
    try:
        with open(HISTORY_FILE, 'r') as f:
            nomes = json.load(f)
        return deque(nomes, maxlen=MAX_HISTORY_SIZE)
    except (FileNotFoundError, json.JSONDecodeError):
        return deque(maxlen=MAX_HISTORY_SIZE)

# Função para salvar o histórico
def save_promo_history(history: deque):
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
                    if discount_value > 20:
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
                
                if not affiliate_link:
                    raise Exception("Link de afiliado não gerado")
                    
            except Exception as e:
                log(f"Erro ao gerar link de afiliado: {e}")
                if attempt < max_retries:
                    log(f"Tentando novamente... (Tentativa {attempt + 1}/{max_retries})")
                    continue
                else:
                    log("Número máximo de tentativas atingido. Pulando produto.")
                    return None, None, None

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
                        .replace("com acréscimo", "com juros")
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
            log(f"Erro ao extrair detalhes (tentativa {attempt}/{max_retries}): {e}")
            time.sleep(random.uniform(2, 4))

    log(f"Falha definitiva ao extrair dados do produto após {max_retries} tentativas: {url}")
    return None, None, None

def check_promotions():
    log("Iniciando verificação de promoções...")
    driver = None
    try:
        driver = init_driver()
        add_cookies(driver)

        product_urls = get_top_offers(driver)
        if not product_urls:
            log("Nenhuma oferta encontrada")
            return

        # Coleta nomes já enviados
        sent_names = set(sent_promotions)  # já estão normalizados no arquivo

        run_whatsapp_auth()
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

                # Envia para WhatsApp se o Telegram foi bem sucedido
                if telegram_success:
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
                        log("✅ Enviado ao WhatsApp com sucesso.")
                        sent_promotions.append(product_title)
                        save_promo_history(sent_promotions)
                        log("Produto salvo no histórico.")

                    except subprocess.CalledProcessError as e:
                        log(f"❌ Erro ao executar o script Node.js: {e}")
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

def schedule_scraper():
    """Configura e inicia o agendamento do scraper."""
    print("Iniciando agendamento do scraper...")
    
    if TEST_MODE:
        print("Modo de teste ativado - Executando imediatamente e a cada hora")
        check_promotions()
        schedule.every(1).hours.do(check_promotions)
    else:
        print("Modo normal - Agendando para horários específicos")
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