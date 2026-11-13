import os
import re
import json
import glob

from data_parser import resolver

# Caminhos resolvidos a partir de ./dados (ou da raiz do projeto).
DIR_ESCAVADOR = str(resolver("escavador_perfis"))
DIR_LATTES_RAIZ = str(resolver("scriptLattes", "resultados"))
DIR_LATTES_JSON = os.path.join(DIR_LATTES_RAIZ, "json")
FILE_ACADEMIC = str(resolver("academicData.ts"))
CACHE_FILE = str(resolver("mapeamento_lattes.json"))

def carregar_nomes_academic_data():
    """Extrai todos os nomes do academicData.ts"""
    if not os.path.exists(FILE_ACADEMIC):
        print(f"❌ Arquivo não encontrado: {FILE_ACADEMIC}")
        return []
        
    with open(FILE_ACADEMIC, 'r', encoding='utf-8') as f:
        content = f.read()

    # Busca todos os nomes dentro dos objetos (turma 1 a 15)
    matches = re.finditer(r'nome:\s*\"([^\"]+)\"', content)
    nomes = [m.group(1).strip().upper() for m in matches]
    
    # Remove duplicatas caso existam
    return list(set(nomes))

def verificar_arquivos():
    print("=" * 60)
    print("🕵️‍♂️ INICIANDO VERIFICAÇÃO CRUZADA DE ARQUIVOS")
    print("=" * 60)

    nomes_academic = carregar_nomes_academic_data()
    print(f"📊 Total de alunos encontrados no academicData.ts: {len(nomes_academic)}")

    # Carrega o mapeamento Lattes para saber os IDs
    mapeamento = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            mapeamento = json.load(f)

    encontrados_lattes = []
    encontrados_escavador = []
    nao_encontrados = []

    for nome in sorted(nomes_academic):
        achou_algo = False
        
        # 1. Verifica no Escavador
        nome_limpo = re.sub(r'[\\/*?:"<>|]', "", nome)
        caminho_html = os.path.join(DIR_ESCAVADOR, nome_limpo, "perfil.html")
        if os.path.exists(caminho_html):
            encontrados_escavador.append(nome)
            achou_algo = True

        # 2. Verifica no Lattes (procura na raiz resultados/ ou resultados/json/)
        id_lattes = mapeamento.get(nome, "").strip()
        if id_lattes and re.match(r'^\d{16}$', id_lattes):
            busca_raiz = glob.glob(os.path.join(DIR_LATTES_RAIZ, f"*_{id_lattes}.json"))
            busca_subpasta = glob.glob(os.path.join(DIR_LATTES_JSON, f"*_{id_lattes}.json"))
            
            if busca_raiz or busca_subpasta:
                encontrados_lattes.append(nome)
                achou_algo = True
                
        # 3. Se não achou em nenhum dos dois
        if not achou_algo:
            nao_encontrados.append(nome)

    # Imprime o Relatório
    print("\n✅ ALUNOS COM JSON DO LATTES ENCONTRADO:")
    print(f"Total: {len(encontrados_lattes)}")
    
    print("\n✅ ALUNOS COM HTML DO ESCAVADOR ENCONTRADO:")
    print(f"Total: {len(encontrados_escavador)}")
    
    print("\n❌ ALUNOS SEM NENHUM ARQUIVO LOCAL (FALTANDO):")
    print(f"Total: {len(nao_encontrados)}")
    for nome in nao_encontrados:
        status_mapeamento = mapeamento.get(nome, "Não mapeado no mapeamento_lattes.json")
        print(f"  - {nome} (Status no cache: {status_mapeamento})")

    print("\n" + "=" * 60)
    print("Resumo Geral:")
    print(f"Total na Base: {len(nomes_academic)} | Cobertura de Arquivos: {len(encontrados_lattes) + len(encontrados_escavador)}")
    if len(nao_encontrados) == 0:
        print("🎉 PERFEITO! Todos os alunos do academicData.ts possuem arquivos físicos.")
    print("=" * 60)

if __name__ == "__main__":
    verificar_arquivos()