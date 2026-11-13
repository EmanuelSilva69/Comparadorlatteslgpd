# Comparador Lattes — Enfermagem (versão sem LLM)

Sistema para acompanhar a trajetória de egressos de pós-graduação, combinando
dados do Lattes (via `scriptLattes`) com perfis públicos do Escavador.

Esta versão **não usa LLM**: os resumos vêm de `resumos_cache.json`. A aplicação
apenas lê e exibe os dados.

## Arquitetura

```
Navegador → (nginx/HTTPS) → FastAPI (login) → data_parser → dados/
```

- **Código** não contém os dados de coleta (HTML do Escavador, currículos, PDFs).
- **Dados de exibição** (`academicData.ts`, `resumos_cache.json`,
  `indice_fontes.json`) acompanham a entrega para o site funcionar.
- **Coleta** (`scriptLattes`, `scraper.py`) roda separada da aplicação web.

## Dados e LGPD

O site precisa apenas de três arquivos. Todo o restante fica fora do Git e é
usado somente pela coleta.

| Arquivo | O site usa? | Local | Conteúdo pessoal |
|---------|-------------|-------|------------------|
| `academicData.ts` | Sim — lista de alunos | repo/imagem | nome, data de defesa, situação, turma |
| `resumos_cache.json` | Sim — resumos pós-defesa | repo/imagem | nome + trajetória profissional |
| `indice_fontes.json` | Sim — selo JSON/HTML | repo/imagem | nomes (derivado, sem dado novo) |
| `mapeamento_lattes.json` | Não — só coleta | `dados/` | nome + ID Lattes/URL |
| `escavador_perfis/` | Não — só coleta | `dados/` | páginas completas, e-mails |
| `demographicData.ts` | Não | `dados/` | nome, sexo, nascimento |
| `scriptLattes/resultados/json/` | Não — só coleta | gerado | currículo completo |
| `CERTIFICADO_*.pdf` | Não | `dados/` | documentos pessoais |

Medidas aplicadas:

- **Minimização**: o site não depende mais dos HTMLs do Escavador nem dos JSONs
  do Lattes. O selo de origem vem de `indice_fontes.json`.
- **Controle de acesso**: login obrigatório em todas as rotas de dados.
- **Finalidade**: acompanhamento de egressos do mestrado em Enfermagem.
- **Segurança**: sessão em cookie `HttpOnly`/`SameSite=Strict`, senha em
  PBKDF2, limite de tentativas, CSRF, CSP e container sem privilégio.

O inventário completo de dados e as pendências de governança estão em
[`PRIVACIDADE.md`](PRIVACIDADE.md).

> **Atenção:** `academicData.ts` e `resumos_cache.json` contêm dados pessoais.
> O repositório deve ser **privado**. Se ele já foi público, remova esses
> arquivos do histórico (ver “Pendências” abaixo) e registre a finalidade e a
> base legal com o DPO da instituição.

## Requisitos

- Python 3.11+
- (Produção) Docker + Docker Compose
- (Coleta) Chrome + `requirements-coleta.txt`

## Configuração

1. Copie o modelo de ambiente:

   ```bash
   cp .env.example .env
   ```

2. Crie o login do responsável e o login mestre da equipe:

   ```bash
   python tools/gerar_senha.py --usuario admin --escrever
   python tools/gerar_senha.py --usuario mestrado --adicionar
   ```

   O primeiro comando grava `APP_SENHA_HASH` e `APP_SECRET_KEY`; o segundo
   adiciona `mestrado` em `APP_USUARIOS`. Todos os logins têm o mesmo nível de
   acesso. Sem `.env`, a aplicação gera uma senha temporária e a imprime no
   console.

3. (Opcional) Coloque os dados de coleta em `./dados/`:

   ```
   dados/
   ├── mapeamento_lattes.json
   ├── escavador_perfis/<NOME>/perfil.html
   └── scriptLattes/resultados/json/*.json
   ```

## Execução local

```bash
pip install -r requirements.txt
python api.py
```

Acesse http://127.0.0.1:8000 — o login é obrigatório.

## Deploy com Docker

```bash
docker compose up -d --build
```

A aplicação escuta apenas em `127.0.0.1:8000`. Publique-a por trás de um
reverse proxy com HTTPS (exemplo de nginx abaixo).

```nginx
server {
    listen 443 ssl;
    server_name comparador.exemplo.edu.br;
    ssl_certificate     /etc/ssl/certs/comparador.crt;
    ssl_certificate_key /etc/ssl/private/comparador.key;

    allow 10.0.0.0/8;   # ajuste à rede interna
    deny  all;

    add_header Content-Security-Policy "default-src 'self'; style-src 'self' 'unsafe-inline'" always;
    add_header X-Content-Type-Options nosniff always;

    location / { proxy_pass http://127.0.0.1:8000; }
}
```

Com HTTPS ativo, defina `APP_COOKIE_SECURE=1` no `.env`.

## Rotas

Todas exigem sessão, exceto `/login` e `/api/login`.

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Frontend (redireciona para `/login` sem sessão) |
| GET | `/login` | Tela de login |
| POST | `/api/login` | Autentica e cria o cookie de sessão |
| POST | `/api/logout` | Encerra a sessão |
| GET | `/api/me` | Usuário autenticado + permissão de atualização |
| GET | `/api/alunos` | Lista de alunos e origem dos dados |
| GET | `/api/resumos-cache` | Resumos pré-gerados |
| POST | `/api/update/lattes` | Coleta Lattes (só com `APP_PERMITIR_ATUALIZACAO=1`) |
| POST | `/api/update/escavador` | Coleta Escavador (idem) |

## Segurança

- Sessão em cookie `HttpOnly`, `SameSite=Strict`, assinado com HMAC-SHA256.
- Senha armazenada como hash PBKDF2-SHA256 (390 mil iterações).
- Limite de 5 tentativas de login por IP a cada 5 minutos.
- POST/PUT/DELETE exigem o cabeçalho `X-Requested-With` (proteção CSRF).
- CORS removido: o frontend é servido pela própria API.
- CSP, `X-Content-Type-Options`, `X-Frame-Options` e `Cache-Control: no-store`.
- Frontend insere dados com `textContent` (sem `innerHTML`).
- Container roda como usuário sem privilégio, com filesystem somente leitura.
- Rotas de atualização protegidas por login, CSRF e lock de execução.

### Pendências que dependem da instituição

1. **LGPD**: registrar finalidade e base legal com o DPO antes do deploy
   (ver `PRIVACIDADE.md`).
2. **Repositório privado** e remoção dos dados do histórico:

   ```bash
   git filter-repo --path escavador_perfis --path demographicData.ts \
       --path mapeamento_lattes.json --invert-paths
   ```

   Depois, force o push. Para o STI clonar um repositório privado, adicione a
   equipe como colaboradora ou use uma deploy key/chave de acesso somente
   leitura — não é preciso tornar o repositório público.
3. **Coleta**: rode `scriptLattes`/`scraper.py` fora do servidor de produção.
4. **TLS**: publique somente via reverse proxy com HTTPS.

## Estrutura

```
├── api.py                  # FastAPI (rotas, auth, cabeçalhos)
├── auth.py                 # Sessão, hash de senha, rate limit
├── data_parser.py          # Leitura dos dados (Lattes/Escavador)
├── public/
│   ├── index.html          # Frontend
│   ├── login.html          # Tela de login
│   └── assets/             # app.js, login.js
├── tools/gerar_senha.py    # Gera hash de senha e atualiza .env
├── academicData.ts         # Lista de alunos (necessário ao site)
├── resumos_cache.json      # Resumos (necessário ao site)
├── indice_fontes.json      # Índice nome → fonte (derivado)
├── dados/                  # Coleta e dados não usados pelo site
├── scraper.py              # Coleta Escavador (fora de produção)
└── scriptLattes/           # Fork do scriptLattes (coleta)
```

## scriptLattes

O `scriptLattes/` é um fork do projeto de Jesús P. Mena-Chalco e
Roberto M. Cesar-Jr (IME/USP), licenciado sob GNU GPL.

## Autor

Emanuel Silva
