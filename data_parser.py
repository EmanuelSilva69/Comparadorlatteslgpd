import glob
import json
import logging
import os
import re
from pathlib import Path

log = logging.getLogger("comparador.dados")

BASE_DIR = Path(__file__).resolve().parent

# Dados pessoais ficam fora do código. Por padrão, em ./dados quando essa
# pasta existir; caso contrário, na raiz do projeto (compatibilidade local).
_data_env = os.getenv("APP_DATA_DIR", "").strip()
if _data_env:
    DATA_DIR = Path(_data_env).expanduser().resolve()
else:
    _padrao = BASE_DIR / "dados"
    DATA_DIR = _padrao if _padrao.is_dir() else BASE_DIR


def resolver(*partes: str) -> Path:
    """Prefere DATA_DIR; cai para BASE_DIR se o arquivo só existir lá."""
    candidato = DATA_DIR.joinpath(*partes)
    if candidato.exists():
        return candidato
    alternativo = BASE_DIR.joinpath(*partes)
    if alternativo.exists():
        return alternativo
    return candidato


CACHE_FILE = str(resolver("mapeamento_lattes.json"))
BASE_DIR_PERFIS = str(resolver("escavador_perfis"))


def extrair_texto_html(html):
    text = html

    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    text = re.sub(r'/*# sourceMappingURL=data:[^ ]+', '', text)
    text = re.sub(r'data:image/[^;]+;base64[^"]+', '', text)

    desc = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    meta_desc = desc.group(1) if desc else ""

    text = re.sub(r'<(br|/p|/div|/li|/tr|/h[1-6]|/header|/section|/footer)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)

    lines = [l.strip() for l in text.split('\n') if l.strip()]
    lines = [l for l in lines if len(l) > 15]

    result = "\n".join(lines)

    if meta_desc:
        result = f"--- RESUMO ---\n{meta_desc}\n\n--- DETALHES ---\n{result}"

    lines_out = result.split('\n')
    if len(lines_out) > 150:
        lines_out = lines_out[:150]
        result = "\n".join(lines_out) + "\n[...]"

    return result


def load_students(filepath=None):
    """Carrega a lista de alunos a partir do arquivo TypeScript."""
    caminho = Path(filepath) if filepath else resolver("academicData.ts")
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    with open(caminho, 'r', encoding='utf-8') as f:
        content = f.read()

    students = []
    # Busca blocos de objetos que tenham nome, defesa, turma e conclusaoNoPrazo
    matches = re.finditer(
        r'nome:\s*"([^"]+)".*?defesa:\s*"([^"]*)".*?conclusaoNoPrazo:\s*"([^"]+)".*?turma:\s*(\d+)',
        content, re.DOTALL
    )

    for m in matches:
        nome = m.group(1).strip()
        defesa = m.group(2).strip()
        status = m.group(3).strip()
        turma = int(m.group(4))

        # Mostra "EM ANDAMENTO" para alunos sem defesa
        if not defesa:
            defesa = "EM ANDAMENTO"

        students.append({
            "nome": nome,
            "defesa": defesa,
            "status": status,
            "turma": turma
        })

    return students


def _pastas_json():
    """Pastas onde o scriptLattes grava os JSONs individuais."""
    candidatas = [
        DATA_DIR / "scriptLattes" / "resultados" / "json",
        BASE_DIR / "scriptLattes" / "resultados" / "json",
    ]
    vistas = []
    for pasta in candidatas:
        if pasta not in vistas:
            vistas.append(pasta)
    return vistas


# Índice derivado: nome -> "json" | "html" | "none".
# Permite exibir a origem sem precisar versionar os HTMLs do Escavador nem os
# JSONs do Lattes (minimização de dados pessoais).
_indice_cache = None
_indice_mtime = None


def _indice_fontes():
    global _indice_cache, _indice_mtime
    caminho = resolver("indice_fontes.json")
    if not caminho.exists():
        return None
    try:
        mtime = caminho.stat().st_mtime
        if _indice_cache is None or mtime != _indice_mtime:
            with open(caminho, "r", encoding="utf-8") as f:
                _indice_cache = json.load(f)
            _indice_mtime = mtime
        return _indice_cache
    except Exception:
        log.warning("Falha ao ler o índice de fontes", exc_info=True)
        return None


def _origem_no_disco(nome_aluno):
    """Verifica no disco se o aluno possui dados JSON (Lattes) ou HTML (Escavador)."""
    # --- CANAL 1: JSON do Lattes ---
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache_ids = json.load(f)
            id_lattes = cache_ids.get(nome_aluno, "").strip()
            if id_lattes and re.match(r'^\d{16}$', id_lattes):
                for json_dir in _pastas_json():
                    arquivos = glob.glob(os.path.join(json_dir, f"*_{id_lattes}.json"))
                    if arquivos:
                        return "json"
        except Exception:
            log.warning("Falha ao consultar o mapeamento Lattes", exc_info=True)

    # --- CANAL 2: HTML do Escavador ---
    nome_pasta_limpo = re.sub(r'[\\/*?:"<>|]', "", nome_aluno)
    caminho_html = os.path.join(BASE_DIR_PERFIS, nome_pasta_limpo, "perfil.html")
    if os.path.exists(caminho_html):
        return "html"

    return "none"


def get_aluno_origem(nome_aluno):
    """Origem dos dados do aluno, usando o índice quando disponível."""
    indice = _indice_fontes()
    if indice is not None:
        return indice.get(nome_aluno, "none")
    return _origem_no_disco(nome_aluno)


def gerar_indice_fontes(destino=None):
    """Regera indice_fontes.json a partir dos arquivos de coleta."""
    alunos = load_students()
    indice = {aluno["nome"]: _origem_no_disco(aluno["nome"]) for aluno in alunos}

    caminho = Path(destino) if destino else resolver("indice_fontes.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, indent=2)

    log.info("Índice de fontes gerado em %s (%d alunos)", caminho, len(indice))
    return indice


def gerar_lista_alunos_scriptlattes(filename=None):
    """
    Lê o mapeamento_lattes.json e gera o arquivo de texto de entrada do scriptLattes.
    Coloca na lista APENAS os alunos que possuem o ID Lattes de 16 dígitos válido.
    Formatação estrita exigida pelo scriptLattes: ID_16_DIGITOS , Nome Completo
    """
    if not os.path.exists(CACHE_FILE):
        log.warning("Arquivo de cache '%s' não encontrado.", CACHE_FILE)
        return False

    with open(CACHE_FILE, 'r', encoding='utf-8') as f:
        cache_ids = json.load(f)

    destino = Path(filename) if filename else BASE_DIR / "scriptLattes" / "lista_alunos.txt"
    os.makedirs(destino.parent, exist_ok=True)
    linhas_para_salvar = []

    for nome, valor in cache_ids.items():
        # Verifica se o valor guardado é puramente um ID numérico de 16 dígitos
        if valor and re.match(r'^\d{16}$', str(valor).strip()):
            # Salvando no padrão estrito 'ID , Nome' exigido pelo CNPq/scriptLattes
            linhas_para_salvar.append(f"{valor.strip()} , {nome}\n")

    with open(destino, "w", encoding="utf-8") as f:
        f.writelines(linhas_para_salvar)

    log.info("%d alunos exportados para %s", len(linhas_para_salvar), destino)
    return True


def get_student_data_from_json(nome_aluno, json_dir=None):
    """
    Busca o arquivo JSON do aluno DIRETAMENTE na subpasta resultados/json/.
    Busca pelo ID de 16 dígitos contido no final do nome do arquivo.
    """
    if not os.path.exists(CACHE_FILE):
        return None

    pastas = [Path(json_dir)] if json_dir else _pastas_json()

    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_ids = json.load(f)

        id_lattes = cache_ids.get(nome_aluno, "").strip()

        # Se não for um ID numérico puro de 16 dígitos, ignora (deixa para o Escavador)
        if not id_lattes or not re.match(r'^\d{16}$', id_lattes):
            return None

        arquivos = []
        for pasta in pastas:
            if os.path.exists(pasta):
                arquivos = glob.glob(os.path.join(pasta, f"*_{id_lattes}.json"))
                if arquivos:
                    break

        if not arquivos:
            return None

        with open(arquivos[0], 'r', encoding='utf-8') as f:
            data = json.load(f)

        pessoais = data.get('informacoes_pessoais', {})
        markdown_text = f"NOME NO PROJETO: {nome_aluno}\n"
        markdown_text += f"NOME OFICIAL LATTES: {pessoais.get('nome_completo', nome_aluno)}\n"
        markdown_text += f"RESUMO: {pessoais.get('texto_resumo', 'Sem resumo disponível')}\n\n"

        markdown_text += "### PROJETOS DE PESQUISA\n"
        for proj in data.get('projetos_pesquisa', []):
            markdown_text += f"- {proj.get('nome', 'Projeto')} ({proj.get('ano_inicio', '')})\n"

        markdown_text += "\n### PUBLICAÇÕES\n"
        for art in data.get('producao_bibliografica', {}).get('artigo_em_periodico', []):
            markdown_text += f"- {art.get('titulo', 'Artigo')} ({art.get('ano', '')})\n"

        return markdown_text
    except Exception:
        log.warning("Erro ao processar JSON do aluno %s", nome_aluno, exc_info=True)
        return None


def obter_conteudo_academico_hibrido(nome_aluno):
    """
    Mecanismo Híbrido de Coleta de Dados (Canal Principal vs Fallback).
    """
    # --- CANAL 1: Dados Oficiais do scriptLattes ---
    dados_lattes = get_student_data_from_json(nome_aluno)
    if dados_lattes:
        return f"--- DADOS OFICIAIS DO CURRÍCULO LATTES (via scriptLattes) ---\n{dados_lattes}"

    # --- CANAL 2: Fallback (Plano B) via HTML do Escavador ---
    nome_pasta_limpo = re.sub(r'[\\/*?:"<>|]', "", nome_aluno)
    caminho_html = os.path.join(BASE_DIR_PERFIS, nome_pasta_limpo, "perfil.html")

    if os.path.exists(caminho_html):
        try:
            with open(caminho_html, "r", encoding="utf-8") as f:
                html_bruto = f.read()

            texto_limpo = extrair_texto_html(html_bruto)

            return f"--- DADOS PROVENIENTES DO HTML DO ESCAVADOR (FALLBACK) ---\nNOME DO ALUNO: {nome_aluno}\n{texto_limpo}"
        except Exception:
            log.warning("Erro ao ler o HTML de %s", nome_aluno, exc_info=True)

    return None
