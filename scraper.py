import os
import re
import json
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import InvalidSessionIdException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from data_parser import load_students

CACHE_FILE = "mapeamento_lattes.json"
BASE_DIR_PERFIS = "escavador_perfis"

def carregar_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def salvar_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=4, ensure_ascii=False)

def iniciar_navegador():
    print("🚀 Inicializando sessão do Chrome para Contingência...")
    options = webdriver.ChromeOptions()
    options.add_argument("start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def iniciar_scraping_google():
    print("🎓 Carregando lista de alunos...")
    alunos = load_students()
    cache_ids = carregar_cache()

    # Cria a pasta base para armazenar os HTMLs dos perfis de contingência
    os.makedirs(BASE_DIR_PERFIS, exist_ok=True)

    driver = iniciar_navegador()
    
    print(f"\n🎯 Total de alunos na lista: {len(alunos)}")
    print("--------------------------------------------------")

    i = 0
    while i < len(alunos):
        aluno = alunos[i]
        nome = aluno["nome"]
        
        val_atual = cache_ids.get(nome, "").strip()
        
        # REGRA DE PROTEÇÃO 1: Se o valor for um ID Lattes válido de 16 dígitos, NÃO MEXE!
        if val_atual and re.match(r'^\d{16}$', val_atual):
            print(f"📦 [{i+1}/{len(alunos)}] {nome} já possui ID Lattes oficial. Protegendo e pulando...")
            i += 1
            continue
            
        # REGRA DE PROTEÇÃO 2: Se já foi baixado o HTML do Escavador anteriormente, pula para poupar rede
        nome_pasta_limpo = re.sub(r'[\\/*?:"<>|]', "", nome)
        caminho_arquivo = os.path.join(BASE_DIR_PERFIS, nome_pasta_limpo, "perfil.html")
        if val_atual.startswith("ESCAVADOR:") and os.path.exists(caminho_arquivo):
            print(f"📦 [{i+1}/{len(alunos)}] {nome} já possui Fallback HTML local. Pulando...")
            i += 1
            continue
            
        # Se chegou aqui, é porque está em branco ("") ou falhou antes. Vamos buscar no Escavador.
        print(f"🔍 [{i+1}/{len(alunos)}] Extraindo Fallback (Escavador HTML) para: {nome}")
        
        try:
            if driver is None:
                driver = iniciar_navegador()

            # --- ETAPA 1: Localizar o link do perfil no Google ---
            driver.get("https://www.google.com")
            time.sleep(random.uniform(2.0, 3.5))
            
            barra_pesquisa = driver.find_element(By.NAME, "q")
            query = f"{nome} escavador"
            barra_pesquisa.send_keys(query)
            barra_pesquisa.send_keys(Keys.ENTER)
            
            time.sleep(random.uniform(4.0, 6.5))
            
            links_google = driver.find_elements(By.TAG_NAME, "a")
            url_escavador = None
            
            for link in links_google:
                try:
                    url = link.get_attribute("href")
                    if url and "escavador.com" in url and ("sobre" in url or "pessoas" in url):
                        url_escavador = url
                        break
                except:
                    continue
            
            sucesso_download = False
            
            # --- ETAPA 2: Baixar a página inteira se o link foi encontrado ---
            if url_escavador:
                print(f"   ℹ️ Link do Escavador mapeado: {url_escavador}")
                driver.get(url_escavador)
                time.sleep(random.uniform(5.0, 8.0)) # Tempo para os scripts de renderização agirem
                
                html_completo = driver.page_source
                
                if html_completo and len(html_completo) > 5000:
                    # Cria a pasta isolada do aluno e salva o Dump do HTML
                    pasta_aluno = os.path.join(BASE_DIR_PERFIS, nome_pasta_limpo)
                    os.makedirs(pasta_aluno, exist_ok=True)
                    
                    caminho_final_html = os.path.join(pasta_aluno, "perfil.html")
                    with open(caminho_final_html, "w", encoding="utf-8") as f:
                        f.write(html_completo)
                        
                    print(f"   💾 HTML de contingência salvo: {caminho_final_html}")
                    
                    # Atualiza o arquivo json marcando como resolvido via Escavador
                    cache_ids[nome] = f"ESCAVADOR:{url_escavador}"
                    salvar_cache(cache_ids)
                    sucesso_download = True
                else:
                    print("   ⚠️ HTML veio corrompito ou menor que o esperado.")
            else:
                print("   ❌ Sem correspondência de perfil público no Escavador.")
            
            if not sucesso_download:
                cache_ids[nome] = "FALHA_CONVENCAO"
                salvar_cache(cache_ids)
            
            i += 1
            intervalo = random.uniform(8.0, 13.0)
            print(f"⏳ Aguardando {intervalo:.1f}s de respiro anti-bloqueio...")
            time.sleep(intervalo)

        except (InvalidSessionIdException, WebDriverException) as e:
            print(f"\n⚠️ Sessão desconectada. Reiniciando engine para reprocessar o aluno atual...")
            try:
                driver.quit()
            except:
                pass
            driver = None
            time.sleep(5)

        except Exception as e:
            print(f"   ⚠️ Falha inesperada: {e}")
            i += 1
            time.sleep(5)

    try:
        if driver:
            driver.quit()
    except:
        pass
    print("\n🏁 Base de Fallback local alimentada com sucesso!")

if __name__ == "__main__":
    if os.getenv("APP_AMBIENTE", "").strip().lower() == "producao":
        raise SystemExit(
            "Scraper desabilitado em produção. Rode a coleta fora do servidor "
            "e importe o resultado (ver README)."
        )
    iniciar_scraping_google()