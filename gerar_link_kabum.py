import urllib.parse

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

def encurtar_url(url):
    """Encurta uma URL usando a API do TinyURL"""
    try:
        import requests
        api_url = f'https://tinyurl.com/api-create.php?url={url}'
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            return response.text.strip()
        else:
            print(f"Erro ao encurtar URL: {response.status_code}")
            return url
    except Exception as e:
        print(f"Erro ao encurtar URL: {str(e)}")
        return url

if __name__ == "__main__":
    # URL do produto da Kabum
    url_produto = "https://www.kabum.com.br/produto/715915"
    
    print("🔗 Gerando link de afiliado para a Kabum...")
    print(f"📦 Produto: {url_produto}")
    print()
    
    # Gera o link de afiliado
    link_afiliado = gerar_link_afiliado(url_produto)
    print("🔗 Link de afiliado completo:")
    print(link_afiliado)
    print()
    
    # Encurta o link
    link_curto = encurtar_url(link_afiliado)
    print("🔗 Link de afiliado encurtado:")
    print(link_curto)
    print()
    
    print("✅ Link de afiliado gerado com sucesso!")
    print("💡 Use o link encurtado para compartilhar nas redes sociais.") 