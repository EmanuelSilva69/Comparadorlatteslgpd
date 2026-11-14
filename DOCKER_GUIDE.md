# Guia de Implantação com Docker — Comparador Lattes

Versão sem LLM. A aplicação só lê dados; a coleta roda separada.

## Requisitos

- Docker Engine 24+ com Docker Compose v2
- ~1 GB de RAM e ~500 MB de disco para a aplicação
- (Opcional) nginx com certificado TLS para publicar com HTTPS

## 1. Clonar o repositório

```bash
git clone <url-do-repositorio>
cd ComparadorLattesEnfermagem
```

> O repositório deve ser **privado**: `academicData.ts` e `resumos_cache.json`
> contêm dados pessoais.

## 2. Configurar o login

```bash
chmod +x setup.sh
./setup.sh
```

O script cria o `.env`, gera o segredo de sessão e imprime as senhas de `admin`
e `mestrado` (login mestre da equipe). Guarde-as: o `.env` **não** é versionado.
Todos os logins têm o mesmo nível de acesso.

No Windows, use `.\setup.ps1`.

Se preferir fazer manualmente:

```bash
cp .env.example .env
python tools/gerar_senha.py --usuario admin --escrever
python tools/gerar_senha.py --usuario mestrado --adicionar
```

O `.env` contém segredos e **não deve ser versionado**. Transfira-o para o
servidor por canal seguro (ou gere novamente lá).

## 3. Dados

O site precisa de:

| Arquivo | Origem |
|---------|--------|
| `academicData.ts` | já acompanha o repositório |
| `resumos_cache.json` | já acompanha o repositório |
| `indice_fontes.json` | já acompanha o repositório |

Opcionalmente, para a coleta:

```
dados/
├── mapeamento_lattes.json
├── escavador_perfis/<NOME>/perfil.html
└── scriptLattes/resultados/json/*.json
```

O `docker-compose.yml` monta `./dados` como somente leitura em `/app/dados`.

## 4. Subir a aplicação

```bash
docker compose up -d --build
docker compose logs -f
```

A aplicação escuta apenas em `127.0.0.1:8000` (não fica exposta na rede).

## 5. Publicar com HTTPS (nginx)

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

Com HTTPS, defina `APP_COOKIE_SECURE=1` no `.env` e reinicie:

```bash
docker compose up -d
```

## 6. Rotas

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Frontend (login obrigatório) |
| GET | `/login` | Tela de login |
| POST | `/api/login` | Autentica |
| POST | `/api/logout` | Encerra a sessão |
| GET | `/api/alunos` | Lista de alunos |
| GET | `/api/resumos-cache` | Resumos pré-gerados |
| POST | `/api/update/lattes` | Coleta Lattes (desabilitada no container) |
| POST | `/api/update/escavador` | Coleta Escavador (desabilitada no container) |

## 7. Coleta de dados (fora do servidor web)

A imagem não tem Chrome nem as dependências do `scriptLattes`. Rode a coleta em
uma máquina controlada e copie o resultado para `dados/`:

```bash
pip install -r requirements-coleta.txt
python scraper.py
```

Depois, regenere o índice:

```bash
python -c "from data_parser import gerar_indice_fontes; gerar_indice_fontes()"
```

> Não execute o scraper do Escavador na infraestrutura institucional: ele viola
> os termos de uso do Google/Escavador e pode bloquear o IP da instituição.

## 8. Atualizar

```bash
git pull
docker compose up -d --build
```

## 9. Observações

- **Firewall:** não é necessário liberar a porta 8000; só o proxy acessa.
- **Logs:** `docker compose logs -f app`.
- **Sessões:** reiniciar o container encerra as sessões ativas.
- **LGPD:** registre finalidade e base legal com o DPO antes do deploy.
