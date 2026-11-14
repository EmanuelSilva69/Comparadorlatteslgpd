#!/usr/bin/env bash
# Configuração inicial do Comparador Lattes.
# Cria o .env, gera o segredo de sessão e os logins admin/mestrado.
#
# Uso:
#   ./setup.sh
#
# Requer Python 3.10+ no host (ou rode dentro de um container com Python).

set -euo pipefail
cd "$(dirname "$0")"

if [ -f .env ]; then
    echo "ERRO: .env já existe."
    echo "Apague ou renomeie o .env antes de rodar o setup novamente."
    exit 1
fi

PYTHON=""
for candidato in python3 python; do
    if command -v "$candidato" >/dev/null 2>&1; then
        if "$candidato" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            PYTHON="$candidato"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERRO: Python 3.10+ não encontrado."
    echo "Instale o Python ou rode este setup em um ambiente com Python."
    exit 1
fi

gerar_senha() {
    "$PYTHON" -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range($1)))"
}

SENHA_ADMIN="$(gerar_senha 16)"
SENHA_MESTRE="$(gerar_senha 14)"

"$PYTHON" tools/gerar_senha.py --usuario admin --senha "$SENHA_ADMIN" --escrever >/dev/null
"$PYTHON" tools/gerar_senha.py --usuario mestrado --senha "$SENHA_MESTRE" --adicionar >/dev/null

echo ""
echo "============================================================"
echo " Configuração concluída. Guarde estas credenciais agora."
echo "============================================================"
echo " Login mestre (equipe):"
echo "   usuário: mestrado"
echo "   senha:   $SENHA_MESTRE"
echo ""
echo " Responsável técnico:"
echo "   usuário: admin"
echo "   senha:   $SENHA_ADMIN"
echo "============================================================"
echo ""
echo "O arquivo .env foi criado e NÃO deve ser versionado."
echo "Para trocar uma senha depois:"
echo "  python tools/gerar_senha.py --usuario mestrado --adicionar"
echo ""
