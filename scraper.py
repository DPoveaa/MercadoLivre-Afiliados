from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import time
import requests
import schedule
import sys

# Configurações
TELEGRAM_BOT_TOKEN = '7809229983:AAGBphj2suFOzCeQOjhNNEnqDeb7aihMYpE'
TELEGRAM_CHAT_ID = '-1002388728835'  # Substitua pelo seu chat ID
ML_AFFILIATE_LABEL = 'centraldedescontos - 61832902'

# Variável global para armazenar promoções já enviadas
sent_promotions = set()

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
    """Inicializa o driver do Chrome com opções visíveis"""
    try:
        log("Inicializando o navegador Chrome...")
        chrome_options = Options()
        # chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Usa o webdriver-manager para baixar o driver automaticamente
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        log("Navegador Chrome inicializado com sucesso")
        return driver
    except WebDriverException as e:
        log(f"ERRO ao inicializar o ChromeDriver: {str(e)}")
        sys.exit(1)

def add_cookies(driver):
    """Adiciona cookies ao driver"""
    try:
        log("Acessando o Mercado Livre para configurar cookies...")
        driver.get('https://www.mercadolivre.com.br')
        time.sleep(2)  # Espera a página carregar
        
        log(f"Adicionando {len(COOKIES)} cookies...")
        for cookie in COOKIES:
            driver.add_cookie(cookie)
            log(f"Cookie adicionado: {cookie['name']}")
        
        log("Cookies configurados com sucesso")
    except Exception as e:
        log(f"ERRO ao configurar cookies: {str(e)}")
        raise

def get_top_offers(driver):
    """Busca as melhores ofertas no Mercado Livre"""
    try:
        log("Acessando página de ofertas...")
        driver.get('https://www.mercadolivre.com.br/ofertas')
        time.sleep(3)  # Espera adicional
        
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.andes-card.poly-card'))
        )
        log("Página de ofertas carregada com sucesso")
        
        cards = driver.find_elements(By.CSS_SELECTOR, '.andes-card.poly-card')
        offers = []
        
        log(f"Encontrados {len(cards)} cards de produtos")
        
        for card in cards[:20]:
            try:
                discount_element = card.find_element(By.CSS_SELECTOR, '.andes-money-amount__discount')
                discount = float(discount_element.text.replace('% OFF', ''))
                link = card.find_element(By.CSS_SELECTOR, 'a.poly-component__title').get_attribute('href')
                offers.append({'discount': discount, 'url': link})
                log(f"Oferta encontrada: {discount}% OFF - {link}")
            except Exception as e:
                log(f"Ignorando card (erro: {str(e)})")
                continue
        
        top_offers = sorted(offers, key=lambda x: x['discount'], reverse=True)[:3]
        log(f"Top 3 ofertas encontradas: {[o['discount'] for o in top_offers]}% OFF")
        
        return [offer['url'] for offer in top_offers]
    
    except Exception as e:
        log(f"ERRO ao buscar ofertas: {str(e)}")
        return []

def get_product_details(driver, url):
    """Extrai detalhes do produto e formata a mensagem"""
    try:
        driver.get(url)
        time.sleep(3)  # Espera a página carregar

        # Extrai o título do produto
        title = driver.find_element(By.CSS_SELECTOR, "h1.ui-pdp-title").text
        
        # Verifica se é oferta do dia
        offer_tag = ""
        try:
            offer_tag = driver.find_element(By.CSS_SELECTOR, ".ui-pdp-promotions-pill-label.ui-pdp-background-color--BLUE").text
        except:
            pass
        
        # Avaliação do produto - método mais robusto
        rating = "Sem avaliações"
        rating_count = ""
        try:
            rating_info = driver.find_element(By.CSS_SELECTOR, ".andes-visually-hidden").get_attribute("textContent")
            if "Avaliação" in rating_info:
                rating = rating_info.split("Avaliação ")[1].split(" de")[0]
                rating_count = rating_info.split("opiniões")[0].split()[-1].replace(".", "").replace(",", "")
        except Exception as e:
            log(f"Erro ao extrair avaliações: {str(e)}")
        
        # Preços
        original_price = driver.find_element(By.CSS_SELECTOR, ".ui-pdp-price__original-value .andes-money-amount__fraction").text
        current_price = driver.find_element(By.CSS_SELECTOR, ".ui-pdp-price__part .andes-money-amount__fraction").text
        try:
            cents = driver.find_element(By.CSS_SELECTOR, ".ui-pdp-price__part .andes-money-amount__cents").text
            current_price = f"{current_price},{cents}"
        except:
            current_price = f"{current_price},00"
        
        # Desconto
        discount = driver.find_element(By.CSS_SELECTOR, ".andes-money-amount__discount").text
        
        # Parcelamento (pega apenas a primeira linha)
        installments = driver.find_element(By.CSS_SELECTOR, "#pricing_price_subtitle").text.split("\n")[0]
        
        # Cupom
        coupon_text = ""
        coupon_savings = ""
        try:
            coupon_text = driver.find_element(By.CSS_SELECTOR, "#coupon-awareness-row-label").text
            coupon_savings = driver.find_element(By.CSS_SELECTOR, "#coupon_summary-subtitles-style-label").text
        except:
            pass
        
        # Imagem do produto
        image_url = ""
        try:
            image_url = driver.find_element(By.CSS_SELECTOR, ".ui-pdp-image.ui-pdp-gallery__figure__image").get_attribute("src")
        except:
            pass
        
        # Formata a mensagem
        message = f"""
🔥 *{title[:100]}*{' - ' + offer_tag if offer_tag else ''}

⭐ *{rating}{' (' + rating_count + ' avaliações)' if rating_count else ''}*  
💰 *De: R$ {original_price}*  
👉 *Por: R$ {current_price}*  
📉 *{discount}*  
💳 {installments[:50]}  
{'🎟️ *' + coupon_text + '* — ' + coupon_savings if coupon_text else ''}

[🔗 Ver produto]({url})
        """.strip()
        
        return message, image_url
        
    except Exception as e:
        log(f"Erro ao extrair detalhes do produto: {str(e)}")
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
        
        new_urls = [url for url in product_urls if url not in sent_promotions]
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
                            sent_promotions.add(url)
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
                    sent_promotions.add(url)
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
            
# Configura o agendamento
log("Configurando agendamento para verificar a cada hora...")
schedule.every().hour.do(check_promotions)

# Executa imediatamente a primeira verificação
log("Executando verificação inicial imediatamente...")
check_promotions()

# Loop principal
log("Bot iniciado. Pressione Ctrl+C para parar.")
try:
    while True:
        schedule.run_pending()
        time.sleep(1)
except KeyboardInterrupt:
    log("Bot encerrado pelo usuário")