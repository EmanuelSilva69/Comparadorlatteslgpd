"""Autenticação simples por sessão para o Comparador Lattes.

Sem dependências externas: usa PBKDF2 (hashlib) para a senha e um token
assinado com HMAC-SHA256 para o cookie de sessão.

Configuração por variáveis de ambiente (ou arquivo .env na raiz):

    APP_USUARIO          usuário de acesso (padrão: admin)
    APP_USUARIOS         usuários extras: "mestrado|<hash>;outro|<hash>"
    APP_SENHA_HASH       hash gerado por tools/gerar_senha.py (recomendado)
    APP_SENHA            senha em texto puro (apenas para testes locais)
    APP_SECRET_KEY       chave usada para assinar o cookie de sessão
    APP_COOKIE_SECURE    1 = cookie só via HTTPS (produção)
    APP_SESSAO_HORAS     validade da sessão em horas (padrão: 8)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

COOKIE_NAME = "sessao"
PBKDF2_ITERACOES = 390_000


def sessao_max_idade() -> int:
    return int(os.getenv("APP_SESSAO_HORAS", "8")) * 3600

TENTATIVAS_MAX = 5
JANELA_TENTATIVAS = 300  # segundos


# --------------------------------------------------------------------------
# .env
# --------------------------------------------------------------------------
def carregar_env(caminho: Path | None = None) -> None:
    """Carrega um .env simples (KEY=VALUE) sem sobrescrever o ambiente."""
    caminho = caminho or BASE_DIR / ".env"
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave = chave.strip()
        valor = valor.strip().strip('"').strip("'")
        if chave:
            os.environ.setdefault(chave, valor)


# --------------------------------------------------------------------------
# Senha
# --------------------------------------------------------------------------
def _b64e(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).decode().rstrip("=")


def _b64d(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def gerar_hash_senha(senha: str, iteracoes: int = PBKDF2_ITERACOES) -> str:
    """Gera um hash no formato pbkdf2_sha256:iteracoes:salt:hash."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, iteracoes)
    return f"pbkdf2_sha256:{iteracoes}:{_b64e(salt)}:{_b64e(digest)}"


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    try:
        algoritmo, iteracoes, salt_b64, digest_b64 = hash_armazenado.split(":")
        if algoritmo != "pbkdf2_sha256":
            return False
        salt = _b64d(salt_b64)
        esperado = _b64d(digest_b64)
        calculado = hashlib.pbkdf2_hmac(
            "sha256", senha.encode("utf-8"), salt, int(iteracoes)
        )
        return hmac.compare_digest(calculado, esperado)
    except Exception:
        return False


# Hash descartável usado para igualar o tempo de resposta de logins inválidos.
_HASH_FICTICIO = gerar_hash_senha("usuario-inexistente")


# --------------------------------------------------------------------------
# Configuração
# --------------------------------------------------------------------------
class Config:
    def __init__(self) -> None:
        self.cookie_seguro = os.getenv("APP_COOKIE_SECURE", "0").strip() == "1"
        self.senha_temporaria: str | None = None
        self.segredo_efemero = False
        self.usuarios: dict[str, str] = {}

        # Formato: APP_USUARIOS="mestrado|<hash>;admin|<hash>"
        bruto = os.getenv("APP_USUARIOS", "").strip()
        if bruto:
            for item in bruto.split(";"):
                item = item.strip()
                if not item or "|" not in item:
                    continue
                usuario, hash_senha = item.split("|", 1)
                usuario = usuario.strip()
                hash_senha = hash_senha.strip()
                if usuario and hash_senha:
                    self.usuarios[usuario] = hash_senha

        # Compatibilidade com a configuração de usuário único.
        usuario = os.getenv("APP_USUARIO", "admin").strip() or "admin"
        hash_senha = os.getenv("APP_SENHA_HASH", "").strip()
        if not hash_senha:
            senha = os.getenv("APP_SENHA", "").strip()
            if senha:
                hash_senha = gerar_hash_senha(senha)
        if hash_senha:
            self.usuarios.setdefault(usuario, hash_senha)

        if not self.usuarios:
            # Sem credencial configurada: gera uma senha aleatória para
            # esta execução. O valor é impresso no console ao iniciar.
            self.senha_temporaria = secrets.token_urlsafe(9)
            self.usuarios[usuario] = gerar_hash_senha(self.senha_temporaria)

        self.segredo = os.getenv("APP_SECRET_KEY", "").strip()
        if not self.segredo:
            # Sessões deixam de valer quando o processo reinicia.
            self.segredo = secrets.token_hex(32)
            self.segredo_efemero = True

    def verificar_credenciais(self, usuario: str, senha: str) -> str | None:
        """Devolve o usuário autenticado ou None."""
        usuario = (usuario or "").strip()
        hash_armazenado = self.usuarios.get(usuario)
        if hash_armazenado is None:
            # Mantém o tempo de resposta parecido para não revelar usuários.
            verificar_senha(senha, _HASH_FICTICIO)
            return None
        if verificar_senha(senha, hash_armazenado):
            return usuario
        return None


# --------------------------------------------------------------------------
# Token de sessão (HMAC + registro em memória para permitir logout)
# --------------------------------------------------------------------------
_sessoes_ativas: dict[str, float] = {}
_sessoes_lock = threading.Lock()


def _registrar_sessao(nonce: str, expira_em: float) -> None:
    agora = time.time()
    with _sessoes_lock:
        for chave in [k for k, v in _sessoes_ativas.items() if v < agora]:
            del _sessoes_ativas[chave]
        _sessoes_ativas[nonce] = expira_em


def _sessao_ativa(nonce: str | None) -> bool:
    if not nonce:
        return False
    with _sessoes_lock:
        expira_em = _sessoes_ativas.get(nonce)
        return expira_em is not None and expira_em >= time.time()


def _remover_sessao(nonce: str | None) -> None:
    if not nonce:
        return
    with _sessoes_lock:
        _sessoes_ativas.pop(nonce, None)


def criar_token(usuario: str, segredo: str) -> str:
    nonce = secrets.token_hex(16)
    expira_em = int(time.time()) + sessao_max_idade()
    _registrar_sessao(nonce, expira_em)

    payload = {"u": usuario, "exp": expira_em, "n": nonce}
    corpo = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    assinatura = _b64e(
        hmac.new(segredo.encode("utf-8"), corpo.encode("utf-8"), hashlib.sha256).digest()
    )
    return f"{corpo}.{assinatura}"


def _ler_payload(token: str, segredo: str) -> dict | None:
    """Valida a assinatura e devolve o payload (sem checar a sessão)."""
    try:
        corpo, assinatura = token.split(".", 1)
        esperado = _b64e(
            hmac.new(segredo.encode("utf-8"), corpo.encode("utf-8"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(assinatura, esperado):
            return None
        payload = json.loads(_b64d(corpo))
        if int(payload.get("exp", 0)) < time.time():
            return None
        return payload
    except Exception:
        return None


def validar_token(token: str, segredo: str) -> str | None:
    payload = _ler_payload(token, segredo)
    if not payload:
        return None
    if not _sessao_ativa(payload.get("n")):
        return None
    return str(payload.get("u") or "") or None


def revogar_token(token: str, segredo: str) -> None:
    payload = _ler_payload(token, segredo)
    if payload:
        _remover_sessao(payload.get("n"))


def usuario_autenticado(request, segredo: str) -> str | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return validar_token(token, segredo)


# --------------------------------------------------------------------------
# Limite de tentativas de login
# --------------------------------------------------------------------------
_tentativas: dict[str, list[float]] = {}
_tentativas_lock = threading.Lock()


def _poda(agora: float, registros: list[float]) -> list[float]:
    return [t for t in registros if agora - t < JANELA_TENTATIVAS]


def permitir_tentativa(ip: str) -> bool:
    agora = time.time()
    with _tentativas_lock:
        registros = _poda(agora, _tentativas.get(ip, []))
        _tentativas[ip] = registros
        return len(registros) < TENTATIVAS_MAX


def registrar_falha(ip: str) -> None:
    agora = time.time()
    with _tentativas_lock:
        registros = _poda(agora, _tentativas.get(ip, []))
        registros.append(agora)
        _tentativas[ip] = registros


def limpar_falhas(ip: str) -> None:
    with _tentativas_lock:
        _tentativas.pop(ip, None)
