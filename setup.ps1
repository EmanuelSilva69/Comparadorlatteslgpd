# Configuração inicial do Comparador Lattes (Windows).
# Cria o .env, gera o segredo de sessão e os logins admin/mestrado.
#
# Uso (PowerShell):
#   .\setup.ps1
#
# Requer Python 3.10+ no host.

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (Test-Path ".env") {
    Write-Host "ERRO: .env já existe." -ForegroundColor Red
    Write-Host "Apague ou renomeie o .env antes de rodar o setup novamente."
    exit 1
}

$python = $null
foreach ($candidato in @("python", "py")) {
    $cmd = Get-Command $candidato -ErrorAction SilentlyContinue
    if ($cmd) {
        & $cmd.Source -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $python = $cmd.Source
            break
        }
    }
}

if (-not $python) {
    Write-Host "ERRO: Python 3.10+ não encontrado." -ForegroundColor Red
    Write-Host "Instale o Python ou rode este setup em um ambiente com Python."
    exit 1
}

function New-Senha([int]$tamanho) {
    return (& $python -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range($tamanho)))").Trim()
}

$senhaAdmin = New-Senha 16
$senhaMestre = New-Senha 14

& $python "tools\gerar_senha.py" --usuario admin --senha $senhaAdmin --escrever | Out-Null
& $python "tools\gerar_senha.py" --usuario mestrado --senha $senhaMestre --adicionar | Out-Null

Write-Host ""
Write-Host "============================================================"
Write-Host " Configuração concluída. Guarde estas credenciais agora."
Write-Host "============================================================"
Write-Host " Login mestre (equipe):"
Write-Host "   usuário: mestrado"
Write-Host "   senha:   $senhaMestre"
Write-Host ""
Write-Host " Responsável técnico:"
Write-Host "   usuário: admin"
Write-Host "   senha:   $senhaAdmin"
Write-Host "============================================================"
Write-Host ""
Write-Host "O arquivo .env foi criado e NÃO deve ser versionado."
Write-Host "Para trocar uma senha depois:"
Write-Host "  python tools/gerar_senha.py --usuario mestrado --adicionar"
