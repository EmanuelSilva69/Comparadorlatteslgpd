"""API do Comparador Lattes (versão sem LLM).

Mudanças em relação à versão anterior:
- autenticação por sessão em todas as rotas (exceto login e assets);
- removidas as rotas de LLM e qualquer dependência de GPU/Ollama;
- CORS removido (frontend é servido pela própria API);
- rotas de atualização desabilitadas por padrão e protegidas por lock;
- mensagens de erro genéricas e cabeçalhos de segurança.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import auth
from data_parser import (
    BASE_DIR,
    gerar_indice_fontes,
    gerar_lista_alunos_scriptlattes,
    get_aluno_origem,
    load_students,
    resolver,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("comparador")

auth.carregar_env()
CFG = auth.Config()

PUBLIC_DIR = BASE_DIR / "public"
PERMITIR_ATUALIZACAO = os.getenv("APP_PERMITIR_ATUALIZACAO", "0").strip() == "1"

app = FastAPI(
    title="Scanner Pós-Mestrado API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# --------------------------------------------------------------------------
# Cabeçalhos de segurança e controle de acesso
# --------------------------------------------------------------------------
CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'"
)

ROTAS_PUBLICAS = {"/login", "/api/login", "/favicon.ico"}


def _rota_publica(caminho: str) -> bool:
    return caminho in ROTAS_PUBLICAS or caminho.startswith("/assets/")


@app.middleware("http")
async def seguranca(request: Request, call_next):
    caminho = request.url.path

    if not _rota_publica(caminho):
        usuario = auth.usuario_autenticado(request, CFG.segredo)
        if not usuario:
            if caminho.startswith("/api/"):
                return JSONResponse({"detail": "Não autenticado."}, status_code=401)
            return RedirectResponse("/login", status_code=303)
        request.state.usuario = usuario

        # CSRF: POST/PUT/DELETE exigem cabeçalho que um site externo não
        # consegue enviar sem passar por preflight de CORS.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("x-requested-with") != "XMLHttpRequest":
                return JSONResponse(
                    {"detail": "Requisição bloqueada pela proteção CSRF."},
                    status_code=403,
                )

    resposta = await call_next(request)

    resposta.headers["Content-Security-Policy"] = CSP
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["X-Frame-Options"] = "DENY"
    resposta.headers["Referrer-Policy"] = "no-referrer"
    resposta.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if caminho.startswith("/api/"):
        resposta.headers["Cache-Control"] = "no-store"
    return resposta


# --------------------------------------------------------------------------
# Autenticação
# --------------------------------------------------------------------------
class LoginBody(BaseModel):
    usuario: str
    senha: str


@app.post("/api/login")
def login(body: LoginBody, request: Request):
    ip = request.client.host if request.client else "desconhecido"

    if not auth.permitir_tentativa(ip):
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas de login. Tente novamente em alguns minutos.",
        )

    usuario = CFG.verificar_credenciais(body.usuario, body.senha)

    if not usuario:
        auth.registrar_falha(ip)
        log.warning("Falha de login para o usuário %r a partir de %s", body.usuario, ip)
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")

    auth.limpar_falhas(ip)
    token = auth.criar_token(usuario, CFG.segredo)

    resposta = JSONResponse({"usuario": usuario})
    resposta.set_cookie(
        key=auth.COOKIE_NAME,
        value=token,
        max_age=auth.sessao_max_idade(),
        httponly=True,
        samesite="strict",
        secure=CFG.cookie_seguro,
        path="/",
    )
    return resposta


@app.post("/api/logout")
def logout(request: Request):
    token = request.cookies.get(auth.COOKIE_NAME)
    if token:
        auth.revogar_token(token, CFG.segredo)
    resposta = JSONResponse({"status": "sessão encerrada"})
    resposta.delete_cookie(auth.COOKIE_NAME, path="/")
    return resposta


@app.get("/api/me")
def me(request: Request):
    return {
        "usuario": request.state.usuario,
        "atualizacao": PERMITIR_ATUALIZACAO,
    }


# --------------------------------------------------------------------------
# Dados
# --------------------------------------------------------------------------
class AlunoResponse(BaseModel):
    nome: str
    defesa: str
    status: str = ""
    turma: int = 0
    origem: str = "none"


@app.get("/api/alunos", response_model=list[AlunoResponse])
def listar_alunos():
    try:
        alunos = load_students()
        for aluno in alunos:
            aluno["origem"] = get_aluno_origem(aluno["nome"])
        return alunos
    except Exception:
        log.exception("Falha ao carregar a lista de alunos")
        raise HTTPException(status_code=500, detail="Não foi possível carregar os dados.")


@app.get("/api/resumos-cache")
def resumos_cache():
    cache_path = resolver("resumos_cache.json")
    if not cache_path.exists():
        raise HTTPException(status_code=404, detail="Cache de resumos não encontrado.")
    try:
        with open(cache_path, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except Exception:
        log.exception("Falha ao ler %s", cache_path)
        raise HTTPException(status_code=500, detail="Não foi possível ler o cache de resumos.")


# --------------------------------------------------------------------------
# Atualização da base (desabilitada por padrão)
# --------------------------------------------------------------------------
_lock_atualizacao = threading.Lock()


def tarefa_atualizar_lattes():
    log.info("Iniciando atualização do Lattes")
    if gerar_lista_alunos_scriptlattes():
        subprocess.run(
            [sys.executable, "scriptLattes.py", "exemplo/teste-01.config"],
            cwd=str(BASE_DIR / "scriptLattes"),
            check=False,
        )
    gerar_indice_fontes()
    log.info("Atualização do Lattes finalizada")


def tarefa_atualizar_escavador():
    log.info("Iniciando extração do Escavador")
    subprocess.run(
        [sys.executable, str(BASE_DIR / "scraper.py")],
        cwd=str(BASE_DIR),
        check=False,
    )
    gerar_indice_fontes()
    log.info("Extração do Escavador finalizada")


def _agendar_atualizacao(tarefa, background_tasks: BackgroundTasks, nome: str):
    if not PERMITIR_ATUALIZACAO:
        raise HTTPException(
            status_code=403,
            detail=(
                "Atualização desabilitada neste ambiente. "
                "Execute a coleta fora do servidor (APP_PERMITIR_ATUALIZACAO=1 para liberar)."
            ),
        )
    if not _lock_atualizacao.acquire(blocking=False):
        raise HTTPException(
            status_code=409, detail="Já existe uma atualização em andamento."
        )

    def executar():
        try:
            tarefa()
        except Exception:
            log.exception("Falha na atualização de %s", nome)
        finally:
            _lock_atualizacao.release()

    background_tasks.add_task(executar)
    return {"status": f"Processo do {nome} iniciado em segundo plano."}


@app.post("/api/update/lattes")
def update_lattes(background_tasks: BackgroundTasks):
    return _agendar_atualizacao(tarefa_atualizar_lattes, background_tasks, "Lattes")


@app.post("/api/update/escavador")
def update_escavador(background_tasks: BackgroundTasks):
    return _agendar_atualizacao(tarefa_atualizar_escavador, background_tasks, "Escavador")


# --------------------------------------------------------------------------
# Frontend
# --------------------------------------------------------------------------
if (PUBLIC_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=PUBLIC_DIR / "assets"), name="assets")


@app.get("/")
def serve_frontend():
    return FileResponse(PUBLIC_DIR / "index.html")


@app.get("/login")
def serve_login(request: Request):
    if auth.usuario_autenticado(request, CFG.segredo):
        return RedirectResponse("/", status_code=303)
    return FileResponse(PUBLIC_DIR / "login.html")


if __name__ == "__main__":
    if CFG.senha_temporaria:
        log.warning(
            "Nenhuma credencial configurada. Usuários: %s | Senha temporária: %s",
            ", ".join(CFG.usuarios),
            CFG.senha_temporaria,
        )
    if CFG.segredo_efemero:
        log.warning(
            "APP_SECRET_KEY não definida: as sessões serão invalidadas ao reiniciar."
        )
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
