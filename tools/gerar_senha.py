"""Gera hash de senha e atualiza o .env do projeto.

Uso:
    python tools/gerar_senha.py
    python tools/gerar_senha.py --usuario admin --senha "minha-senha" --escrever
    python tools/gerar_senha.py --usuario mestrado --adicionar
"""

from __future__ import annotations

import argparse
import getpass
import secrets
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import auth  # noqa: E402

ENV = RAIZ / ".env"


def ler_env() -> dict[str, str]:
    dados: dict[str, str] = {}
    if not ENV.exists():
        return dados
    for linha in ENV.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        dados[chave.strip()] = valor.strip()
    return dados


def escrever_env(dados: dict[str, str]) -> None:
    linhas = ["# Gerado por tools/gerar_senha.py — NÃO versionar."]
    for chave, valor in dados.items():
        linhas.append(f"{chave}={valor}")
    ENV.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera hash de senha para o Comparador Lattes.")
    parser.add_argument("--usuario", default="admin", help="usuário (padrão: admin)")
    parser.add_argument("--senha", help="senha em texto puro (se omitida, será solicitada)")
    parser.add_argument(
        "--escrever",
        action="store_true",
        help="grava APP_USUARIO/APP_SENHA_HASH no .env",
    )
    parser.add_argument(
        "--adicionar",
        action="store_true",
        help="adiciona o usuário em APP_USUARIOS (login compartilhado)",
    )
    args = parser.parse_args()

    senha = args.senha or getpass.getpass("Senha: ")
    if not senha:
        print("Senha vazia. Nada foi gerado.", file=sys.stderr)
        return 1

    if not args.senha:
        confirmacao = getpass.getpass("Confirme a senha: ")
        if senha != confirmacao:
            print("As senhas não conferem.", file=sys.stderr)
            return 1

    hash_senha = auth.gerar_hash_senha(senha)
    print(f"APP_USUARIO={args.usuario}")
    print(f"APP_SENHA_HASH={hash_senha}")

    if not (args.escrever or args.adicionar):
        return 0

    dados = ler_env()

    if args.adicionar:
        usuarios = dados.get("APP_USUARIOS", "").strip()
        pares = [p for p in usuarios.split(";") if p.strip()]
        pares = [p for p in pares if p.split("|", 1)[0].strip() != args.usuario]
        pares.append(f"{args.usuario}|{hash_senha}")
        dados["APP_USUARIOS"] = ";".join(pares)
    else:
        dados["APP_USUARIO"] = args.usuario
        dados["APP_SENHA_HASH"] = hash_senha

    dados.setdefault("APP_SECRET_KEY", secrets.token_hex(32))
    dados.setdefault("APP_COOKIE_SECURE", "0")
    dados.setdefault("APP_SESSAO_HORAS", "8")
    dados.setdefault("APP_PERMITIR_ATUALIZACAO", "0")

    escrever_env(dados)
    print(f"\n.env atualizado em {ENV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
